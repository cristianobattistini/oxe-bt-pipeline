#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import random
import argparse
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# -------------------------------
# PROMPT: schema MINIMALE / varianti
# -------------------------------

SYS_PREFIX = (
    "SYSTEM: You are a BehaviorTree.CPP code generator.\n"
    "CONSTRAINTS:\n"
    "- Output ONLY one BT.CPP XML tree (no prose, no comments, no markdown).\n"
    '- Format: <BehaviorTree ID="MainTree"> ... </BehaviorTree>\n'
    "- Close all tags. Use readable node names and ports only when meaningful.\n"
)

TPL_MINIMAL = SYS_PREFIX + "\nINSTRUCTION: {task_instruction}\n\nReturn only the XML."
TPL_SUMMARY = SYS_PREFIX + "\nINSTRUCTION: {task_instruction}\nSUMMARY: {task_summary}\n\nReturn only the XML."
TPL_DOM = (
    SYS_PREFIX
    + "\nINSTRUCTION: {task_instruction}\nSUMMARY: {task_summary}\nDOMAIN: {dom_constraints}\n\nReturn only the XML."
)

def clip(txt: str, max_chars: int) -> str:
    txt = (txt or "").strip()
    return txt[:max_chars].rstrip()

def build_domain_constraints(meta: dict) -> str:
    allowed_nodes = meta.get("allowed_nodes") or []
    allowed_ports = meta.get("allowed_ports") or []
    naming = meta.get("naming_conventions", "")
    parts = []
    if allowed_nodes:
        parts.append("Allowed nodes: " + ", ".join(allowed_nodes) + ".")
    if allowed_ports:
        parts.append("Allowed ports: " + ", ".join(allowed_ports) + ".")
    if naming:
        parts.append(f"Naming: {naming}")
    return " ".join(parts) if parts else "None."

def prompt_minimal(meta: dict) -> str:
    return TPL_MINIMAL.format(task_instruction=clip(meta.get("task_instruction", ""), 200))

def prompt_summary(meta: dict) -> str:
    return TPL_SUMMARY.format(
        task_instruction=clip(meta.get("task_instruction", ""), 200),
        task_summary=clip(meta.get("task_summary", ""), 400),
    )

def prompt_dom(meta: dict) -> str:
    return TPL_DOM.format(
        task_instruction=clip(meta.get("task_instruction", ""), 200),
        task_summary=clip(meta.get("task_summary", ""), 400),
        dom_constraints=build_domain_constraints(meta),
    )

# -------------------------------
# Scansione episodi
# -------------------------------

def discover_episodes(root: Path) -> List[Tuple[str, Path]]:
    """
    Cerca episodi in due modalità:
      1) root/<dataset_name>/episode_*/  (preferita)
      2) root/episode_*/                  (fallback)
    Ritorna lista di (dataset_name, path_episode).
    """
    out: List[Tuple[str, Path]] = []
    found_any = False
    for ds_dir in sorted(root.iterdir()):
        if ds_dir.is_dir():
            eps = sorted([p for p in ds_dir.glob("episode_*") if p.is_dir()])
            if eps:
                found_any = True
                for ep in eps:
                    out.append((ds_dir.name, ep))
    if found_any:
        return out
    eps = sorted([p for p in root.glob("episode_*") if p.is_dir()])
    for ep in eps:
        out.append((root.name if root.name else "default", ep))
    return out

# -------------------------------
# Utilità XML / record
# -------------------------------

def safe_xml(xml_text: str) -> str:
    return xml_text.replace("\r\n", "\n").replace("\r", "\n").strip()

def make_records_for_episode(meta: dict, xml_text: str, mode: str, mix_ratio: str) -> List[Dict]:
    """
    Restituisce una lista di RECORD *logici* (prompt stringa + response stringa).
    La conversione al formato 'messages' avviene più avanti quando conosciamo il path del media.
    """
    if mode == "minimal":
        return [{"prompt": prompt_minimal(meta), "response": xml_text}]
    if mode == "summary":
        return [{"prompt": prompt_summary(meta), "response": xml_text}]
    a, b, c = [int(x) for x in mix_ratio.split(",")]
    recs = []
    recs += [{"prompt": prompt_minimal(meta), "response": xml_text}] * a
    recs += [{"prompt": prompt_summary(meta), "response": xml_text}] * b
    recs += [{"prompt": prompt_dom(meta),      "response": xml_text}] * c
    return recs

