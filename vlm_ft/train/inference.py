#!/usr/bin/env python3
import argparse
import re
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel

DEFAULT_SYSTEM = (
    "You are a BehaviorTree.CPP code generator.\n"
    "CONSTRAINTS:\n"
    "- Output ONLY one BT.CPP XML tree (no prose, no comments, no markdown).\n"
    '- Format: <BehaviorTree ID="MainTree"> ... </BehaviorTree>\n'
    "- Close all tags. Use readable node names and ports only when meaningful."
)

def build_messages(system_text: str, prompt_text: str, video_path: str | None):
    content = [
        {"type": "text", "text": f"SYSTEM: {system_text}"},
        {"type": "text", "text": f"INSTRUCTION: {prompt_text}"},
    ]
    if video_path:
        content.append({"type": "video", "path": video_path})
    return [{"role": "user", "content": content}]

def parse_args():
    ap = argparse.ArgumentParser(description="SmolVLM2 inference (LoRA adapters o checkpoint merge).")
    ap.add_argument("--base_id", default="HuggingFaceTB/SmolVLM2-2.2B-Instruct",
                    help="Checkpoint base HuggingFace (usato con adapter LoRA).")
    ap.add_argument("--adapter_dir", default="",
                    help="Cartella con gli adapter LoRA addestrati. Se presente, usa base_id + adapter.")
    ap.add_argument("--merged_dir", default="",
                    help="Cartella di un checkpoint già mergiato (stand-alone). Alternativa a --adapter_dir.")
    ap.add_argument("--video", default="", help="Path assoluto al video (opzionale).")
    ap.add_argument("--system", default=DEFAULT_SYSTEM, help="Testo SYSTEM.")
    ap.add_argument("--prompt", required=True, help="Istruzione naturale. Metti 'Return only the XML.' ecc.")
    ap.add_argument("--max_new_tokens", type=int, default=512)
    args = ap.parse_args()

    if args.adapter_dir and args.merged_dir:
        raise SystemExit("Usa O --adapter_dir O --merged_dir, non entrambi.")
    return args

def main():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Caricamento processor e modello
    if args.merged_dir:
        processor = AutoProcessor.from_pretrained(args.merged_dir, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            args.merged_dir, trust_remote_code=True, device_map="auto", attn_implementation="eager"
        )
    else:
        processor = AutoProcessor.from_pretrained(args.adapter_dir or args.base_id, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            args.base_id, trust_remote_code=True, device_map="auto", attn_implementation="eager"
        )
        if args.adapter_dir:
            model = PeftModel.from_pretrained(model, args.adapter_dir)

    model.eval()
    model.config.use_cache = True

    # Costruzione messaggi coerente col training
    messages = build_messages(args.system, args.prompt, args.video or None)

    # Tokenizzazione con template chat; il processor gestisce anche il video
    batch = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True, return_tensors="pt", return_dict=True
    )

    # Sposta su device e normalizza dtype dei video
    for k, v in batch.items():
        if torch.is_tensor(v):
            batch[k] = v.to(device, non_blocking=True)
    if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
        # Conv2d della vision è sempre sicura in float32
        batch["pixel_values"] = batch["pixel_values"].to(torch.float32, non_blocking=True)

    # Generazione
    with torch.inference_mode():
        out = model.generate(
            **batch,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            repetition_penalty=1.05,
            eos_token_id=processor.tokenizer.eos_token_id,
            return_dict_in_generate=True,
        )

    # Decodifica SOLO la parte generata (assistant), non il prompt
    gen_ids = out.sequences
    prompt_len = batch["input_ids"].shape[1]
    assistant_ids = gen_ids[0][prompt_len:]
    text = processor.tokenizer.decode(assistant_ids, skip_special_tokens=True)

    # Estrai solo l'XML se presente
    m = re.search(r"<BehaviorTree[\\s\\S]*?</BehaviorTree>", text)
    print(m.group(0) if m else text)

if __name__ == "__main__":
    main()
