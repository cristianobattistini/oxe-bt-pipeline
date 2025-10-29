#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import sys
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText, LogitsProcessor, LogitsProcessorList # <-- CORRETTO IMPORT
from peft import PeftModel

DEFAULT_SYSTEM = (
    "You are a BehaviorTree.CPP code generator.\n"
    "CONSTRAINTS:\n"
    "- Output ONLY one BT.CPP XML tree (no prose, no comments, no markdown).\n"
    '- Format: <BehaviorTree ID="MainTree"> ... </BehaviorTree>\n'
    "- Close all tags. Use readable node names and ports only when meaningful."
)

class VDDLogitsProcessor(LogitsProcessor):
    """
    Applica il Visual Debias Decoding contrastando i logits con/senza video.
    Ref: https://arxiv.org/abs/2403.05262
    """
    def __init__(self, model, processor, bias_messages, alpha, device):
        self.model = model
        self.processor = processor
        self.bias_messages = bias_messages # Messaggi senza video
        self.alpha = alpha
        self.device = device
        self.eos_token_id = getattr(processor.tokenizer, "eos_token_id", None)

    @torch.inference_mode()
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        if self.alpha == 0:
            return scores

        # 1. Prepara l'input per il calcolo del bias (senza video)
        #    Usa gli stessi token generati finora (input_ids) ma con i messaggi originali senza video
        
        # Crea il batch di bias A PARTIRE dai messaggi senza video
        bias_batch = self.processor.apply_chat_template(
            self.bias_messages, add_generation_prompt=True, tokenize=True, return_tensors="pt", return_dict=True
        )
        
        # Trova la lunghezza del prompt di bias
        bias_prompt_len = bias_batch["input_ids"].shape[1]
        
        # Prendi i token generati dal 'vero' input_ids
        # NOTA: ASSUME che il prompt text-only sia lungo uguale! Questo potrebbe essere fragile.
        #       Una soluzione più robusta cercherebbe la fine del prompt effettivo in input_ids.
        generated_ids = input_ids[:, bias_prompt_len:] 
                                                       
        # Concatena prompt bias + token generati
        current_bias_input_ids = torch.cat([bias_batch["input_ids"].to(self.device), generated_ids], dim=1)
        
        # Crea l'attention mask per il bias input
        current_bias_attention_mask = torch.ones_like(current_bias_input_ids)


        # 2. Esegui il forward pass per ottenere i logits del bias
        bias_outputs = self.model(
            input_ids=current_bias_input_ids,
            attention_mask=current_bias_attention_mask,
            # pixel_values=None # Assicurati che non ci siano pixel_values
        )
        bias_logits = bias_outputs.logits[:, -1, :] # Logits solo per l'ULTIMO token

        # 3. Applica la formula VDD
        debiased_scores = (1 + self.alpha) * scores - self.alpha * bias_logits
        
        # Sicurezza: non penalizzare mai il token EOS se è il più probabile senza bias
        if self.eos_token_id is not None:
             # Controlla solo se ci sono token EOS nei top logits (più efficiente)
             top_indices = torch.topk(scores, k=5, dim=-1).indices
             if self.eos_token_id in top_indices[0]:
                 if torch.argmax(scores, dim=-1)[0] == self.eos_token_id:
                     debiased_scores[:, self.eos_token_id] = scores[:, self.eos_token_id].item() # Ripristina il logit EOS originale
        
        return debiased_scores


def build_messages(system_text: str, prompt_text: str, video_path: str | None):
    content = []
    # Aggiungi system prompt solo se non è vuoto
    if system_text and system_text.strip():
        content.append({"type": "text", "text": f"SYSTEM: {system_text}"})
    
    # Aggiungi video se presente PRIMA del prompt utente
    if video_path:
        content.append({"type": "video", "path": video_path})
        
    # Aggiungi prompt utente
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
    ap.add_argument("--video", default="", help="Path video di default (opzionale).")
    ap.add_argument("--system", default=DEFAULT_SYSTEM, help="Testo SYSTEM.")
    ap.add_argument("--prompt", help="Prompt per singolo run (se non usi --interactive).")
    ap.add_argument("--max_new_tokens", type=int, default=512, help="Token generati al massimo.")
    ap.add_argument("--vdd_alpha", type=float, default=0.0,
                    help="Forza del Visual Debias Decoding (0=disabilitato, es. 1.0). Molto più lento!")
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="Temperatura per il sampling (default: 1.0). Valori < 1 rendono l'output più deterministico.")
    ap.add_argument("--do_sample", action="store_true",
                    help="Abilita il sampling (necessario per temperature != 1.0). Default: False (greedy).")
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
    model.config.use_cache = True  # riduce latenza tra generazioni
    print(f"Modello caricato su: {model.device}")
    return device, processor, model