def split_prompt(prompt_text: str) -> Tuple[str, str]:
    if "\nINSTRUCTION:" in prompt_text:
        sys_part, instr_part = prompt_text.split("\nINSTRUCTION:", 1)
        sys_part = sys_part.strip()
        instr_part = ("INSTRUCTION:" + instr_part).strip()
    else:
        sys_part, instr_part = prompt_text, ""
    return sys_part, instr_part

def to_chat_record_video(prompt_text: str, xml_text: str, video_path: str,
                         dataset_id: str, episode_id: str) -> Dict:
    sys_part, instr_part = split_prompt(prompt_text)
    messages = [
        {"role": "user",
         "content": [
             {"type": "text", "text": sys_part},
             {"type": "text", "text": instr_part},
             {"type": "video", "path": video_path}
         ]},
        {"role": "assistant", "content": [{"type": "text", "text": xml_text}]}
    ]
    return {"messages": messages, "meta": {"dataset_id": dataset_id, "episode_id": episode_id}}

def to_chat_record_image(prompt_text: str, xml_text: str, image_path: str,
                         dataset_id: str, episode_id: str, local_id: str) -> Dict:
    """
    Versione per locals: inserisce un blocco 'image' al posto del video.
    """
    sys_part, instr_part = split_prompt(prompt_text)
    messages = [
        {"role": "user",
         "content": [
             {"type": "text", "text": sys_part},
             {"type": "text", "text": instr_part},
             {"type": "image", "path": image_path}
         ]},
        {"role": "assistant", "content": [{"type": "text", "text": xml_text}]}
    ]
    return {"messages": messages,
            "meta": {"dataset_id": dataset_id, "episode_id": episode_id, "local_id": local_id}}

# -------------------------------
# Helpers per LOCALS (immagine + subtree)
# -------------------------------

def discover_locals(ep_dir: Path, locals_dirname: str) -> List[Path]:
    """
    Ritorna la lista di cartelle local_* presenti in episode/locals/.
    """
    c = ep_dir / locals_dirname
    if not c.exists():
        return []
    return sorted([p for p in c.iterdir() if p.is_dir() and p.name.startswith("local_")])

def find_first_image(local_dir: Path, image_glob: str) -> Optional[Path]:
    imgs = sorted(list(local_dir.glob(image_glob)))
    if imgs:
        return imgs[0]
    # fallback: prova png/jpg generici
    for patt in ["*.jpg", "*.jpeg", "*.png"]:
        imgs = sorted(list(local_dir.glob(patt)))
        if imgs:
            return imgs[0]
    return None

# -------------------------------
# Pipeline principale
# -------------------------------

