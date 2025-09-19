#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generatore struttura dataset + prompt locali in due passaggi.

USO TIPICO
1) Inizializza struttura episodio:
   python generate_folders.py --mode init --out-root out --dest-root dataset --prompt-src prompts/prompt_full.md

2) Popola i prompt locali con GLOBAL_BT, NODE_LIBRARY, descrizione e COPIA i frame top-K:
   python generate_folders.py --mode locals --dest-root dataset --node-lib library/node_library_v_01.json

NOTE
- In --mode locals, per ciascun local_{1..3} tenta di copiare il relativo frame da:
  out/<DATASET_ID>/<EPISODE_ID>/final_selected/sampled_frames/frame_XX.{jpg,jpeg,png}
- Non sovrascrive file esistenti senza --overwrite.
"""

import argparse
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

# -------------------- Pattern per compilare prompt globale --------------------

PROMPT_LINE_PATTERNS = {
    "TASK INSTRUCTION": re.compile(r'^(\s*-\s*TASK INSTRUCTION:\s*)".*?"\s*$', re.IGNORECASE),
    "DATASET_ID":       re.compile(r'^(\s*-\s*DATASET_ID:\s*)".*?"\s*$', re.IGNORECASE),
    "EPISODE_ID":       re.compile(r'^(\s*-\s*EPISODE_ID:\s*)".*?"\s*$', re.IGNORECASE),
}

# -------------------- Skeleton minimi --------------------

BT_XML_SKELETON = """<BehaviorTree ID="MainTree">
  <Sequence>
    <!-- TODO: fill with valid nodes from node_library -->
  </Sequence>
</BehaviorTree>
"""

SUBTREE_XML_SKELETON = """<BehaviorTree ID="MainTree">
  <Sequence name="LocalSubtask">
    <!-- perceive / align / act / verify -->
  </Sequence>
</BehaviorTree>
"""

SUBTREE_JSON_SKELETON = """{
  "frame_index": null,
  "local_intent": "",
  "assumptions": "",
  "bb_read": [],
  "bb_write": [],
  "coherence_with_global": "",
  "format_checks": { "only_known_nodes": true, "only_binned_values": true }
}
"""

LOCAL_PROMPT_TEMPLATE = """SYSTEM (role: senior BT engineer)
You generate BehaviorTree.CPP v3 XML subtrees that are locally consistent with a given GLOBAL BT.
Follow STRICT RULES. Print exactly two code blocks: (1) XML subtree, (2) JSON metadata.

INPUTS
- NODE_LIBRARY (authoritative; use only these node IDs, ports, and port_value_spaces):
{NODE_LIBRARY}

- GLOBAL_BT (authoritative structure, do not modify here):
{GLOBAL_BT}

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{GLOBAL_DESCRIPTION}

- FRAME (single image; indexing is authoritative):
frame_index: {FRAME_INDEX}
frame_name: "{FRAME_NAME}"
frame_ranking_hint: {FRAME_RANK_HINT}

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{LOCAL_ANNOTATION}

- REPLACEMENT_TARGET (where the subtree will plug):
{REPLACEMENT_TARGET}

STRICT RULES
1) Output (1) must be BehaviorTree.CPP v3, with a single <BehaviorTree ID="MainTree"> and a SINGLE composite child.
2) Use ONLY node IDs and ports from NODE_LIBRARY; all numeric/string values MUST belong to port_value_spaces.
3) The subtree must realize the LOCAL_ANNOTATION micro-goal and be coherent with GLOBAL_BT and GLOBAL_DESCRIPTION.
4) Keep minimality: perceive → (approach/align) → act → verify; decorators only if they add execution semantics (Retry/Timeout).
5) Do not invent blackboard keys not implied by NODE_LIBRARY or GLOBAL_BT.
6) No comments, no extra tags, no prose inside XML.

REQUIRED OUTPUT

(1) XML subtree
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="LocalSubtask">
      <!-- minimal, binned, library-only -->
    </Sequence>
  </BehaviorTree>
