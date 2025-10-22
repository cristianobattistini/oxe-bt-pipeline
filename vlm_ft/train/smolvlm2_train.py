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

from torch.utils.tensorboard import SummaryWriter


# Disabilita FlashAttention; abilita backend SDPA compatibili
try:
    from torch.backends.cuda import sdp_kernel
    sdp_kernel(enable_flash=False, enable_mem_efficient=True, enable_math=True)
except Exception:
    # fallback per versioni PyTorch precedenti
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    torch.backends.cuda.enable_math_sdp(True)



def move_to_device(batch, device):
    if torch.is_tensor(batch):
        return batch.to(device, non_blocking=True)
    if isinstance(batch, dict):
        return {k: move_to_device(v, device) for k, v in batch.items()}
    if isinstance(batch, (list, tuple)):
        return type(batch)(move_to_device(x, device) for x in batch)
    return batch


def _safe_makedirs(p):
    os.makedirs(p, exist_ok=True)

def _rotate_checkpoints(ckpt_dir, keep_last_k):
    if keep_last_k <= 0 or not os.path.isdir(ckpt_dir):
        return
    sub = sorted([d for d in os.listdir(ckpt_dir) if (ckpt_dir+'/'+d).endswith(('/')) or True],
                 key=lambda x: os.path.getmtime(os.path.join(ckpt_dir, x)))
    if len(sub) <= keep_last_k:
        return
    for d in sub[:-keep_last_k]:
        try:
            import shutil
            shutil.rmtree(os.path.join(ckpt_dir, d), ignore_errors=True)
        except Exception:
            pass

