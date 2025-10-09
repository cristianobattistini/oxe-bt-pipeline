#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fine-tuning di HuggingFaceTB/SmolVLM2-2.2B-Instruct su dataset JSONL (video + istruzione -> BT XML),
replicando la soluzione dei notebook: il processor legge i video dai path dentro ai messages.
Nessuna decodifica/campionamento frame manuale nel codice: delega al processor.

Formato atteso JSONL (una riga per sample):
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type":"text","text":"SYSTEM/CONSTRAINTS..."},
        {"type":"text","text":"INSTRUCTION..."},
        {"type":"video","path":"videos/<ds>/<ep>/contact_video.mp4"}
      ]
    },
    {
      "role":"assistant",
      "content":[{"type":"text","text":"<BehaviorTree ID=\"MainTree\"> ... </BehaviorTree>"}]
    }
  ],
  "meta": {"dataset_id":"...", "episode_id":"..."}
}

Uso tipico:
  python3 train_smolvlm2_train.py \
      --train_jsonl /path/to/private_datasets/train/data.jsonl \
      --val_jsonl   /path/to/private_datasets/val/data.jsonl \
      --output_dir  /path/to/ft-smolvlm2-bt-video \
      --model_id    HuggingFaceTB/SmolVLM2-2.2B-Instruct \
      --per_device_train_batch_size 1 \
      --gradient_accumulation_steps 16 \
      --learning_rate 2e-4 \
      --num_train_epochs 3 \
      --use_lora 1 \
      --lora_r 16 --lora_alpha 32 --lora_dropout 0.05