def generate_once(model, processor, device, system_text, prompt_text, video_path,
                  max_new_tokens=512, vdd_alpha=0.0, temperature=1.0, do_sample=False):

    messages = build_messages(system_text, prompt_text, video_path or None)
    try:
        batch = processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True, return_tensors="pt", return_dict=True
        )
    except Exception as e:
        print(f"\nErrore durante l'applicazione del chat template: {e}", file=sys.stderr)
        print("Controlla che il video esista e sia leggibile:", video_path, file=sys.stderr)
        return "[ERRORE TEMPLATE]"
        
    # move to device
    for k, v in batch.items():
        if torch.is_tensor(v):
            batch[k] = v.to(device, non_blocking=True)
    if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):

        # Usa il dtype corretto atteso dal modello
        model_dtype_config = getattr(model.config, "torch_dtype", torch.float32) # Prendi il valore dalla config

        # Converti la stringa (se necessario) in un oggetto torch.dtype
        if isinstance(model_dtype_config, str):
            if model_dtype_config == "float32":
                model_dtype = torch.float32
            elif model_dtype_config == "float16":
                model_dtype = torch.float16
            elif model_dtype_config == "bfloat16":
                model_dtype = torch.bfloat16
            else:
                # Fallback se la stringa non è riconosciuta
                print(f"Warning: Unrecognized torch_dtype string '{model_dtype_config}' in model config. Using float32.", file=sys.stderr)
                model_dtype = torch.float32
        elif isinstance(model_dtype_config, torch.dtype):
            model_dtype = model_dtype_config # Era già del tipo giusto
        else:
            # Fallback per tipi inaspettati
             print(f"Warning: Unexpected type for torch_dtype '{type(model_dtype_config)}' in model config. Using float32.", file=sys.stderr)
             model_dtype = torch.float32

        # Ora usa model_dtype, che è sicuramente un oggetto torch.dtype
        batch["pixel_values"] = batch["pixel_values"].to(model_dtype, non_blocking=True)

    logits_processor = LogitsProcessorList() # Sempre una lista

    # --- Logica VDD ---
    if vdd_alpha > 0:
        print(f"VDD attivo (alpha={vdd_alpha}). L'inferenza sarà molto più lenta.")
        # Crea i messaggi per il calcolo del bias (senza video)
        bias_messages = build_messages(system_text, prompt_text, video_path=None)
        vdd_processor = VDDLogitsProcessor(model, processor, bias_messages, vdd_alpha, device)
        logits_processor.append(vdd_processor)
    # --------------------

    with torch.inference_mode():
        eos_id = getattr(processor.tokenizer, "eos_token_id", None)
        pad_id = getattr(processor.tokenizer, "pad_token_id", eos_id) # Usa pad o eos

        # --- Parametri di Generazione Aggiornati ---
        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "temperature": temperature if do_sample and temperature > 0 else 1.0, # Temperatura > 0 e solo se do_sample=True
            "top_p": 0.9 if do_sample else None, # Aggiungi top_p per sampling più stabile
            "repetition_penalty": 1.05,
            "eos_token_id": eos_id,
            "pad_token_id": pad_id, # Importante per evitare warning
            "logits_processor": logits_processor if logits_processor else None, # Passa il processore VDD se attivo
            "return_dict_in_generate": True,
            "output_scores": False, # Non servono gli score qui
        }
        # ------------------------------------------
        
        try:
            out = model.generate(**batch, **generation_kwargs)
        except Exception as e:
            print(f"\nErrore durante la generazione: {e}", file=sys.stderr)
            if "CUDA out of memory" in str(e):
                 print("Memoria GPU esaurita. Riduci max_new_tokens o prova senza VDD.", file=sys.stderr)
            return "[ERRORE GENERAZIONE]"


    gen_ids = out.sequences
    prompt_len = batch["input_ids"].shape[1]
    # Gestisci caso in cui la generazione è vuota o solo padding/eos
    assistant_ids = gen_ids[0][prompt_len:]
    if assistant_ids.numel() == 0:
         return "[OUTPUT VUOTO]"
         
    # Decodifica escludendo token speciali
    text = processor.tokenizer.decode(assistant_ids, skip_special_tokens=True)
    
    # Estrazione XML (più robusta)
    m = re.search(r"<BehaviorTree\b[\s\S]*?</BehaviorTree>", text, re.IGNORECASE)
    return (m.group(0) if m else text).strip()