def main():
    ap = argparse.ArgumentParser("Build JSONL for SmolVLM FT from episodes (video) and locals (images)")
    # --- invariato: video ---
    ap.add_argument("--episodes_root", type=str, required=True,
                    help="Radice con i dataset che contengono episode_*")
    ap.add_argument("--out_root", type=str, required=True,
                    help="Cartella dove creare train/ e val/")
    ap.add_argument("--train_ratio", type=float, default=0.9)
    ap.add_argument("--shuffle_seed", type=int, default=42)
    ap.add_argument("--prompt_mode", type=str, default="minimal",
                    choices=["minimal", "summary", "mix"])
    ap.add_argument("--mix_ratio", type=str, default="8,2,1",
                    help="Per mode=mix: proporzioni minimal,summary,dom")
    ap.add_argument("--meta_filename", type=str, default="meta.json")
    ap.add_argument("--xml_filename", type=str, default="bt.xml")
    ap.add_argument("--video_filename", type=str, default="contact_video.mp4")
    ap.add_argument("--jsonl_name", type=str, default="data.jsonl")
    ap.add_argument("--videos_subdir", type=str, default="videos",
                    help="Sottocartella (dentro lo split) in cui copiare i video")
    ap.add_argument("--no-copy-video", action="store_true",
                    help="Non copiare i video; salva il path assoluto al file originale")
    ap.add_argument("--limit", type=int, default=0,
                    help="Processa solo i primi N episodi (debug)")

    # --- nuovo: locals (immagini) ---
    ap.add_argument("--enable-locals", action="store_true",
                    help="Se presente, genera anche il dataset images+BT per i locals")
    ap.add_argument("--locals-dirname", type=str, default="locals",
                    help="Nome directory dei locals dentro l'episodio")
    ap.add_argument("--local-xml-filename", type=str, default="subtree_.xml",
                    help="Nome del file XML del subtree locale")
    ap.add_argument("--local-prompt-filename", type=str, default="local_prompt.md",
                    help="Nome del file testo con l'istruzione specifica del local")
    ap.add_argument("--local-image-glob", type=str, default="frame_*.jpg",
                    help="Glob per l'immagine del local (es. frame_*.jpg)")
    ap.add_argument("--jsonl-name-locals", type=str, default="data_locals.jsonl",
                    help="Nome del JSONL per i locals (immagini)")
    ap.add_argument("--images-subdir", type=str, default="images",
                    help="Sottocartella (dentro lo split) per copiare le immagini")
    ap.add_argument("--no-copy-image", action="store_true",
                    help="Non copiare le immagini; salva path assoluti")

    args = ap.parse_args()

    episodes_root = Path(args.episodes_root).resolve()
    out_root = Path(args.out_root).resolve()
    train_dir = out_root / "train"
    val_dir = out_root / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    all_eps = discover_episodes(episodes_root)
    if not all_eps:
        raise SystemExit(f"Nessun episodio trovato sotto: {episodes_root}")

    random.Random(args.shuffle_seed).shuffle(all_eps)
    if args.limit > 0:
        all_eps = all_eps[:args.limit]

    n_train = max(0, int(len(all_eps) * args.train_ratio))
    train_eps = all_eps[:n_train]
    val_eps = all_eps[n_train:]

    # -------- VIDEO (invariato) --------
    def process_split_video(split_eps: List[Tuple[str, Path]], split_dir: Path):
        jsonl_path = split_dir / args.jsonl_name
        with jsonl_path.open("w", encoding="utf-8") as jf:
            for ds_name, ep_dir in split_eps:
                meta_path  = ep_dir / args.meta_filename
                xml_path   = ep_dir / args.xml_filename
                video_path = ep_dir / args.video_filename
                if not (meta_path.exists() and xml_path.exists() and video_path.exists()):
                    continue

                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    continue

                xml_text = safe_xml(xml_path.read_text(encoding="utf-8"))

                if args.no_copy_video:
                    video_field = str(video_path.resolve())
                else:
                    dest = split_dir / args.videos_subdir / ds_name / ep_dir.name / args.video_filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(video_path, dest)
                    video_field = str(dest.relative_to(split_dir))

                records = make_records_for_episode(meta, xml_text, args.prompt_mode, args.mix_ratio)
                for rec in records:
                    chat_rec = to_chat_record_video(
                        prompt_text=rec["prompt"],
                        xml_text=rec["response"],
                        video_path=video_field,
                        dataset_id=ds_name,
                        episode_id=ep_dir.name
                    )
                    jf.write(json.dumps(chat_rec, ensure_ascii=False) + "\n")

    process_split_video(train_eps, train_dir)
    process_split_video(val_eps, val_dir)

    # -------- LOCALS (nuovo, opzionale) --------
    def make_local_meta(base_meta: dict, local_prompt_text: Optional[str]) -> dict:
        """
        Costruisce un meta ad-hoc per il local:
        - se esiste local_prompt.md lo usa come task_instruction;
        - altrimenti usa base_meta.task_instruction con nota di focalizzazione locale.
        Manteniamo gli altri campi invariati per coerenza col mixing dei prompt.
        """
        m = dict(base_meta) if base_meta else {}
        if local_prompt_text and local_prompt_text.strip():
            m["task_instruction"] = local_prompt_text.strip()
        else:
            ti = (base_meta or {}).get("task_instruction", "")
            m["task_instruction"] = f"{ti}\nFocus only on the local subtask depicted in the image. Ignore video-specific details."
        return m

    def process_split_locals(split_eps: List[Tuple[str, Path]], split_dir: Path):
        if not args.enable_locals:
            return
        jsonl_path = split_dir / args.jsonl-name-locals if hasattr(args, "jsonl-name-locals") else split_dir / args.jsonl_name_locals  # safety for hyphen/underscore
        # gestisci attributo con underscore (nome effettivo argparse)
        jsonl_path = split_dir / getattr(args, "jsonl_name_locals")
        with jsonl_path.open("w", encoding="utf-8") as jf:
            for ds_name, ep_dir in split_eps:
                meta_path = ep_dir / args.meta_filename
                base_meta = {}
                if meta_path.exists():
                    try:
                        base_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        base_meta = {}

                # Scansiona locals
                for local_dir in discover_locals(ep_dir, args.locals_dirname):
                    local_id = local_dir.name  # es. local_1
                    xml_path  = local_dir / args.local_xml_filename
                    prompt_md = local_dir / args.local_prompt_filename
                    img_path  = find_first_image(local_dir, args.local_image_glob)

                    if not (xml_path.exists() and img_path and img_path.exists()):
                        continue

                    xml_text = safe_xml(xml_path.read_text(encoding="utf-8"))
                    local_prompt_text = prompt_md.read_text(encoding="utf-8") if prompt_md.exists() else None
                    meta = make_local_meta(base_meta, local_prompt_text)

                    # copia o referenzia immagine
                    if args.no_copy_image:
                        image_field = str(img_path.resolve())
                    else:
                        dest = split_dir / args.images_subdir / ds_name / ep_dir.name / local_id / img_path.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(img_path, dest)
                        image_field = str(dest.relative_to(split_dir))

                    # records come per i video, ma con blocco immagine
                    records = make_records_for_episode(meta, xml_text, args.prompt_mode, args.mix_ratio)
                    for rec in records:
                        chat_rec = to_chat_record_image(
                            prompt_text=rec["prompt"],
                            xml_text=rec["response"],
                            image_path=image_field,
                            dataset_id=ds_name,
                            episode_id=ep_dir.name,
                            local_id=local_id
                        )
                        jf.write(json.dumps(chat_rec, ensure_ascii=False) + "\n")

    process_split_locals(train_eps, train_dir)
    process_split_locals(val_eps, val_dir)

    print(f"Creati: {train_dir / args.jsonl_name}  e  {val_dir / args.jsonl_name}")
    if args.enable_locals:
        print(f"Creati locals: {train_dir / args.jsonl_name_locals}  e  {val_dir / args.jsonl_name_locals}")
    print(f"Esempio video: {train_dir / args.videos_subdir}")
    if args.enable_locals:
        print(f"Esempio images: {train_dir / args.images_subdir}")
    print("Schema record: {'messages': [...], 'meta': {...}}  con content: [{type:'text'|'video'|'image', ...}]")