def save_checkpoint(tag, model, processor, optimizer, scheduler, global_step, epoch, ckpt_dir, use_lora):
    """Salva adapter/weights + stato ottimizzatore/scheduler."""
    path = os.path.join(ckpt_dir, tag)
    _safe_makedirs(path)

    # 1) pesi modello
    if use_lora:
        # salva SOLO l’adapter (leggero)
        model.save_pretrained(path)
    else:
        # salva tutto (pesante!)
        model.save_pretrained(path)

    # 2) metadati/optimizer/scheduler
    state = {
        "global_step": int(global_step),
        "epoch": int(epoch),
        "optimizer": optimizer.state_dict() if optimizer is not None else None,
        "scheduler": scheduler.state_dict() if scheduler is not None else None,
        "rng": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["cuda_rng"] = torch.cuda.get_rng_state_all()

    torch.save(state, os.path.join(path, "trainer_state.pt"))

    # 3) symlink 'latest'
    latest = os.path.join(ckpt_dir, "latest")
    try:
        if os.path.islink(latest) or os.path.exists(latest):
            import shutil
            if os.path.islink(latest): os.unlink(latest)
            elif os.path.isdir(latest): shutil.rmtree(latest)
            else: os.remove(latest)
        os.symlink(path, latest, target_is_directory=True)
    except Exception:
        pass

def load_checkpoint_if_any(model, resume_path, optimizer=None, scheduler=None, device="cuda", use_lora=True):
    """Carica adapter/weights e stato ottimizzatore/scheduler se presenti."""
    if resume_path is None:
        return model, optimizer, scheduler, 0, 0

    # 1) pesi modello
    if use_lora:
        from peft import PeftModel
        # carica gli adapter dentro al modello corrente
        model = PeftModel.from_pretrained(model, resume_path, is_trainable=True)
    else:
        # per full-finetune: ricarica pesi completi
        from transformers import AutoModelForImageTextToText
        # Nota: in questo caso conviene ri-creare il modello da resume_path,
        # ma dato che abbiamo già una istanza, carichiamo lo state_dict:
        sd = torch.load(os.path.join(resume_path, "pytorch_model.bin"), map_location=device)
        model.load_state_dict(sd, strict=False)

    # 2) stato trainer
    trainer_state = os.path.join(resume_path, "trainer_state.pt")
    start_step, start_epoch = 0, 0
    if os.path.exists(trainer_state):
        st = torch.load(trainer_state, map_location=device)
        start_step = int(st.get("global_step", 0))
        start_epoch = int(st.get("epoch", 0))
        if optimizer is not None and st.get("optimizer") is not None:
            optimizer.load_state_dict(st["optimizer"])
        if scheduler is not None and st.get("scheduler") is not None:
            scheduler.load_state_dict(st["scheduler"])
        try:
            torch.set_rng_state(st["rng"])
            if torch.cuda.is_available() and "cuda_rng" in st:
                torch.cuda.set_rng_state_all(st["cuda_rng"])
        except Exception:
            pass

    print(f"[RESUME] Ripartenza da {resume_path} (epoch={start_epoch}, step={start_step})")
    return model, optimizer, scheduler, start_step, start_epoch


# -------------------------
# Dataset: NON tokenizza, risolve solo i path.
# -------------------------
class VLMJsonlDataset(Dataset):
    """
    Restituisce solo {"messages": [...]} con path video assoluti.
    Non chiama il processor: questo avviene nella collate_fn.
    """
    def __init__(self, jsonl_path: str):
        super().__init__()
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

                # Risoluzione path per eventuali video nel messaggio user
                for c in msgs[0].get("content", []):
                    if isinstance(c, dict) and c.get("type") == "video":
                        p = c.get("path", "")
                        if not p:
                            continue
                        abs_p = os.path.abspath(os.path.join(base_dir, p))
                        if not os.path.exists(abs_p):
                            # fallback: .../train/<p>
                            alt_p = os.path.abspath(os.path.join(os.path.dirname(base_dir), "train", p))
                            if os.path.exists(alt_p):
                                abs_p = alt_p
                            else:
                                print(f"[WARN] Video non trovato: {abs_p}")
                                # evita crash del processor se il file manca
                                c.clear()
                                c["type"] = "text"
                                c["text"] = "[VIDEO_MISSING]"
                        c["path"] = abs_p

                self.samples.append({"messages": msgs})

        if not self.samples:
            raise ValueError(f"Nessun sample valido in {jsonl_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self.samples[idx]


# -------------------------
# Collate: come nel tutorial (processor + maschere + padding)
# -------------------------
def make_collate_fn(processor: AutoProcessor):
    # garantisci il pad token
    if processor.tokenizer.pad_token_id is None:
        if processor.tokenizer.eos_token_id is None:
            raise ValueError("Tokenizer senza pad_token e senza eos_token.")
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    pad_id = processor.tokenizer.pad_token_id

    # id del token <image> da mascherare
    image_tok_id = None
    if "<image>" in processor.tokenizer.additional_special_tokens:
        idx = processor.tokenizer.additional_special_tokens.index("<image>")
        image_tok_id = processor.tokenizer.additional_special_tokens_ids[idx]

    def collate(examples: List[Dict[str, Any]]):
        items = []
        for ex in examples:
            messages = ex["messages"]

            # chat completa (user+assistant) — include anche i video
            inst = processor.apply_chat_template(
                messages,
                add_generation_prompt=False,
                tokenize=True,
                return_tensors="pt",
                return_dict=True,
            )
            # solo utente: serve per mascherare le label
            enc_user = processor.apply_chat_template(
                [messages[0]],
                add_generation_prompt=False,
                tokenize=True,
                return_tensors="pt",
                return_dict=True,
            )

            for k in ("input_ids", "attention_mask"):
                if isinstance(inst[k], torch.Tensor) and inst[k].dim() == 1:
                    inst[k] = inst[k].unsqueeze(0)

            input_ids = inst["input_ids"].squeeze(0)        # CPU
            attention_mask = inst["attention_mask"].squeeze(0)  # CPU

            labels = input_ids.clone()
            user_len = enc_user["input_ids"].shape[-1]
            labels[:user_len] = -100
            if image_tok_id is not None:
                labels[labels == image_tok_id] = -100

            item = {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}

            # pixel_values opzionali (se c'è "video" nei messages)
            if "pixel_values" in inst:
                pv = inst["pixel_values"]  # (1,F,C,H,W) o (F,C,H,W)
                if pv.dim() == 5 and pv.shape[0] == 1:
                    pv = pv.squeeze(0)
                item["pixel_values"] = pv  # CPU

            items.append(item)

        # padding testo (CPU)
        batch_input_ids = pad_sequence([it["input_ids"] for it in items],
                                       batch_first=True, padding_value=pad_id)
        batch_attention = pad_sequence([it["attention_mask"] for it in items],
                                       batch_first=True, padding_value=0)
        batch_labels = pad_sequence([it["labels"] for it in items],
                                    batch_first=True, padding_value=-100)

        batch = {
            "input_ids": batch_input_ids,
            "attention_mask": batch_attention,
            "labels": batch_labels,
        }

        # padding video sui frame (CPU)
        if "pixel_values" in items[0]:
            pvs = [it["pixel_values"] for it in items]  # ciascuno (F,C,H,W)
            max_f = max(pv.shape[0] for pv in pvs)
            C, H, W = pvs[0].shape[1:]
            padded = []
            for pv in pvs:
                F = pv.shape[0]
                if F < max_f:
                    pad = torch.zeros((max_f - F, C, H, W), dtype=pv.dtype)
                    pv = torch.cat([pv, pad], dim=0)
                padded.append(pv)
            batch["pixel_values"] = torch.stack(padded, dim=0)  # (B,F,C,H,W) — CPU

        return batch

    return collate


@torch.no_grad()
def evaluate(model, val_loader, device, writer=None, epoch=None):
    if val_loader is None:
        return None

    model.eval()
    total_loss, total_steps = 0.0, 0

    for batch in val_loader:
        # CPU -> GPU
        batch = move_to_device(batch, device)
        if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
            batch["pixel_values"] = batch["pixel_values"].to(torch.float32, non_blocking=True)

        outputs = model(**batch)
        loss = outputs.loss
        total_loss += loss.item()
        total_steps += 1

    val_loss = total_loss / max(1, total_steps)
    if writer is not None and epoch is not None:
        writer.add_scalar("loss/val_epoch", val_loss, epoch)

    model.train()   # IMPORTANT: torna in train mode
    return val_loss


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
    parser.add_argument("--num_workers", type=int, default=0)  # alza dopo il primo run
    parser.add_argument("--log_dir", type=str, default=None)
    parser.add_argument("--val_every", type=int, default=1, help="Valida ogni N epoche (default: 1)")
    parser.add_argument("--patience", type=int, default=0, help="Early stopping patience in epoche (0=disattivato)")
    parser.add_argument("--checkpoint_dir", type=str, default=None,
                    help="Dove salvare i checkpoint (default: <output_dir>/ckpts)")
    parser.add_argument("--save_every_steps", type=int, default=0,
                        help="Salva un checkpoint ogni N step (0=disattivo)")
    parser.add_argument("--save_every_epochs", type=int, default=1,
                        help="Salva un checkpoint al termine di ogni N epoche (0=disattivo)")
    parser.add_argument("--keep_last_k", type=int, default=3,
                        help="Conserva solo gli ultimi K checkpoint (0=tutti)")
    parser.add_argument("--resume_from", type=str, default=None,
                        help="Cartella di un checkpoint da cui riprendere")
    
    ckpt_dir = args.checkpoint_dir or os.path.join(args.output_dir, "ckpts")
    _safe_makedirs(args.output_dir)
    _safe_makedirs(ckpt_dir)



    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    processor = AutoProcessor.from_pretrained(args.model_id, trust_remote_code=True)

    # ----------------- Modello -----------------
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
            _attn_implementation="eager",
            device_map="auto",
            max_memory={0: "11GiB", 1: "11GiB"},
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
            device_map="auto",
            trust_remote_code=True,
            _attn_implementation="eager",
        ).to(device)

        # opzionale: blocca la parte vision
        for param in model.model.vision_model.parameters():
            param.requires_grad = False


    # subito dopo aver creato `model`
    model.config.use_cache = False                 # evita attivazioni extra
    model.gradient_checkpointing_enable()          # abbatte la memoria attivazioni


    peak_mem = torch.cuda.max_memory_allocated()
    print(f"The model as is is holding: {peak_mem / 1024**3:.2f} GB of GPU RAM")

    # ----------------- Dati & DataLoader -----------------
    train_ds = VLMJsonlDataset(args.train_jsonl)
    collate = make_collate_fn(processor)
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate,
        num_workers=args.num_workers,
        pin_memory=(device == "cuda"),   # OK: i tensori sono CPU qui
    )

    val_loader = None
    if args.val_jsonl and os.path.exists(args.val_jsonl):
        val_ds = VLMJsonlDataset(args.val_jsonl)
        val_loader = DataLoader(
            val_ds,
            batch_size=args.batch_size,  # spesso si può alzare un po' perché non si fa backward
            shuffle=False,
            collate_fn=collate,
            num_workers=args.num_workers,
            pin_memory=(device == "cuda"),
        )


    # ----------------- Ottimizzazione -----------------
    optimizer = AdamW(model.parameters(), lr=args.lr)

    num_training_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, num_training_steps // 100),
        num_training_steps=num_training_steps,
    )

    # ---- RESUME (se richiesto) ----
    use_lora_flag = bool(args.use_lora or args.use_qlora)
    model, optimizer, scheduler, global_step, start_epoch = load_checkpoint_if_any(
        model,
        args.resume_from if args.resume_from and args.resume_from != "latest" else (
            os.path.join(ckpt_dir, "latest") if args.resume_from == "latest" else None
        ),
        optimizer=optimizer,
        scheduler=scheduler,
        device=device,
        use_lora=use_lora_flag,
    )



    # ----- TensorBoard -----
    from torch.utils.tensorboard import SummaryWriter
    log_dir = args.log_dir or os.path.join(args.output_dir, "tblogs")
    os.makedirs(log_dir, exist_ok=True)
    writer = SummaryWriter(log_dir=log_dir)

    # ----- Training loop -----
    model.config.use_cache = False
    model.gradient_checkpointing_enable()

    model.train()
    global_step = 0
    optimizer.zero_grad(set_to_none=True)

    # prerequisiti prima del loop (una volta sola)
    use_lora_flag = bool(args.use_lora or args.use_qlora)
    ckpt_dir = args.checkpoint_dir or os.path.join(args.output_dir, "ckpts")
    os.makedirs(ckpt_dir, exist_ok=True)

    best_val = float("inf")
    bad_epochs = 0
    best_dir = os.path.join(args.output_dir, "best")
    os.makedirs(best_dir, exist_ok=True)

    # --------- TRAINING LOOP CORRETTO + CHECKPOINTING ----------
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch+1}/{args.epochs}")
        epoch_loss_sum, epoch_steps = 0.0, 0

        pbar = tqdm(train_loader, dynamic_ncols=True)
        for batch in pbar:
            # CPU -> GPU
            batch = move_to_device(batch, device)

            # dtype sicuro per la vision
            if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
                batch["pixel_values"] = batch["pixel_values"].to(torch.float32, non_blocking=True)

            # forward/backward
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()

            # logging per step
            writer.add_scalar("loss/train_step", loss.item(), global_step)
            epoch_loss_sum += loss.item()
            epoch_steps += 1

            do_step = ((global_step + 1) % args.gradient_accumulation_steps == 0)

            if do_step:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                writer.add_scalar("lr", scheduler.get_last_lr()[0], global_step + 1)

                # checkpoint per STEP (opzionale)
                if getattr(args, "save_every_steps", 0) > 0 and ((global_step + 1) % args.save_every_steps == 0):
                    tag = f"step_{global_step + 1:08d}"
                    save_checkpoint(tag, model, processor, optimizer, scheduler,
                                    global_step + 1, epoch, ckpt_dir, use_lora_flag)
                    _rotate_checkpoints(ckpt_dir, getattr(args, "keep_last_k", 0))

            if global_step % 10 == 0:
                pbar.set_description(f"step {global_step} | loss {loss.item():.4f}")

            global_step += 1

        # --- FLUSH FINALE: gestisce l'accumulation monca a fine epoca ---
        if (global_step % args.gradient_accumulation_steps) != 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            writer.add_scalar("lr", scheduler.get_last_lr()[0], global_step)

        # media epoch (train)
        if epoch_steps > 0:
            writer.add_scalar("loss/train_epoch", epoch_loss_sum / epoch_steps, epoch)

        # --- VALIDATION per epoca ---
        if (val_loader is not None) and ((epoch + 1) % args.val_every == 0):
            val_loss = evaluate(model, val_loader, device, writer, epoch)
            print(f"[VAL] epoch {epoch+1}: val_loss={val_loss:.4f}")

            # best checkpoint
            if val_loss < best_val:
                best_val = val_loss
                bad_epochs = 0
                model.save_pretrained(best_dir)
                processor.save_pretrained(best_dir)
                print(f"✓ Nuovo best salvato in {best_dir} (val_loss={best_val:.4f})")
            else:
                bad_epochs += 1
                if args.patience > 0 and bad_epochs >= args.patience:
                    print(f"Early stopping: nessun miglioramento per {bad_epochs} epoche.")
                    # salva un checkpoint finale di sicurezza prima di uscire
                    tag = f"epoch_{epoch+1:03d}_earlystop"
                    save_checkpoint(tag, model, processor, optimizer, scheduler,
                                    global_step, epoch + 1, ckpt_dir, use_lora_flag)
                    _rotate_checkpoints(ckpt_dir, getattr(args, "keep_last_k", 0))
                    break

        # checkpoint per EPOCA (opzionale)
        if getattr(args, "save_every_epochs", 0) > 0 and ((epoch + 1) % args.save_every_epochs == 0):
            tag = f"epoch_{epoch + 1:03d}"
            save_checkpoint(tag, model, processor, optimizer, scheduler,
                            global_step, epoch + 1, ckpt_dir, use_lora_flag)
            _rotate_checkpoints(ckpt_dir, getattr(args, "keep_last_k", 0))


    # ----- Salvataggio e chiusura -----
    os.makedirs(args.output_dir, exist_ok=True)
    model.save_pretrained(args.output_dir)
    processor.save_pretrained(args.output_dir)
    writer.close()
    print(f"Modello salvato in {args.output_dir}")



