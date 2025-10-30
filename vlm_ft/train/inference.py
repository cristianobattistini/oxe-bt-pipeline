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

def build_messages(system_text: str, prompt_text: str, video_path: str | None, image_path: str | None):
    """
    Costruisce i messaggi per il processor:
    - Inserisce il SYSTEM (testo)
    - Inserisce opzionalmente un media: video OPPURE immagine (mutuamente esclusivi)
    - Inserisce il prompt utente (testo)
    """
    if video_path and image_path:
        raise ValueError("Fornisci solo uno tra 'video' e 'image', non entrambi.")

    content = []
    if system_text and system_text.strip():
        content.append({"type": "text", "text": f"SYSTEM: {system_text}"})

    if video_path:
        content.append({"type": "video", "path": video_path})
    elif image_path:
        # Per coerenza con il video, usiamo il campo 'path' anche per l'immagine
        content.append({"type": "image", "path": image_path})

    content.append({"type": "text", "text": f"INSTRUCTION: {prompt_text}"})
    return [{"role": "user", "content": content}]


def parse_args():
    ap = argparse.ArgumentParser(description="SmolVLM2 inference (LoRA adapters o checkpoint merge).")
    ap.add_argument("--base_id", default="HuggingFaceTB/SmolVLM2-2.2B-Instruct",
                    help="Modello base HuggingFace (usato se non passi --merged_dir).")
    ap.add_argument("--adapter_dir", default="",
                    help="Cartella con adapter LoRA addestrati (opzionale).")
    ap.add_argument("--merged_dir", default="",
                    help="Cartella di un checkpoint MERGIATO stand-alone (alternativa ad --adapter_dir).")

    # Media di default per run singola o REPL
    ap.add_argument("--video", default="", help="Path video di default (opzionale).")
    ap.add_argument("--image", default="", help="Path immagine di default (opzionale).")

    ap.add_argument("--system", default=DEFAULT_SYSTEM, help="Testo SYSTEM.")
    ap.add_argument("--prompt", help="Prompt per singolo run (se non usi --interactive).")
    ap.add_argument("--max_new_tokens", type=int, default=512, help="Token generati al massimo.")

    # Sampling (nessun VDD: rimosso)
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="Temperatura per il sampling (default: 1.0). Valori < 1 rendono l'output più deterministico.")
    ap.add_argument("--do_sample", action="store_true",
                    help="Abilita il sampling (necessario per temperature != 1.0). Default: greedy.")

    ap.add_argument("--interactive", action="store_true",
                    help="REPL: rimane in loop riusando il modello caricato una sola volta.")
    return ap.parse_args()