if __name__ == "__main__":
    main()



'''
Generazione standard (copia i .mp4 nello split)

python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root dataset \
  --out_root private_datasets \
  --prompt_mode minimal


# Variante: non copiare i video (usa path assoluti)

python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root dataset \
  --out_root private_datasets \
  --prompt_mode minimal \
  --no-copy-video


# Variante: subset veloce per test
python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root dataset \
  --out_root private_datasets \
  --prompt_mode minimal \
  --train_ratio 0.8 \
  --limit 10


# Variante: mix di prompt (8 minimal, 2 summary, 1 dom)
python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root dataset \
  --out_root private_datasets \
  --prompt_mode mix \
  --mix_ratio 6,3,1


# dentro westworld

cd ~/storage/oxe-bt-pipeline

python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root ~/datasets/private/oxe_episodes \
  --out_root      ~/datasets/private/oxe_vlm_jsonl \
  --prompt_mode   minimal


  python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root dataset \
  --out_root private_datasets \
  --prompt_mode minimal

  # video + locals 
  python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root dataset \
  --out_root private_datasets \
  --prompt_mode mix --mix_ratio 6,3,1 \
  --enable-locals \
  --no-copy-video --no-copy-image


  python3 vlm_ft/tools/build_jsonl_from_episodes.py \
  --episodes_root dataset \
  --out_root private_datasets \
  --prompt_mode minimal \
  --enable-locals


  
    # video + locals 

'''
