#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import sys
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
                    help="Modello base HuggingFace (usato se non passi --merged_dir).")
    ap.add_argument("--adapter_dir", default="",
                    help="Cartella con adapter LoRA addestrati (opzionale).")
    ap.add_argument("--merged_dir", default="",
                    help="Cartella di un checkpoint MERGIATO stand-alone (alternativa ad --adapter_dir).")
    ap.add_argument("--video", default="", help="Path video di default (opzionale).")
    ap.add_argument("--system", default=DEFAULT_SYSTEM, help="Testo SYSTEM.")
    ap.add_argument("--prompt", help="Prompt per singolo run (se non usi --interactive).")
    ap.add_argument("--max_new_tokens", type=int, default=512, help="Token generati al massimo.")
    ap.add_argument("--interactive", action="store_true",
                    help="REPL: rimane in loop riusando il modello caricato una sola volta.")
    return ap.parse_args()

def load_model_and_processor(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.merged_dir:
        # Usa direttamente il checkpoint mergiato
        processor = AutoProcessor.from_pretrained(args.merged_dir, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            args.merged_dir, trust_remote_code=True, device_map="auto", attn_implementation="eager"
        )
    else:
        # Base (e opzionalmente adapter LoRA)
        processor = AutoProcessor.from_pretrained(args.adapter_dir or args.base_id, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            args.base_id, trust_remote_code=True, device_map="auto", attn_implementation="eager"
        )
        if args.adapter_dir:
            model = PeftModel.from_pretrained(model, args.adapter_dir)
    model.eval()
    model.config.use_cache = True  # riduce latenza tra generazioni
    return device, processor, model

def generate_once(model, processor, device, system_text, prompt_text, video_path, max_new_tokens=512):
    messages = build_messages(system_text, prompt_text, video_path or None)
    batch = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True, return_tensors="pt", return_dict=True
    )
    # move to device
    for k, v in batch.items():
        if torch.is_tensor(v):
            batch[k] = v.to(device, non_blocking=True)
    if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
        batch["pixel_values"] = batch["pixel_values"].to(torch.float32, non_blocking=True)

    with torch.inference_mode():
        eos_id = getattr(processor.tokenizer, "eos_token_id", None)
        out = model.generate(
            **batch,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            repetition_penalty=1.05,
            eos_token_id=eos_id,
            return_dict_in_generate=True,
        )

    # Decodifica SOLO la parte generata
    gen_ids = out.sequences
    prompt_len = batch["input_ids"].shape[1]
    assistant_ids = gen_ids[0][prompt_len:]
    text = processor.tokenizer.decode(assistant_ids, skip_special_tokens=True)

    # Estrai solo l'XML se presente
    m = re.search(r"<BehaviorTree[\s\S]*?</BehaviorTree>", text)
    return (m.group(0) if m else text).strip()

def run_single(args):
    if not args.prompt:
        raise SystemExit("Errore: serve --prompt (oppure usa --interactive).")
    device, processor, model = load_model_and_processor(args)
    xml = generate_once(model, processor, device, args.system, args.prompt, args.video or None, args.max_new_tokens)
    print(xml)

def run_repl(args):
    device, processor, model = load_model_and_processor(args)
    current_system = args.system
    current_video = args.video or None
    max_tokens = args.max_new_tokens

    print("🔁 REPL SmolVLM2 — comandi: ::video PATH  |  ::system TESTO  |  ::max INT  |  ::show  |  ::quit")
    print(f"[video default={current_video!r}] [max_new_tokens={max_tokens}]")
    try:
        while True:
            prompt = input("\nprompt> ").strip()
            if not prompt:
                continue
            if prompt.startswith("::"):
                cmd, *rest = prompt[2:].split(" ", 1)
                arg = rest[0] if rest else ""
                if cmd == "quit":
                    break
                elif cmd == "video":
                    current_video = arg or None
                    print(f"OK: video default -> {current_video}")
                elif cmd == "system":
                    current_system = arg if arg else input("nuovo SYSTEM> ")
                    print("OK: SYSTEM aggiornato.")
                elif cmd == "max":
                    try:
                        max_tokens = int(arg)
                        print(f"OK: max_new_tokens -> {max_tokens}")
                    except ValueError:
                        print("Valore non valido.")
                elif cmd == "show":
                    print(f"SYSTEM:\n{current_system}\nVIDEO: {current_video}\nMAX: {max_tokens}")
                else:
                    print("Comando sconosciuto.")
                continue

            # Genera
            xml = generate_once(model, processor, device, current_system, prompt, current_video, max_tokens)
            print("\n=== OUTPUT XML ===")
            print(xml)
            sys.stdout.flush()

            # (facoltativo) pulizia memoria temporanea tra run
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    except (EOFError, KeyboardInterrupt):
        pass
    print("\nBye 👋")

def main():
    args = parse_args()
    if args.adapter_dir and args.merged_dir:
        raise SystemExit("Usa O --adapter_dir O --merged_dir, non entrambi.")

    if args.interactive:
        run_repl(args)     # loop interattivo
    else:
        run_single(args)   # comportamento singolo run (come prima)

if __name__ == "__main__":
    main()
