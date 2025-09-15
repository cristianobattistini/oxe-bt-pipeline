#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bootstrap per-episode files (bt.xml, meta.json, prompt.md) partendo dalla struttura sotto 'out/'.
- Scansiona: out/<DATASET_ID>/episode_*/
- Scrive:    dataset/<DATASET_ID>/<EPISODE_ID>/{bt.xml, meta.json, prompt.md}
- prompt.md viene copiato da PROMPT.md/prompt.md in root (o --prompt-src),
  e auto-riempito con instruction/dataset/episode.
"""

import argparse
import json
import re
from pathlib import Path
from datetime import datetime

PROMPT_LINE_PATTERNS = {
    "TASK INSTRUCTION": re.compile(r'^(\s*-\s*TASK INSTRUCTION:\s*)".*?"\s*$', re.IGNORECASE),
    "DATASET_ID":       re.compile(r'^(\s*-\s*DATASET_ID:\s*)".*?"\s*$', re.IGNORECASE),
    "EPISODE_ID":       re.compile(r'^(\s*-\s*EPISODE_ID:\s*)".*?"\s*$', re.IGNORECASE),
}

BT_XML_SKELETON = """<BehaviorTree ID="MainTree">
  <Sequence>
    <!-- TODO: fill with valid nodes from node_library -->
  </Sequence>
</BehaviorTree>
"""

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
        # fallback: inserisci sotto la sezione INPUTS
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

def read_instruction(ep_out_dir: Path) -> str:
    instr_file = ep_out_dir / "instruction.txt"
    if instr_file.exists():
        return instr_file.read_text(encoding="utf-8").strip()
    return ""

def write_safe(path: Path, content: str, overwrite: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    path.write_text(content, encoding="utf-8")
    return True

def main():
    ap = argparse.ArgumentParser(description="Generate bt.xml, meta.json, prompt.md for each episode found under 'out/'.")
    ap.add_argument("--out-root", default="out", help="Root sorgente con datasets/episodes (default: out)")
    ap.add_argument("--dest-root", default="dataset", help="Root destinazione (default: dataset)")
    ap.add_argument("--prompt-src", default=None, help="Path al template prompt (default: PROMPT.md o prompt.md in root)")
    ap.add_argument("--prompt-name", default="prompt.md", help="Nome file prompt generato (default: prompt.md)")
    ap.add_argument("--overwrite", action="store_true", help="Sovrascrive file esistenti")
    ap.add_argument("--dry-run", action="store_true", help="Mostra cosa farebbe senza scrivere")
    args = ap.parse_args()

    project_root = Path.cwd()
    out_root  = project_root / args.out_root
    dest_root = project_root / args.dest_root

    # Sorgente template prompt
    if args.prompt_src:
        prompt_src = Path(args.prompt_src)
    else:
        cand = [project_root / "PROMPT.md", project_root / "prompt.md"]
        prompt_src = next((p for p in cand if p.exists()), None)
        if prompt_src is None:
            raise FileNotFoundError("PROMPT.md/prompt.md non trovati nella root. Specifica --prompt-src.")

    prompt_template = load_prompt_template(prompt_src)

    if not out_root.exists():
        raise FileNotFoundError(f"'out' root non trovata: {out_root}")

    created = 0
    skipped = 0
    now = datetime.now().isoformat(timespec="seconds")

    for ds_dir in sorted([p for p in out_root.iterdir() if p.is_dir()]):
        dataset_id = ds_dir.name
        for ep_dir in sorted([p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]):
            episode_id = ep_dir.name
            instruction = read_instruction(ep_dir)

            ep_dest = dest_root / dataset_id / episode_id
            bt_path   = ep_dest / "bt.xml"
            meta_path = ep_dest / "meta.json"
            prm_path  = ep_dest / args.prompt_name



            # Skip totale se la cartella dell'episodio esiste e non è richiesto overwrite
            if ep_dest.exists() and not args.overwrite:
                if args.dry_run:
                    print(f"[DRY][SKIP] {dataset_id}/{episode_id} (episode dir already exists)")
                else:
                    print(f"[SKIP] {dataset_id}/{episode_id} (episode dir already exists; use --overwrite to regenerate)")
                skipped += 1
                continue

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

            if args.dry_run:
                print(f"[DRY] {dataset_id}/{episode_id} -> {bt_path.name}, {meta_path.name}, {prm_path.name}")
                continue

                # scrittura
            wrote_any = False
            wrote_any |= write_safe(bt_path, BT_XML_SKELETON, args.overwrite)
            wrote_any |= write_safe(meta_path, meta_json, args.overwrite)
            wrote_any |= write_safe(prm_path, prompt_filled, args.overwrite)

            if wrote_any:
                created += 1
                print(f"[OK]  {dataset_id}/{episode_id} → files ready")
            else:
                skipped += 1
                print(f"[SKIP] {dataset_id}/{episode_id} (già presenti; usa --overwrite)")

    if not args.dry_run:
        print(f"\nDone. Episodes: {created + skipped} | created/updated: {created} | skipped: {skipped}")

if __name__ == "__main__":
    main()

    