"""

import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List

import torch
from torch.utils.data import Dataset

from transformers import (
    AutoProcessor,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    set_seed,
)
from peft import LoraConfig, get_peft_model


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train_jsonl", type=str, required=True)
    ap.add_argument("--val_jsonl",   type=str, required=True)
    ap.add_argument("--output_dir",  type=str, required=True)
    ap.add_argument("--model_id",    type=str, default="HuggingFaceTB/SmolVLM2-2.2B-Instruct")

    ap.add_argument("--seed", type=int, default=42)

    ap.add_argument("--per_device_train_batch_size", type=int, default=1)
    ap.add_argument("--per_device_eval_batch_size",  type=int, default=1)
    ap.add_argument("--gradient_accumulation_steps", type=int, default=16)
    ap.add_argument("--learning_rate", type=float, default=2e-4)
    ap.add_argument("--num_train_epochs", type=int, default=3)
    ap.add_argument("--weight_decay", type=float, default=0.0)
    ap.add_argument("--warmup_ratio", type=float, default=0.03)
    ap.add_argument("--logging_steps", type=int, default=20)
    ap.add_argument("--save_steps", type=int, default=500)
    ap.add_argument("--save_total_limit", type=int, default=2)
    ap.add_argument("--eval_steps", type=int, default=500)

    ap.add_argument("--use_lora", type=int, default=1)
    ap.add_argument("--lora_r", type=int, default=16)
    ap.add_argument("--lora_alpha", type=int, default=32)
    ap.add_argument("--lora_dropout", type=float, default=0.05)

    ap.add_argument("--load_in_8bit", type=int, default=0)
    ap.add_argument("--load_in_4bit", type=int, default=0)

    return ap.parse_args()


class VLMJsonlDataset(Dataset):
    """
    Legge JSONL con messages (user: text+video path; assistant: XML).
    Tokenizza con AutoProcessor.apply_chat_template lasciando i path video nei messages:
    il processor carica e campiona i frame internamente (backend: pyav o decord).
    Maschera la loss sui token del 'user' (labels=-100) e la calcola solo sull'XML dell'assistant.

    Per mascherare correttamente, tokenizziamo due volte:
      1) solo il messaggio 'user' (con path video), per conoscere la sua lunghezza in token.
      2) l'intera conversazione (user+assistant), per ottenere input_ids/labels finali.
    """
    def __init__(self, jsonl_path: str, processor: AutoProcessor):
        super().__init__()
        self.processor = processor
        self.samples: List[Dict[str, Any]] = []
        self.base_dir = os.path.dirname(os.path.abspath(jsonl_path))
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                ex = json.loads(line)
                msgs = ex.get("messages", [])
                if not (isinstance(msgs, list) and len(msgs) == 2 and msgs[0].get("role") == "user" and msgs[1].get("role") == "assistant"):
                    continue
                # Normalizza eventuali path relativi rispetto alla posizione del JSONL
                for c in msgs[0].get("content", []):
                    if isinstance(c, dict) and c.get("type") == "video" and "path" in c and c["path"] and not os.path.isabs(c["path"]):
                        c["path"] = os.path.abspath(os.path.join(self.base_dir, c["path"]))
                self.samples.append(ex)
        if len(self.samples) == 0:
            raise ValueError(f"Nessun sample valido in {jsonl_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        ex = self.samples[idx]
        messages = ex["messages"]

        # 1) Tokenizza solo il 'user' per ottenere la lunghezza in token del prompt (inclusi token video speciali)
        msgs_user = [messages[0]]
        enc_user = self.processor.apply_chat_template(
            msgs_user,
            add_generation_prompt=False,
            return_tensors="pt",
        )

        # 2) Tokenizza la conversazione completa (user + assistant)
        enc_full = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=False,
            return_tensors="pt",
        )

        # 3) Costruisci labels mascherando i token del 'user'
        input_ids = enc_full["input_ids"][0]            # (L,)
        attention_mask = enc_full["attention_mask"][0]  # (L,)
        labels = input_ids.clone()
        user_len = enc_user["input_ids"].shape[-1]
        labels[:user_len] = -100

        # 4) Includi eventuali chiavi visive che il processor abbia prodotto (pixel_values_videos, ecc.)
        sample = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }
        for k, v in enc_full.items():
            if k in ("input_ids", "attention_mask"):
                continue
            # Generalmente è un tensore video già pronto. Lo teniamo.
            sample[k] = v

        return sample


class DataCollatorVLM:
    """
    Padding di input_ids/attention_mask/labels; gli altri tensori (video) vengono impilati se hanno shape compatibili.
    """
    def __init__(self, processor: AutoProcessor):
        self.processor = processor

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        batch = {}
        pad_id = self.processor.tokenizer.pad_token_id

        for k in ("input_ids", "attention_mask", "labels"):
            seqs = [f[k] for f in features]
            if not torch.is_tensor(seqs[0]):
                seqs = [torch.tensor(s) for s in seqs]
            batch[k] = torch.nn.utils.rnn.pad_sequence(
                seqs, batch_first=True,
                padding_value=(pad_id if k != "labels" else -100)
            )

        # Altri campi (tipicamente pixel_values_video)
        for k in features[0].keys():
            if k in batch or k in ("input_ids", "attention_mask", "labels"):
                continue
            vals = [f[k] for f in features]
            if torch.is_tensor(vals[0]):
                try:
                    batch[k] = torch.stack(vals, dim=0)
                except Exception:
                    # fallback: lista
                    batch[k] = vals
            else:
                batch[k] = vals
        return batch


def main():
    args = parse_args()
    set_seed(args.seed)

    torch_dtype = "auto"
    device_map = "auto"

    quant_kwargs = {}
    if args.load_in_8bit:
        quant_kwargs["load_in_8bit"] = True
        device_map = "auto"
    if args.load_in_4bit:
        quant_kwargs["load_in_4bit"] = True
        device_map = "auto"

    print(f"Carico processor e modello: {args.model_id}")
    processor = AutoProcessor.from_pretrained(args.model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype=torch_dtype,
        device_map=device_map,
        trust_remote_code=True,
        **quant_kwargs
    )

    if args.use_lora:
        print("Abilito LoRA...")
        peft_cfg = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, peft_cfg)

    print("Costruisco dataset...")
    train_ds = VLMJsonlDataset(args.train_jsonl, processor)
    val_ds   = VLMJsonlDataset(args.val_jsonl, processor)
    collator = DataCollatorVLM(processor)

    print("Imposto TrainingArguments...")
    targs = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        warmup_ratio=args.warmup_ratio,
        weight_decay=args.weight_decay,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        evaluation_strategy="steps",
        eval_steps=args.eval_steps,
        bf16=torch.cuda.is_available(),
        fp16=not torch.cuda.is_available(),
        dataloader_num_workers=2,
        report_to=["tensorboard"],   # invece di []
        logging_dir=f"{args.output_dir}/tb",  # cartella per i log
    )

    trainer = Trainer(
        model=model,
        args=targs,
        data_collator=collator,
        train_dataset=train_ds,
        eval_dataset=val_ds,
    )

    print("Avvio training...")
    trainer.train()

    print("Salvo modello e processor...")
    trainer.save_model(args.output_dir)
    processor.save_pretrained(args.output_dir)

    print("Done.")


if __name__ == "__main__":
    main()


'''

tmux new -s smolft
# (dentro tmux) avvia il training, meglio salvare anche lo stdout:
python3 train_smolvlm2_bt_video_paths.py \
  --train_jsonl .../train/data.jsonl \
  --val_jsonl   .../val/data.jsonl \
  --output_dir  /home/<cognome>/storage/models/ft-smolvlm2-bt-video \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 16 \
  --learning_rate 2e-4 \
  --num_train_epochs 3 \
  --use_lora 1 | tee /home/<cognome>/storage/logs/smolvlm2_bt_video.log

# stacca la sessione senza fermare il job:
Ctrl-b d

# per rientrare:
tmux attach -t smolft

<!-- Esempio di comando usato per il training (con batch size 1 e grad acc 32 per batch effettivo 32) -->


python3 vlm_ft/train_smolvlm2_bt_video_paths.py \
  --train_jsonl /home/battistini/private_datasets/train/data.jsonl \
  --val_jsonl   /home/battistini/private_datasets/val/data.jsonl \
  --output_dir  /home/battistini/exp/outputs/ft-smolvlm2-bt-video \
  --model_id HuggingFaceTB/SmolVLM2-2.2B-Instruct \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 32 \
  --learning_rate 2e-4 \
  --num_train_epochs 1 \
  --use_lora 1 \
  --load_in_4bit 1 \
  --lora_r 16 --lora_alpha 32 --lora_dropout 0.05


'''