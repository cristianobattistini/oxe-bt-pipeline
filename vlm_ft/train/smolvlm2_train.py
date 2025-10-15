#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fine-tuning di HuggingFaceTB/SmolVLM2-2.2B-Instruct
su dataset JSONL con video e testo (BT XML come target).
Usa la pipeline semplice del notebook SmolVLM2_Video_FT.ipynb.
"""

import os
import json
import argparse
from typing import Dict, Any, List

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoProcessor, AutoModelForImageTextToText, AdamW, get_linear_schedule_with_warmup
from tqdm import tqdm


# -------------------------
# Dataset JSONL (preservato)
# -------------------------
class VLMJsonlDataset(Dataset):
    """
    Tokenizza i messages con AutoProcessor.apply_chat_template.
    Maschera la loss sui token del 'user' e la calcola solo sull'XML dell'assistant.
    """
    def __init__(self, jsonl_path: str, processor: AutoProcessor):
        super().__init__()
        self.processor = processor
        self.samples: List[Dict[str, Any]] = []

        base_dir = os.path.dirname(os.path.abspath(jsonl_path))
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                ex = json.loads(line)
                msgs = ex.get("messages", [])
                if not (isinstance(msgs, list) and len(msgs) == 2 and msgs[0].get("role") == "user" and msgs[1].get("role") == "assistant"):
                    continue
                for c in msgs[0].get("content", []):
                    if isinstance(c, dict) and c.get("type") == "video":
                        p = c.get("path", "")
                        if p and not os.path.isabs(p):
                            c["path"] = os.path.abspath(os.path.join(base_dir, p))
                self.samples.append(ex)

        if not self.samples:
            raise ValueError(f"Nessun sample valido in {jsonl_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        ex = self.samples[idx]
        messages = ex["messages"]

        # Tokenizza
        enc_user = self.processor.apply_chat_template(
            [messages[0]], add_generation_prompt=False, tokenize=True, return_tensors="pt"
        )
        enc_full = self.processor.apply_chat_template(
            messages, add_generation_prompt=False, tokenize=True, return_tensors="pt"
        )

        # Aggiungi dimensione batch se manca
        for k in ["input_ids", "attention_mask"]:
            if k in enc_full and enc_full[k].dim() == 1:
                enc_full[k] = enc_full[k].unsqueeze(0)
            if k in enc_user and enc_user[k].dim() == 1:
                enc_user[k] = enc_user[k].unsqueeze(0)

        input_ids = enc_full["input_ids"][0]
        attention_mask = enc_full["attention_mask"][0]
        labels = input_ids.clone()

        # Maschera i token utente
        user_len = enc_user["input_ids"].shape[-1]
        labels[:user_len] = -100

        sample = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }
        for k, v in enc_full.items():
            if k not in ("input_ids", "attention_mask"):
                sample[k] = v
        return sample



# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_jsonl", type=str, required=True)
    parser.add_argument("--val_jsonl", type=str)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--model_id", type=str, default="HuggingFaceTB/SmolVLM2-2.2B-Instruct")
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=16)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    print(f"Carico processor e modello: {args.model_id}")
    processor = AutoProcessor.from_pretrained(args.model_id, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model_id, trust_remote_code=True, torch_dtype="auto", device_map="auto"
    )

    train_ds = VLMJsonlDataset(args.train_jsonl, processor)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=lambda x: x[0])

    optimizer = AdamW(model.parameters(), lr=args.lr)
    num_training_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=num_training_steps)

    model.train()
    global_step = 0
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch+1}/{args.epochs}")
        for batch in tqdm(train_loader):
            for k in batch:
                if torch.is_tensor(batch[k]):
                    batch[k] = batch[k].to(device)

            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()

            if (global_step + 1) % args.gradient_accumulation_steps == 0:
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

            if global_step % 10 == 0:
                print(f"Step {global_step}: loss = {loss.item():.4f}")
            global_step += 1

    os.makedirs(args.output_dir, exist_ok=True)
    model.save_pretrained(args.output_dir)
    processor.save_pretrained(args.output_dir)
    print(f"Modello salvato in {args.output_dir}")


if __name__ == "__main__":
    main()


'''

python3 smolvlm2_train.py \
  --train_jsonl /home/battistini/private_datasets/train/data.jsonl \
  --val_jsonl   /home/battistini/private_datasets/val/data.jsonl \
  --output_dir  /home/battistini/exp/outputs/ft-smolvlm2-bt-video \
  --batch_size 1 \
  --gradient_accumulation_steps 32 \
  --lr 2e-4 \
  --epochs 1


'''