def run_single(args):
    if not args.prompt:
        raise SystemExit("Errore: serve --prompt (oppure usa --interactive).")
    device, processor, model = load_model_and_processor(args)
    xml = generate_once(
        model, processor, device,
        args.system, args.prompt, args.video or None,
        args.max_new_tokens, args.vdd_alpha, args.temperature, args.do_sample # <-- OK!
    )
    print(xml)


def run_repl(args):
    device, processor, model = load_model_and_processor(args)
    current_system = args.system
    current_video = args.video or None
    max_tokens = args.max_new_tokens
    vdd_alpha = args.vdd_alpha
    temperature = args.temperature
    do_sample = args.do_sample

    print("🔁 REPL SmolVLM2 — comandi: ::video PATH | ::system TXT | ::max INT | ::alpha F | ::temp F | ::sample B | ::show | ::quit")
    print(f"[video={current_video!r}] [max={max_tokens}] [alpha={vdd_alpha}] [temp={temperature}] [sample={do_sample}]")
    
    # --- AGGIUNTO try: mancante ---
    try:
        while True:
            try: # Gestisce input multi-linea con Ctrl+D o EOF improvviso
                prompt_lines = []
                print("\nprompt> ", end='', flush=True) # Stampa prompt senza newline
                while True:
                    line = sys.stdin.readline()
                    if not line: # EOF (Ctrl+D)
                        raise EOFError 
                    if line.strip() == "": # Invio vuoto termina input multi-linea
                        break
                    prompt_lines.append(line)
                prompt = "".join(prompt_lines).strip()
            except EOFError:
                 print("\nEOF ricevuto, uscita.")
                 break # Esce dal while True
            except KeyboardInterrupt:
                 print("\nInterruzione, uscita.")
                 break # Esce dal while True

            if not prompt:
                continue

            if prompt.startswith("::"):
                cmd, *rest = prompt[2:].split(" ", 1)
                arg = rest[0] if rest else ""
                cmd = cmd.lower() # Rendi case-insensitive

                if cmd == "quit":
                    break
                elif cmd == "video":
                    current_video = arg.strip() or None
                    print(f"OK: video default -> {current_video}")
                elif cmd == "system":
                    current_system = arg.strip() if arg else input("nuovo SYSTEM> ").strip()
                    print("OK: SYSTEM aggiornato.")
                elif cmd == "max":
                    try:
                        new_max = int(arg)
                        if new_max <= 0: raise ValueError("Max tokens deve essere > 0")
                        max_tokens = new_max
                        print(f"OK: max_new_tokens -> {max_tokens}")
                    except ValueError as e:
                        print(f"Valore intero non valido: {e}")                
                elif cmd == "alpha":
                    try:
                        new_alpha = float(arg)
                        if new_alpha < 0: raise ValueError("Alpha non può essere negativo")
                        vdd_alpha = new_alpha
                        print(f"OK: vdd_alpha -> {vdd_alpha}")
                    except ValueError as e:
                        print(f"Valore float non valido: {e}")
                elif cmd == "temp":
                    try:
                        new_temp = float(arg)
                        if new_temp <= 0: raise ValueError("Temperatura deve essere > 0")
                        temperature = new_temp
                        print(f"OK: temperature -> {temperature}")
                    except ValueError as e:
                        print(f"Valore float non valido: {e}")
                elif cmd == "sample":
                     if not arg: # Toggle se non viene dato argomento
                          do_sample = not do_sample
                     elif arg.lower() in ['true', '1', 'yes', 'on']:
                         do_sample = True
                     elif arg.lower() in ['false', '0', 'no', 'off']:
                         do_sample = False
                     else:
                         print("Usa True/False, 1/0, Yes/No, On/Off o nessun argomento per toggle.")
                     print(f"OK: do_sample -> {do_sample}")
                
                elif cmd == "show":
                    print(f"SYSTEM:\n{current_system}\nVIDEO: {current_video}\nMAX: {max_tokens}\nALPHA: {vdd_alpha}\nTEMP: {temperature}\nSAMPLE: {do_sample}")
                else:
                    print(f"Comando sconosciuto: '{cmd}'. Comandi disponibili: video, system, max, alpha, temp, sample, show, quit")
                continue # Torna al prompt senza generare

            # Genera (chiamata corretta)
            xml = generate_once(
                model, processor, device,
                current_system, prompt, current_video,
                max_tokens, vdd_alpha, temperature, do_sample
            )
            print("\n=== OUTPUT XML ===")
            print(xml)
            sys.stdout.flush()

            # (facoltativo) pulizia memoria temporanea tra run
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    # --- SPOSTATO FUORI DAL WHILE ---
    except (EOFError, KeyboardInterrupt):
        # Questo blocco viene raggiunto solo se l'input fallisce all'inizio o Ctrl+C/EOF fuori dal loop principale
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