def load_model_and_processor(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    load_path = args.merged_dir or args.adapter_dir or args.base_id

    try:
        processor = AutoProcessor.from_pretrained(load_path, trust_remote_code=True)
    except ValueError as e:
        print(f"Errore caricando il processor da '{load_path}': {e}", file=sys.stderr)
        print("Assicurati che la cartella contenga i file del processor (tokenizer.json, processor_config.json, ecc.).", file=sys.stderr)
        if args.adapter_dir and not args.merged_dir:
            print("Se usi --adapter_dir, prova a copiare i file *.json, *.txt, *.md dalla cartella 'best' o dal modello base.", file=sys.stderr)
        raise SystemExit(1)

    if args.merged_dir:
        print(f"Caricamento modello MERGIATO da: {args.merged_dir}")
        model = AutoModelForImageTextToText.from_pretrained(
            args.merged_dir, trust_remote_code=True, device_map="auto", attn_implementation="eager"
        )
    else:
        print(f"Caricamento modello BASE da: {args.base_id}")
        model = AutoModelForImageTextToText.from_pretrained(
            args.base_id, trust_remote_code=True, device_map="auto", attn_implementation="eager"
        )
        if args.adapter_dir:
            print(f"Applicazione ADAPTER da: {args.adapter_dir}")
            try:
                model = PeftModel.from_pretrained(model, args.adapter_dir)
            except Exception as e:
                print(f"Errore caricando l'adapter da '{args.adapter_dir}': {e}", file=sys.stderr)
                print("Assicurati che la cartella contenga i file dell'adapter (adapter_model.*, adapter_config.json).", file=sys.stderr)
                raise SystemExit(1)

    model.eval()
    model.config.use_cache = True
    print(f"Modello caricato su: {model.device}")
    return device, processor, model


def _move_batch_to_device_and_cast(batch: dict, model):
    """Sposta i tensori su device e imposta il dtype dei pixel in accordo alla config del modello."""
    device = next(model.parameters()).device
    for k, v in list(batch.items()):
        if torch.is_tensor(v):
            batch[k] = v.to(device, non_blocking=True)

    if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
        model_dtype_config = getattr(model.config, "torch_dtype", torch.float32)
        if isinstance(model_dtype_config, str):
            if model_dtype_config == "float32":
                model_dtype = torch.float32
            elif model_dtype_config == "float16":
                model_dtype = torch.float16
            elif model_dtype_config == "bfloat16":
                model_dtype = torch.bfloat16
            else:
                print(f"Warning: dtype string sconosciuto '{model_dtype_config}', uso float32.", file=sys.stderr)
                model_dtype = torch.float32
        elif isinstance(model_dtype_config, torch.dtype):
            model_dtype = model_dtype_config
        else:
            print(f"Warning: tipo inatteso per torch_dtype '{type(model_dtype_config)}', uso float32.", file=sys.stderr)
            model_dtype = torch.float32

        batch["pixel_values"] = batch["pixel_values"].to(model_dtype, non_blocking=True)

    return batch


def generate_once(model, processor, device, system_text, prompt_text, video_path, image_path,
                  max_new_tokens=512, temperature=1.0, do_sample=False):

    try:
        messages = build_messages(system_text, prompt_text, video_path or None, image_path or None)
        batch = processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True, return_tensors="pt", return_dict=True
        )
    except Exception as e:
        print(f"\nErrore durante la preparazione input: {e}", file=sys.stderr)
        print("Controlla che il media esista e sia leggibile. Video:", video_path, "Immagine:", image_path, file=sys.stderr)
        return "[ERRORE TEMPLATE]"

    batch = _move_batch_to_device_and_cast(batch, model)

    with torch.inference_mode():
        eos_id = getattr(processor.tokenizer, "eos_token_id", None)
        pad_id = getattr(processor.tokenizer, "pad_token_id", eos_id)

        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "temperature": temperature if do_sample and temperature > 0 else 1.0,
            "top_p": 0.9 if do_sample else None,
            "repetition_penalty": 1.05,
            "eos_token_id": eos_id,
            "pad_token_id": pad_id,
            "return_dict_in_generate": True,
            "output_scores": False,
        }

        try:
            out = model.generate(**batch, **{k: v for k, v in generation_kwargs.items() if v is not None})
        except Exception as e:
            print(f"\nErrore durante la generazione: {e}", file=sys.stderr)
            if "CUDA out of memory" in str(e):
                print("Memoria GPU esaurita. Riduci max_new_tokens o disabilita sampling.", file=sys.stderr)
            return "[ERRORE GENERAZIONE]"

    gen_ids = out.sequences
    prompt_len = batch["input_ids"].shape[1]
    assistant_ids = gen_ids[0][prompt_len:]
    if assistant_ids.numel() == 0:
        return "[OUTPUT VUOTO]"

    text = processor.tokenizer.decode(assistant_ids, skip_special_tokens=True)
    m = re.search(r"<BehaviorTree\b[\s\S]*?</BehaviorTree>", text, re.IGNORECASE)
    return (m.group(0) if m else text).strip()


def run_single(args):
    if not args.prompt:
        raise SystemExit("Errore: serve --prompt (oppure usa --interactive).")
    if args.video and args.image:
        raise SystemExit("Errore: fornisci SOLO uno tra --video e --image.")
    device, processor, model = load_model_and_processor(args)
    xml = generate_once(
        model, processor, device,
        args.system, args.prompt, args.video or None, args.image or None,
        args.max_new_tokens, args.temperature, args.do_sample
    )
    print(xml)


