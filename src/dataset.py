"""Dataset and collate function for vision-language behavior tree data."""
import os
import json
import random
from pathlib import Path
from typing import Dict, Any, List
import torch
from torch.utils.data import Dataset
from torch.nn.utils.rnn import pad_sequence
from transformers import AutoProcessor
import logging

logger = logging.getLogger(__name__)


class VLMJsonlDataset(Dataset):
    """
    JSONL dataset for vision-language models.
    
    Each line contains:
    {
        "messages": [
            {"role": "user", "content": [{"type": "text", ...}, {"type": "image/video", "path": ...}]},
            {"role": "assistant", "content": [{"type": "text", "text": "..."}]}
        ]
    }
    """
    
    def __init__(self, jsonl_path: str):
        super().__init__()
        self.samples: List[Dict[str, Any]] = []
        jsonl_path = Path(jsonl_path)
        base_dir = jsonl_path.parent
        
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                
                ex = json.loads(line)
                msgs = ex.get("messages", [])
                
                # Validate message structure
                if not (isinstance(msgs, list) and len(msgs) == 2 and
                        msgs[0].get("role") == "user" and
                        msgs[1].get("role") == "assistant"):
                    continue
                
                # Resolve media paths (PLATFORM-AGNOSTIC)
                for c in msgs[0].get("content", []):
                    media_type = c.get("type")
                    if isinstance(c, dict) and media_type in ("video", "image"):
                        p = c.get("path", "")
                        if not p:
                            continue
                        
                        # Convert to Path and handle both / and \
                        p_normalized = Path(p.replace("\\", "/"))
                        
                        # Try relative to base_dir
                        abs_p = (base_dir / p_normalized).resolve()
                        
                        # Fallback path resolution
                        if not abs_p.exists():
                            alt_p = (base_dir.parent / "train" / p_normalized).resolve()
                            if alt_p.exists():
                                abs_p = alt_p
                            else:
                                logger.warning(f"{media_type.upper()} not found: {abs_p}")
                                c.clear()
                                c["type"] = "text"
                                c["text"] = f"[{media_type.upper()}_MISSING]"
                                continue
                        
                        # Store as POSIX path string (always uses /)
                        c["path"] = abs_p.as_posix()
                
                self.samples.append({"messages": msgs})
        
        if not self.samples:
            raise ValueError(f"No valid samples found in {jsonl_path}")
        
        logger.info(f"Loaded {len(self.samples)} samples from {jsonl_path}")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self.samples[idx]


def make_collate_fn(processor: AutoProcessor, dropout_ratio: float = 0.0):
    """
    Create collate function that tokenizes, pads, and masks labels.
    
    Args:
        processor: HuggingFace processor with tokenizer
        dropout_ratio: Probability of dropping instruction text (for robustness)
    
    Returns:
        Collate function for DataLoader
    """
    # Ensure pad token is set
    if processor.tokenizer.pad_token_id is None:
        if processor.tokenizer.eos_token_id is None:
            raise ValueError("Tokenizer has no pad_token and no eos_token.")
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    
    pad_id = processor.tokenizer.pad_token_id
    
    # Get <image> token ID for label masking (with fallback)
    image_tok_id = None
    possible_tokens = ["<image>", "<img>", "<IMAGE>"]
    
    for token in possible_tokens:
        if token in processor.tokenizer.additional_special_tokens:
            idx = processor.tokenizer.additional_special_tokens.index(token)
            image_tok_id = processor.tokenizer.additional_special_tokens_ids[idx]
            logger.info(f"Using image token: '{token}' (ID: {image_tok_id})")
            break
    
    if image_tok_id is None:
        logger.warning("No image token found in tokenizer. Image tokens will not be masked in labels.")
    
    def collate(examples: List[Dict[str, Any]]):
        items = []
        
        for ex in examples:
            messages = ex["messages"]
            
            # Optional instruction dropout
            if dropout_ratio > 0 and random.random() < dropout_ratio:
                user_content = messages[0].get("content", [])
                for content_part in user_content:
                    if (content_part.get("type") == "text" and
                        content_part.get("text", "").lstrip().startswith("INSTRUCTION:")):
                        content_part["text"] = ""
                        break
            
            # Tokenize full conversation
            inst = processor.apply_chat_template(
                messages,
                add_generation_prompt=False,
                tokenize=True,
                return_tensors="pt",
                return_dict=True,
            )
            
            # Tokenize user message only (for label masking)
            enc_user = processor.apply_chat_template(
                [messages[0]],
                add_generation_prompt=False,
                tokenize=True,
                return_tensors="pt",
                return_dict=True,
            )
            
            # Ensure tensors are 2D
            for k in ("input_ids", "attention_mask"):
                if isinstance(inst[k], torch.Tensor) and inst[k].dim() == 1:
                    inst[k] = inst[k].unsqueeze(0)
            
            input_ids = inst["input_ids"].squeeze(0)
            attention_mask = inst["attention_mask"].squeeze(0)
            labels = input_ids.clone()
            
            # Mask user tokens in labels
            user_len = enc_user["input_ids"].shape[-1]
            labels[:user_len] = -100
            
            # Mask <image> tokens in labels
            if image_tok_id is not None:
                labels[labels == image_tok_id] = -100
            
            item = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels
            }
            
            # Handle pixel values (images/videos)
            if "pixel_values" in inst:
                pv = inst["pixel_values"]
                # Remove batch dimension if present
                if pv.dim() == 5 and pv.shape[0] == 1:
                    pv = pv.squeeze(0)
                item["pixel_values"] = pv
            
            items.append(item)
        
        # Pad sequences
        batch_input_ids = pad_sequence(
            [it["input_ids"] for it in items],
            batch_first=True,
            padding_value=pad_id
        )
        batch_attention = pad_sequence(
            [it["attention_mask"] for it in items],
            batch_first=True,
            padding_value=0
        )
        batch_labels = pad_sequence(
            [it["labels"] for it in items],
            batch_first=True,
            padding_value=-100
        )
        
        batch = {
            "input_ids": batch_input_ids,
            "attention_mask": batch_attention,
            "labels": batch_labels,
        }
        
        # Pad pixel values (for videos with different frame counts)
        if "pixel_values" in items[0]:
            pvs = [it["pixel_values"] for it in items]
            max_f = max(pv.shape[0] for pv in pvs)
            C, H, W = pvs[0].shape[1:]
            
            padded = []
            for pv in pvs:
                F = pv.shape[0]
                if F < max_f:
                    pad = torch.zeros((max_f - F, C, H, W), dtype=pv.dtype)
                    pv = torch.cat([pv, pad], dim=0)
                padded.append(pv)
            
            batch["pixel_values"] = torch.stack(padded, dim=0)
        
        return batch
    
    return collate