</root>

(2) JSON metadata
{{
  "frame_index": {FRAME_INDEX},
  "local_intent": "",
  "plugs_into": {{ "path_from_root": ["MainTree"], "mode": "replace-only" }},
  "bb_read": [],
  "bb_write": [],
  "assumptions": [],
  "coherence_with_global": "",
  "format_checks": {{
    "single_root_composite": true,
    "decorators_single_child": true,
    "only_known_nodes": true,
    "only_binned_values": true
  }}
}}
"""

LOCAL_ANNOTATION_SKELETON = """{
  "frame": "frame_<k>",
  "phase": "<perceive|approach|align|act|verify|retreat>",
  "active_leaf": {"id": "<leaf_id_from_library>", "attrs": {}},
  "active_path_ids": ["MainTree"],
  "lookahead_hint": {"next_phase": "<phase>", "next_leaf_id": null, "reason": "<visual cue>"}
}"""

REPLACEMENT_TARGET_SKELETON = """{
  "path_from_root": ["MainTree"],
  "semantics": "replace-only"
}"""

# -------------------- Utility I/O --------------------

def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def write_safe(path: Path, content: str, overwrite: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    path.write_text(content, encoding="utf-8")
    return True

def copy_safe(src: Path, dst: Path, overwrite: bool) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not overwrite:
        return False
    shutil.copy2(src, dst)
    return True

def indent_block(text: str, indent_spaces: int) -> str:
    pad = " " * indent_spaces
    lines = text.splitlines()
    return "\n".join(pad + l for l in lines)

# -------------------- Prompt globale (init) --------------------

def load_prompt_template(prompt_src: Path) -> str:
    if not prompt_src.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_src}")
    return prompt_src.read_text(encoding="utf-8")

def fill_prompt(template: str, instruction: str, dataset_id: str, episode_id: str) -> str:
    instr_clean = instruction.replace('\n', ' ').strip()
    lines = template.splitlines()

    def replace_line(lines, pat_key, value):
        pat = PROMPT_LINE_PATTERNS[pat_key]
        for i, line in enumerate(lines):
            if pat.match(line):
                lines[i] = pat.sub(rf'\1"{value}"', line)
                return True
        return False

    found_instr = replace_line(lines, "TASK INSTRUCTION", instr_clean)
    found_ds    = replace_line(lines, "DATASET_ID", dataset_id)
    found_ep    = replace_line(lines, "EPISODE_ID", episode_id)

    if not (found_instr and found_ds and found_ep):
        try:
            idx = next(i for i, l in enumerate(lines) if "INPUTS" in l)
            inject = [
                f'- TASK INSTRUCTION: "{instr_clean}"',
                f'- DATASET_ID: "{dataset_id}"',
                f'- EPISODE_ID: "{episode_id}"',
            ]
            lines[idx+1:idx+1] = inject
        except StopIteration:
            lines += [
                "",
                "INPUTS (auto-filled fallback):",
                f'- TASK INSTRUCTION: "{instr_clean}"',
                f'- DATASET_ID: "{dataset_id}"',
                f'- EPISODE_ID: "{episode_id}"',
            ]
    out = "\n".join(lines)
    if not out.endswith("\n"):
        out += "\n"
    return out

# -------------------- Lettura dati episodio --------------------

def read_instruction(ep_out_dir: Path) -> str:
    instr_file = ep_out_dir / "instruction.txt"
    return instr_file.read_text(encoding="utf-8").strip() if instr_file.exists() else ""

def parse_meta(meta_path: Path) -> dict:
    try:
        return json.loads(load_text(meta_path))
    except Exception:
        return {}

def guess_task_long_description(meta_path: Path) -> str:
    try:
        meta = json.loads(load_text(meta_path))
        tld = meta.get("task_long_description")
        if tld:
            return json.dumps(tld, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return json.dumps({
        "overview": "",
        "preconditions": [],
        "stepwise_plan": [],
        "success_criteria": [],
        "failure_and_recovery": [],
        "termination": ""
    }, indent=2)

# -------------------- Frame helpers --------------------

def frame_id_to_index(frame_id: Optional[str]) -> Optional[int]:
    if not frame_id:
        return None
    m = re.match(r"^frame_(\d+)$", frame_id.strip())
    return int(m.group(1)) if m else None

def find_frame_file(out_root_for_ep: Path, frame_id: str) -> Optional[Path]:
    """
    Cerca il file immagine del frame dentro:
      <out_ds_ep>/final_selected/sampled_frames/frame_XX.{jpg,jpeg,png}
    Restituisce il Path se trovato, altrimenti None.
    """
    idx = frame_id_to_index(frame_id)
    if idx is None:
        return None
    d = out_root_for_ep / "final_selected" / "sampled_frames"
    if not d.exists():
        return None
    names = [f"frame_{idx:02d}", f"frame_{idx}"]
    exts  = [".jpg", ".jpeg", ".png"]
    for n in names:
        for e in exts:
            p = d / f"{n}{e}"
            if p.exists():
                return p
    # fallback: qualsiasi estensione
    for n in names:
        for p in d.glob(f"{n}.*"):
            if p.is_file():
                return p
    return None

def pick_top_k_frames(meta: dict, k: int = 3) -> list[str]:
    order = (meta.get("frame_ranking") or {}).get("order") or []
    return order[:k]

def get_frame_score(meta: dict, frame_id: Optional[str]):
    if not frame_id:
        return None
    scores = (meta.get("frame_ranking") or {}).get("scores") or {}
    return scores.get(frame_id)

def get_local_annotation(meta: dict, frame_id: Optional[str]) -> Optional[dict]:
    if not frame_id:
        return None
    anns = meta.get("local_annotations") or []
    for a in anns:
        if a.get("frame") == frame_id:
            return a
    return None

# -------------------- Copie file episode --------------------

def copy_contact_sheet(ep_out_dir: Path, ep_dest: Path, overwrite: bool) -> bool:
    src_dir = ep_out_dir / "final_selected"
    if not src_dir.exists():
        return False
    candidates = ["episode.jpeg", "episode.jpg", "contact_sheet.jpg", "contact_sheet.jpeg", "contact_sheet.png"]
    src = next((src_dir / c for c in candidates if (src_dir / c).exists()), None)
    if src is None:
        return False
    dst = ep_dest / f"contact_sheet{src.suffix.lower()}"
    return copy_safe(src, dst, overwrite)

def ensure_locals_structure(ep_dest: Path, overwrite: bool) -> int:
    created = 0
    locals_root = ep_dest / "locals"
    for i in range(1, 4):
        ld = locals_root / f"local_{i}"
        ld.mkdir(parents=True, exist_ok=True)
        xml_p = ld / "subtree_.xml"
        json_p = ld / "subtree_.json"
        if write_safe(xml_p, SUBTREE_XML_SKELETON, overwrite): created += 1
        if write_safe(json_p, SUBTREE_JSON_SKELETON, overwrite): created += 1
    return created

# -------------------- Modalità INIT --------------------

def init_mode(out_root: Path, dest_root: Path, prompt_src: Path, prompt_name: str, overwrite: bool, dry_run: bool):
    prompt_template = load_prompt_template(prompt_src)
    created = skipped = 0
    now = datetime.now().isoformat(timespec="seconds")

    for ds_dir in sorted([p for p in out_root.iterdir() if p.is_dir()]):
        dataset_id = ds_dir.name
        for ep_dir in sorted([p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]):
            episode_id = ep_dir.name
            ep_dest = dest_root / dataset_id / episode_id

            instruction = read_instruction(ep_dir)
            bt_path   = ep_dest / "bt.xml"
            meta_path = ep_dest / "meta.json"
            prm_path  = ep_dest / prompt_name

            prompt_filled = fill_prompt(prompt_template, instruction, dataset_id, episode_id)
            meta = {
                "dataset_id": dataset_id,
                "episode_id": episode_id,
                "created_at": now,
                "instruction": instruction,
                "sources": {
                    "frames_dir": str(ep_dir.resolve()),
                    "prompt_template": str(prompt_src.resolve())
                },
                "notes": "Fill after model generation."
            }
            meta_json = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"

            if dry_run:
                print(f"[DRY] {dataset_id}/{episode_id} -> ensure bt.xml, meta.json, {prompt_name}, contact_sheet, locals/")
                continue

            wrote_any = False
            wrote_any |= write_safe(bt_path, BT_XML_SKELETON, overwrite)
            wrote_any |= write_safe(meta_path, meta_json, overwrite)
            wrote_any |= write_safe(prm_path, prompt_filled, overwrite)
            cs_ok = copy_contact_sheet(ep_dir, ep_dest, overwrite)
            locals_created = ensure_locals_structure(ep_dest, overwrite)
            wrote_any |= cs_ok or (locals_created > 0)

            if wrote_any:
                created += 1
                print(f"[OK]  {dataset_id}/{episode_id} → files ensured (locals:{locals_created}, sheet:{'yes' if cs_ok else 'no'})")
            else:
                skipped += 1
                print(f"[SKIP] {dataset_id}/{episode_id} (already present; use --overwrite to regenerate)")

    print(f"\nInit done. Episodes processed: {created + skipped} | created/updated: {created} | fully skipped: {skipped}")

# -------------------- Modalità LOCALS --------------------

def locals_mode(project_root: Path, dest_root: Path, node_lib_path: Path, overwrite: bool, dry_run: bool):
    if not node_lib_path or not node_lib_path.exists():
        raise FileNotFoundError("--node-lib è obbligatorio in --mode locals e deve esistere.")
    node_lib_text = load_text(node_lib_path)

    created = skipped = 0
    for ds_dir in sorted([p for p in dest_root.iterdir() if p.is_dir()]):
        dataset_id = ds_dir.name
        for ep_dir in sorted([p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]):
            episode_id = ep_dir.name

            bt_path   = ep_dir / "bt.xml"
            meta_path = ep_dir / "meta.json"
            if not bt_path.exists():
                print(f"[WARN] bt.xml mancante: {bt_path}. Salto locals per questo episodio.")
                continue

            bt_text  = load_text(bt_path)
            bt_full  = ep_dir / "bt_full.xml"
            write_safe(bt_full, bt_text, overwrite=False)

            meta = parse_meta(meta_path) if meta_path.exists() else {}
            tld_text = guess_task_long_description(meta_path) if meta_path.exists() else guess_task_long_description(meta_path)

            # Cartella out/<ds>/<ep> per risalire ai frame reali
            out_ep = project_root / "out" / dataset_id / episode_id

            locals_root = ep_dir / "locals"
            if not locals_root.exists():
                print(f"[WARN] locals/ mancante in {ep_dir}. Eseguire prima --mode init.")
                continue

            # Scegli i top-3 dal ranking
            top_frames = pick_top_k_frames(meta, k=3)
            # Se non ci sono, lascia vuoto (verranno placeholder nei prompt)
            for i in range(1, 4):
                ld = locals_root / f"local_{i}"
                if not ld.exists():
                    ld.mkdir(parents=True, exist_ok=True)

                local_prompt = ld / "local_prompt.md"
                if local_prompt.exists() and not overwrite:
                    skipped += 1
                    continue

                frame_id  = top_frames[i-1] if i-1 < len(top_frames) else None
                frame_idx = frame_id_to_index(frame_id) if frame_id else None
                # Nome file: se trovo l'immagine reale, userò quello; altrimenti placeholder
                frame_path = find_frame_file(out_ep, frame_id) if frame_id else None
                frame_name = frame_path.name if frame_path else "frame_.jpg"
                frame_score = get_frame_score(meta, frame_id) if frame_id else None

                ann_obj  = get_local_annotation(meta, frame_id) if frame_id else None
                ann_text = json.dumps(ann_obj, indent=2, ensure_ascii=False) if ann_obj else LOCAL_ANNOTATION_SKELETON

                content = LOCAL_PROMPT_TEMPLATE.format(
                    NODE_LIBRARY=indent_block(node_lib_text, 0),
                    GLOBAL_BT=indent_block(bt_text, 0),
                    GLOBAL_DESCRIPTION=indent_block(tld_text, 0),
                    FRAME_INDEX=("null" if frame_idx is None else str(frame_idx)),
                    FRAME_NAME=frame_name,
                    FRAME_RANK_HINT=("null" if frame_score is None else frame_score),
                    LOCAL_ANNOTATION=ann_text,
                    REPLACEMENT_TARGET=REPLACEMENT_TARGET_SKELETON
                )

                if dry_run:
                    print(f"[DRY] would write {local_prompt} (frame_id={frame_id}, file={frame_name}, score={frame_score})")
                else:
                    write_safe(local_prompt, content, overwrite=True)
                    # copia il frame reale nella cartella local_i se esiste
                    if frame_path is not None:
                        dst_img = ld / frame_path.name
                        copied = copy_safe(frame_path, dst_img, overwrite)
                        if copied:
                            print(f"[OK]  copied frame -> {dst_img}")
                    created += 1
                    print(f"[OK]  wrote {local_prompt} (frame_id={frame_id}, file={frame_name}, score={frame_score})")

    print(f"\nLocals done. local_prompt.md created: {created} | skipped (exists): {skipped}")

# -------------------- Main --------------------

def main():
    ap = argparse.ArgumentParser(description="Generate per-episode structure and/or local prompts.")
    ap.add_argument("--mode", choices=["init", "locals"], default="init",
                    help="init: crea struttura episodio; locals: genera prompt locali precompilati e copia i frame top-K.")
    ap.add_argument("--out-root", default="out", help="[init] sorgente datasets/episodes (default: out)")
    ap.add_argument("--dest-root", default="dataset", help="[init/locals] destinazione (default: dataset)")
    ap.add_argument("--prompt-src", default=None, help="[init] template prompt globale (default: prompts/prompt_full.md o prompts/prompt.md)")
    ap.add_argument("--prompt-name", default="prompt.md", help="[init] nome file prompt generato (default: prompt.md)")
    ap.add_argument("--node-lib", type=Path, default=None, help="[locals] path a node_library.json")
    ap.add_argument("--overwrite", action="store_true", help="sovrascrive file esistenti")
    ap.add_argument("--dry-run", action="store_true", help="stampa azioni senza scrivere")
    args = ap.parse_args()

    project_root = Path.cwd()
    dest_root = project_root / args.dest_root

    if args.mode == "init":
        out_root = project_root / args.out_root
        if args.prompt_src:
            prompt_src = Path(args.prompt_src)
        else:
            cand = [project_root / "prompts" / "prompt_full.md",
                    project_root / "prompts" / "prompt.md"]
            prompt_src = next((p for p in cand if p.exists()), None)
            if prompt_src is None:
                raise FileNotFoundError("Template prompt non trovato. Specifica --prompt-src.")
        init_mode(out_root, dest_root, prompt_src, args.prompt_name, args.overwrite, args.dry_run)

    elif args.mode == "locals":
        if args.node_lib is None:
            raise FileNotFoundError("--node-lib è obbligatorio in --mode locals.")
        locals_mode(project_root, dest_root, args.node_lib, args.overwrite, args.dry_run)

if __name__ == "__main__":
    main()


'''
python generate_folders.py \
  --mode init \
  --out-root out \
  --dest-root dataset \
  --prompt-src prompts/prompt_full.md

python generate_folders.py \
  --mode locals \
  --dest-root dataset \
  --node-lib library/node_library_v_01.json
  

'''