if __name__ == "__main__":
    main()

'''

python smolvlm2_train.py \
  --train_jsonl /home/battistini/exp/private_datasets/oxe_vlm_jsonl/train/data.jsonl \
  --val_jsonl   /home/battistini/exp/private_datasets/oxe_vlm_jsonl/val/data.jsonl \
  --output_dir  /home/battistini/exp/output_smolvlm2_lora \
  --log_dir     /home/battistini/exp/output_smolvlm2_lora/tblogs \
  --batch_size 1 --epochs 1 --gradient_accumulation_steps 8 \
  --use_lora

mkdir -p /home/battistini/exp/output_smolvlm2_lora

python vlm_ft/train/smolvlm2_train.py \
  --train_jsonl /home/battistini/exp/private_datasets/oxe_vlm_jsonl/train/data.jsonl \
  --val_jsonl   /home/battistini/exp/private_datasets/oxe_vlm_jsonl/val/data.jsonl \
  --output_dir  /home/battistini/exp/output_smolvlm2_lora \
  --log_dir     /home/battistini/exp/output_smolvlm2_lora/tblogs \
  --batch_size 1 --epochs 3 --lr 2e-4 --gradient_accumulation_steps 8 \
  --use_lora 2>&1 | tee /home/battistini/exp/output_smolvlm2_lora/train.log









DATA=/home/battistini/exp/private_datasets/oxe_vlm_jsonl
OUT=/home/battistini/exp/output_smolvlm2_lora
LOGDIR=$OUT/tblogs
mkdir -p "$OUT" "$LOGDIR"


tmux new -s vlm




python vlm_ft/train/smolvlm2_train.py \
  --train_jsonl "$DATA/train/data.jsonl" \
  --val_jsonl   "$DATA/val/data.jsonl" \
  --output_dir  "$OUT" \
  --log_dir     "$LOGDIR" \
  --batch_size 1 \
  --epochs 3 \
  --lr 2e-4 \
  --gradient_accumulation_steps 8 \
  --val_every 1 \
  --patience 2 \
  --use_lora 2>&1 | tee "$OUT/train.log"


# dentro tmux
tmux new-window -n tb
tensorboard --logdir "$LOGDIR" --port 6006 --bind_all
tensorboard --logdir /home/battistini/storage/oxe-bt-pipeline/output_smolvlm2_lora/tblogs             --port 6007 --bind_all --reload_interval 5

# inference usando il checkpoint
python inference.py \
  --adapter_dir "$OUT/best" \
  --video "/home/battistini/exp/private_datasets/val/videos/asu_table_top_converted_externally_to_rlds_0.1.0/episode_092/contact_video.mp4" \
  --prompt "Return only one BehaviorTree.CPP XML. No prose."

'''

