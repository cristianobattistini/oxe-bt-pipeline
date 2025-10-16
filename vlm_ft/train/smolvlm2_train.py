#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
from typing import Dict, Any, List

import torch
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence
from transformers import (
    AutoProcessor,
    BitsAndBytesConfig,
    AutoModelForImageTextToText,
    AdamW,
    get_linear_schedule_with_warmup,
)
from peft import LoraConfig, prepare_model_for_kbit_training, get_peft_model
from tqdm import tqdm


# -------------------------
# Dataset JSONL
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
                if not (isinstance(msgs, list)
                        and len(msgs) == 2
                        and msgs[0].get("role") == "user"
                        and msgs[1].get("role") == "assistant"):
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

        enc_user = self.processor.apply_chat_template(
            [messages[0]], add_generation_prompt=False, tokenize=True, return_tensors="pt"
        )
        enc_full = self.processor.apply_chat_template(
            messages, add_generation_prompt=False, tokenize=True, return_tensors="pt"
        )

        if isinstance(enc_full, dict):
            for k in ["input_ids", "attention_mask"]:
                if k in enc_full and hasattr(enc_full[k], "dim") and enc_full[k].dim() == 1:
                    enc_full[k] = enc_full[k].unsqueeze(0)
        if isinstance(enc_user, dict):
            for k in ["input_ids", "attention_mask"]:
                if k in enc_user and hasattr(enc_user[k], "dim") and enc_user[k].dim() == 1:
                    enc_user[k] = enc_user[k].unsqueeze(0)

        input_ids = enc_full["input_ids"][0]
        attention_mask = enc_full["attention_mask"][0]
        labels = input_ids.clone()
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
# Collate function
# -------------------------
def collate_fn(examples):
    input_ids = pad_sequence(
        [ex["input_ids"] for ex in examples],
        batch_first=True,
        padding_value=processor.tokenizer.pad_token_id
    )
    attention_mask = pad_sequence(
        [ex["attention_mask"] for ex in examples],
        batch_first=True,
        padding_value=0
    )
    labels = pad_sequence(
        [ex["labels"] for ex in examples],
        batch_first=True,
        padding_value=-100
    )

    image_token_id = processor.tokenizer.additional_special_tokens_ids[
        processor.tokenizer.additional_special_tokens.index("<image>")
    ]
    labels[labels == image_token_id] = -100

    out = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels
    }

    if "pixel_values" in examples[0]:
        pvs = [ex["pixel_values"] for ex in examples]
        max_frames = max(pv.shape[0] for pv in pvs)
        max_h = max(pv.shape[-2] for pv in pvs)
        max_w = max(pv.shape[-1] for pv in pvs)

        padded_pixel_values_list = []
        for pv in pvs:
            f, c, h, w = pv.shape
            padded = torch.zeros(
                (max_frames, c, max_h, max_w),
                dtype=pv.dtype,
                device=pv.device
            )
            padded[:f, :, :h, :w] = pv
            padded_pixel_values_list.append(padded)

        out["pixel_values"] = torch.stack(padded_pixel_values_list, dim=0)

    return out


# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_jsonl", type=str, required=True)
    parser.add_argument("--val_jsonl", type=str)
    parser.add_argument("--use_qlora", action="store_true")
    parser.add_argument("--use_lora", action="store_true")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--model_id", type=str, default="HuggingFaceTB/SmolVLM2-2.2B-Instruct")
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=16)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    processor = AutoProcessor.from_pretrained(args.model_id, trust_remote_code=True)

    if args.use_qlora or args.use_lora:
        lora_config = LoraConfig(
            r=8,
            lora_alpha=8,
            lora_dropout=0.1,
            target_modules=['down_proj', 'o_proj', 'k_proj', 'q_proj', 'gate_proj', 'up_proj', 'v_proj'],
            use_dora=not args.use_qlora,
            init_lora_weights="gaussian"
        )
        lora_config.inference_mode = False

        bnb_config = None
        if args.use_qlora:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16
            )

        model = AutoModelForImageTextToText.from_pretrained(
            args.model_id,
            quantization_config=bnb_config,
            _attn_implementation="flash_attention_2",
            device_map="auto",
            trust_remote_code=True,
        )
        model.add_adapter(lora_config)
        model.enable_adapters()
        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(model, lora_config)
        print(model.get_nb_trainable_parameters())
    else:
        model = AutoModelForImageTextToText.from_pretrained(
            args.model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
            _attn_implementation="flash_attention_2",
        ).to(device)

        # opzionale: blocca la parte vision
        for param in model.model.vision_model.parameters():
            param.requires_grad = False

    peak_mem = torch.cuda.max_memory_allocated()
    print(f"The model as is is holding: {peak_mem / 1024**3:.2f} GB of GPU RAM")

    train_ds = VLMJsonlDataset(args.train_jsonl, processor)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)

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