def run_repl(args):
    device, processor, model = load_model_and_processor(args)
    current_system = args.system
    current_video = args.video or None
    current_image = args.image or None
    max_tokens = args.max_new_tokens
    temperature = args.temperature
    do_sample = args.do_sample

    print("REPL SmolVLM2 — comandi: ::video PATH | ::image PATH | ::system TXT | ::max INT | ::temp F | ::sample B | ::show | ::clear | ::quit")
    print(f"[video={current_video!r}] [image={current_image!r}] [max={max_tokens}] [temp={temperature}] [sample={do_sample}]")

    try:
        while True:
            try:
                prompt_lines = []
                print("\nprompt> ", end='', flush=True)
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        raise EOFError
                    if line.strip() == "":
                        break
                    prompt_lines.append(line)
                prompt = "".join(prompt_lines).strip()
            except EOFError:
                print("\nEOF ricevuto, uscita.")
                break
            except KeyboardInterrupt:
                print("\nInterruzione, uscita.")
                break

            if not prompt:
                continue

            if prompt.startswith("::"):
                cmd, *rest = prompt[2:].split(" ", 1)
                arg = (rest[0] if rest else "").strip()
                cmd = cmd.lower()

                if cmd == "quit":
                    break
                elif cmd == "video":
                    current_video = arg or None
                    if current_video:
                        current_image = None  # media mutuamente esclusivi
                    print(f"OK: video default -> {current_video}")
                elif cmd == "image":
                    current_image = arg or None
                    if current_image:
                        current_video = None
                    print(f"OK: image default -> {current_image}")
                elif cmd == "system":
                    current_system = arg if arg else input("nuovo SYSTEM> ").strip()
                    print("OK: SYSTEM aggiornato.")
                elif cmd == "max":
                    try:
                        new_max = int(arg)
                        if new_max <= 0:
                            raise ValueError("Max tokens deve essere > 0")
                        max_tokens = new_max
                        print(f"OK: max_new_tokens -> {max_tokens}")
                    except ValueError as e:
                        print(f"Valore intero non valido: {e}")
                elif cmd == "temp":
                    try:
                        new_temp = float(arg)
                        if new_temp <= 0:
                            raise ValueError("Temperatura deve essere > 0")
                        temperature = new_temp
                        print(f"OK: temperature -> {temperature}")
                    except ValueError as e:
                        print(f"Valore float non valido: {e}")
                elif cmd == "sample":
                    if not arg:
                        do_sample = not do_sample
                    elif arg.lower() in ['true', '1', 'yes', 'on']:
                        do_sample = True
                    elif arg.lower() in ['false', '0', 'no', 'off']:
                        do_sample = False
                    else:
                        print("Usa True/False, 1/0, Yes/No, On/Off o nessun argomento per toggle.")
                    print(f"OK: do_sample -> {do_sample}")
                elif cmd == "show":
                    print(f"SYSTEM:\n{current_system}\nVIDEO: {current_video}\nIMAGE: {current_image}\nMAX: {max_tokens}\nTEMP: {temperature}\nSAMPLE: {do_sample}")
                elif cmd == "clear":
                    current_video = None
                    current_image = None
                    print("OK: media di default azzerati (video/image).")
                else:
                    print(f"Comando sconosciuto: '{cmd}'. Comandi: video, image, system, max, temp, sample, show, clear, quit")
                continue

            xml = generate_once(
                model, processor, device,
                current_system, prompt, current_video, current_image,
                max_tokens, temperature, do_sample
            )
            print("\n=== OUTPUT XML ===")
            print(xml)
            sys.stdout.flush()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    except (EOFError, KeyboardInterrupt):
        pass

    print("\nChiusura.")


def main():
    args = parse_args()
    if args.adapter_dir and args.merged_dir:
        raise SystemExit("Usa O --adapter_dir O --merged_dir, non entrambi.")

    if args.video and args.image and not args.interactive:
        raise SystemExit("Fornisci SOLO uno tra --video e --image.")

    if args.interactive:
        run_repl(args)
    else:
        run_single(args)

if __name__ == "__main__":
    main()


'''

python inference.py \
  --adapter_dir /path/to/adapters/best \
  --image /path/to/frame.jpg \
  --prompt "INSTRUCTION: pick up the bread and place it on the plate" \
  --max_new_tokens 512

  python inference.py \
  --merged_dir /path/to/merged_ckpt \
  --video /path/to/episode_099/contact_video.mp4 \
  --prompt "INSTRUCTION: put down the bread on the table, then retreat" \
  --do_sample --temperature 0.8

  
  python inference.py --adapter_dir /path/to/adapters/best --interactive
# dentro il REPL:
::image /path/to/frame.jpg
# scrivi il prompt, invio vuoto per eseguire

'''