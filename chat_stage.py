#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Staging persistente per PROMPTS (p/) e FRAMES (f/) dal dato episodio fino alla fine.

Uso tipico:
  python chat_stage.py build --from 1
  python chat_stage.py build --from 17 --dataset utokyo_xarm_pick_and_place_0.1.0
  python chat_stage.py build --from 5 --locals 1,2,3

Comandi:
  build    : crea/aggiorna p/ e f/ per tutti gli episodi da --from in avanti
  rebuild  : pulisce p/ e f/ e poi esegue build (richiede gli stessi parametri di build)
  clean    : rimuove p/ e f/
  status   : mostra quanti episodi/local verrebbero processati con i parametri indicati

Parametri comuni:
  --from N           (obbligatorio per build/rebuild/status) episodio di partenza (numero)
  --dataset NAME     (opzionale) nome dir in dataset/, default: columbia_cairlab_pusht_real_0.1.0
  --locals 1,2,3     (opzionale) lista di local da includere; default: 1,2,3
"""

import argparse
import os
import re
import shutil
from pathlib import Path
from typing import List, Optional

# ====== DEFAULTS MODIFICABILI ======
DATASET_ROOT = Path("dataset")
DEFAULT_DATASET = "utokyo_pr2_opening_fridge_0.1.0"
EPISODE_PREFIX = "episode_"
EP_NUM_WIDTH = 3
DEFAULT_LOCALS = [1, 2, 3]
P_DIR = Path("p")   # prompts
F_DIR = Path("f")   # frames
# ===================================

def ep_name(n: int) -> str:
    return f"{EPISODE_PREFIX}{n:0{EP_NUM_WIDTH}d}"

def list_episodes(dataset: str) -> List[int]:
    base = DATASET_ROOT / dataset
    nums = []
    for p in base.glob(f"{EPISODE_PREFIX}*"):
        if p.is_dir():
            m = re.fullmatch(rf"{re.escape(EPISODE_PREFIX)}(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
    return sorted(nums)

def pick_prompt(local_dir: Path) -> Optional[Path]:
    for cand in (local_dir / "local_prompt.md", local_dir / "local_prompt"):
        if cand.exists():
            return cand
    return None

def pick_frame(local_dir: Path) -> Optional[Path]:
    imgs = sorted(local_dir.glob("frame_*.jpg"))
    return imgs[0] if imgs else None

def symlink_or_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dst.exists():
            dst.unlink()
        os.symlink(src.resolve(), dst)
    except OSError:
        shutil.copy2(src, dst)

def prepare_episode(dataset: str, ep: int, locals_list: List[int]) -> int:
    """Ritorna quanti local sono stati creati/aggiornati per ep."""
    ep_dir = DATASET_ROOT / dataset / ep_name(ep)
    if not ep_dir.is_dir():
        print(f"Avviso: manca {ep_dir}, salto episodio.")
        return 0

    created = 0
    for loc in locals_list:
        local_dir = ep_dir / "locals" / f"local_{loc}"
        if not local_dir.is_dir():
            print(f"Avviso: manca {local_dir}, salto local.")
            continue

        prompt = pick_prompt(local_dir)
        frame  = pick_frame(local_dir)
        if prompt is None:
            print(f"Avviso: {local_dir} senza local_prompt(.md), salto local.")
            continue
        if frame is None:
            print(f"Avviso: {local_dir} senza frame_*.jpg, salto local.")
            continue

        label = f"E{ep:0{EP_NUM_WIDTH}d}_L{loc}"
        # Prompt
        ext = prompt.suffix if prompt.suffix else ".md"
        dst_prompt = P_DIR / f"{label}_local_prompt{ext}"
        symlink_or_copy(prompt, dst_prompt)
        # Frame
        dst_frame = F_DIR / f"{label}_frame{frame.suffix}"
        symlink_or_copy(frame, dst_frame)

        created += 1
    return created

def do_build(from_ep: int, dataset: str, locals_list: List[int]) -> int:
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"Nessun episodio >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return 0
    total = 0
    for ep in eps:
        total += prepare_episode(dataset, ep, locals_list)
    print(f"Creati/aggiornati {total} local in p/ e f/ "
          f"(dataset '{dataset}', da {ep_name(from_ep)} a {ep_name(eps[-1])}).")
    return total

def do_rebuild(from_ep: int, dataset: str, locals_list: List[int]):
    for d in (P_DIR, F_DIR):
        if d.exists():
            shutil.rmtree(d)
    do_build(from_ep, dataset, locals_list)

def do_status(from_ep: int, dataset: str, locals_list: List[int]):
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"Nessun episodio >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return
    print(f"Processerei {len(eps)} episodi ({ep_name(eps[0])} → {ep_name(eps[-1])}), "
          f"{len(locals_list)} local ciascuno: ~{len(eps)*len(locals_list)} coppie.")

def do_clean():
    removed = False
    for d in (P_DIR, F_DIR):
        if d.exists():
            shutil.rmtree(d)
            removed = True
    print("Pulito." if removed else "Nulla da rimuovere.")

def parse_locals(s: Optional[str]) -> List[int]:
    if not s:
        return DEFAULT_LOCALS
    vals = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if not tok.isdigit():
            raise SystemExit("Formato --locals non valido. Esempio: --locals 1,2,3")
        vals.append(int(tok))
    return vals or DEFAULT_LOCALS

def main():
    ap = argparse.ArgumentParser(description="Staging p/ (prompts) e f/ (frames) dal dato episodio fino alla fine.")
    ap.add_argument("cmd", choices=["build", "rebuild", "clean", "status"])
    ap.add_argument("--from", dest="from_ep", type=int, help="episodio di partenza (numero, es. 17)")
    ap.add_argument("--dataset", dest="dataset", default=DEFAULT_DATASET, help="nome dataset in 'dataset/'")
    ap.add_argument("--locals", dest="locals_csv", default=",".join(map(str, DEFAULT_LOCALS)),
                    help="lista di local, es. '1,2,3'")
    args = ap.parse_args()

    if args.cmd in ("build", "rebuild", "status") and args.from_ep is None:
        raise SystemExit("Parametro obbligatorio: --from <numero episodio>")

    locals_list = parse_locals(args.locals_csv)

    if args.cmd == "build":
        do_build(args.from_ep, args.dataset, locals_list)
    elif args.cmd == "rebuild":
        do_rebuild(args.from_ep, args.dataset, locals_list)
    elif args.cmd == "status":
        do_status(args.from_ep, args.dataset, locals_list)
    elif args.cmd == "clean":
        do_clean()

if __name__ == "__main__":
    main()
