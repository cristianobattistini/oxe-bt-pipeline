#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Staging persistente per PROMPTS (p/) e FRAMES (f/) dal dato episodio fino alla fine.

Uso tipico (LOCALS):
  python chat_stage.py build --from 1
  python chat_stage.py build --from 17 --dataset utokyo_xarm_pick_and_place_0.1.0
  python chat_stage.py build --from 5 --locals 1,2,3

Uso tipico (ROOT, separato dai locals):
  python chat_stage.py build-root --from 1
  python chat_stage.py status-root --from 10 --dataset asu_table_top_converted_externally_to_rlds_0.1.0
  python chat_stage.py rebuild-root --from 3

Comandi (LOCALS, invariati):
  build       : crea/aggiorna p/ e f/ per tutti gli episodi da --from in avanti (solo locals/)
  rebuild     : pulisce p/ e f/ e poi esegue build (staging locals, come sopra)
  clean       : rimuove p/ e f/ interi (attenzione: cancella anche gli output root)
  status      : mostra quanti episodi/local verrebbero processati (solo locals)

Comandi (ROOT, sempre separati):
  build-root    : crea/aggiorna p/ e f/ SOLO con i file root (prompt.md + contact_sheet.*)
  rebuild-root  : rimuove SOLO gli output root e poi esegue build-root
  clean-root    : rimuove SOLO gli output root da p/ e f/ (non tocca i locals)
  status-root   : mostra quanti episodi root verrebbero processati

Parametri comuni:
  --from N           (obbligatorio per build*/status*) episodio di partenza (numero)
  --dataset NAME     (opzionale) nome dir in dataset/, default: utokyo_pr2_opening_fridge_0.1.0
  --locals 1,2,3     (opzionale, SOLO per comandi locals) lista di local da includere; default: 1,2,3
"""

import argparse
import os
import re
import shutil
from pathlib import Path
from typing import List, Optional

# ====== DEFAULTS MODIFICABILI ======
DATASET_ROOT = Path("dataset1")
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

# -----------------------
# LOCALS: pickers
# -----------------------
def pick_prompt(local_dir: Path) -> Optional[Path]:
    for cand in (local_dir / "local_prompt.md", local_dir / "local_prompt"):
        if cand.exists():
            return cand
    return None

def pick_frame(local_dir: Path) -> Optional[Path]:
    imgs = sorted(local_dir.glob("frame_*.jpg"))
    return imgs[0] if imgs else None

# -----------------------
# ROOT: pickers
# -----------------------
def pick_episode_prompt(ep_dir: Path) -> Optional[Path]:
    # prompt a livello root episodio
    for cand in (ep_dir / "prompt.md", ep_dir / "prompt"):
        if cand.exists():
            return cand
    return None

def pick_contact_sheet(ep_dir: Path) -> Optional[Path]:
    # contact sheet a livello root episodio
    for name in ("contact_sheet.jpg", "contact_sheet.jpeg", "contact_sheet.png"):
        cand = ep_dir / name
        if cand.exists():
            return cand
    matches = list(ep_dir.glob("contact_sheet.*"))
    return matches[0] if matches else None

# -----------------------
# FS helpers
# -----------------------
def symlink_or_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dst.exists():
            dst.unlink()
        os.symlink(src.resolve(), dst)
    except OSError:
        shutil.copy2(src, dst)

# -----------------------
# LOCALS: staging
# -----------------------
def prepare_episode(dataset: str, ep: int, locals_list: List[int]) -> int:
    """Ritorna quanti local sono stati creati/aggiornati per ep (solo locals/)."""
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
    print(f"Creati/aggiornati {total} locals in p/ e f/ "
          f"(dataset '{dataset}', da {ep_name(from_ep)} a {ep_name(eps[-1])}).")
    return total

def do_rebuild(from_ep: int, dataset: str, locals_list: List[int]):
    # Pulisce tutto p/ e f/ (comportamento storico)
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
    # Rimuove interamente p/ e f/ (attenzione: cancella anche ROOT)
    removed = False
    for d in (P_DIR, F_DIR):
        if d.exists():
            shutil.rmtree(d)
            removed = True
    print("Pulito." if removed else "Nulla da rimuovere.")

# -----------------------
# ROOT: staging
# -----------------------
def prepare_episode_root(dataset: str, ep: int) -> int:
    """
    Staggia (p/, f/) i file root dell'episodio (prompt.md + contact_sheet.*).
    Ritorna 1 se creato/aggiornato, 0 se nulla da fare.
    """
    ep_dir = DATASET_ROOT / dataset / ep_name(ep)
    if not ep_dir.is_dir():
        print(f"Avviso: manca {ep_dir}, salto episodio (root).")
        return 0

    prompt = pick_episode_prompt(ep_dir)
    sheet  = pick_contact_sheet(ep_dir)

    if prompt is None and sheet is None:
        return 0

    label = f"E{ep:0{EP_NUM_WIDTH}d}"

    if prompt is not None:
        ext = prompt.suffix if prompt.suffix else ".md"
        dst_prompt = P_DIR / f"{label}_prompt{ext}"
        symlink_or_copy(prompt, dst_prompt)

    if sheet is not None:
        dst_frame = F_DIR / f"{label}_contact_sheet{sheet.suffix}"
        symlink_or_copy(sheet, dst_frame)

    return 1

def do_build_root(from_ep: int, dataset: str) -> int:
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"Nessun episodio >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return 0
    total = 0
    for ep in eps:
        total += prepare_episode_root(dataset, ep)
    print(f"Creati/aggiornati {total} ROOT (prompt/contact_sheet) in p/ e f/ "
          f"(dataset '{dataset}', da {ep_name(from_ep)} a {ep_name(eps[-1])}).")
    return total

def do_status_root(from_ep: int, dataset: str):
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"Nessun episodio >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return
    print(f"Processerei {len(eps)} episodi (ROOT soltanto): ~{len(eps)} coppie (prompt + contact_sheet).")

def clean_root_outputs():
    """
    Cancella SOLO gli output root da p/ e f/, senza toccare i file dei locals.
    Usa pattern conservativi:
      p/E???_prompt.*
      f/E???_contact_sheet.*
    """
    removed = False
    if P_DIR.exists():
        for pth in P_DIR.glob(r"E???_prompt.*"):
            if pth.is_file() or pth.is_symlink():
                pth.unlink()
                removed = True
    if F_DIR.exists():
        for pth in F_DIR.glob(r"E???_contact_sheet.*"):
            if pth.is_file() or pth.is_symlink():
                pth.unlink()
                removed = True
    print("Puliti gli output ROOT." if removed else "Nessun output ROOT da rimuovere.")

def do_rebuild_root(from_ep: int, dataset: str):
    clean_root_outputs()
    do_build_root(from_ep, dataset)

# -----------------------
# CLI
# -----------------------
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
    ap.add_argument("cmd", choices=[
        # LOCALS (storici)
        "build", "rebuild", "clean", "status",
        # ROOT (separati)
        "build-root", "rebuild-root", "clean-root", "status-root"
    ])
    ap.add_argument("--from", dest="from_ep", type=int, help="episodio di partenza (numero, es. 17)")
    ap.add_argument("--dataset", dest="dataset", default=DEFAULT_DATASET, help="nome dataset in 'dataset/'")
    ap.add_argument("--locals", dest="locals_csv", default=",".join(map(str, DEFAULT_LOCALS)),
                    help="lista di local, es. '1,2,3' (solo per comandi locals)")
    args = ap.parse_args()

    # Controllo 'from' solo dove serve
    if args.cmd in ("build", "rebuild", "status", "build-root", "rebuild-root", "status-root") and args.from_ep is None:
        raise SystemExit("Parametro obbligatorio: --from <numero episodio>")

    if args.cmd in ("build", "rebuild", "status"):
        locals_list = parse_locals(args.locals_csv)

    # Dispatcher
    if args.cmd == "build":
        do_build(args.from_ep, args.dataset, locals_list)
    elif args.cmd == "rebuild":
        do_rebuild(args.from_ep, args.dataset, locals_list)
    elif args.cmd == "status":
        do_status(args.from_ep, args.dataset, locals_list)
    elif args.cmd == "clean":
        do_clean()

    elif args.cmd == "build-root":
        do_build_root(args.from_ep, args.dataset)
    elif args.cmd == "rebuild-root":
        do_rebuild_root(args.from_ep, args.dataset)
    elif args.cmd == "status-root":
        do_status_root(args.from_ep, args.dataset)
    elif args.cmd == "clean-root":
        clean_root_outputs()

if __name__ == "__main__":
    main()

# ==========================
# ESEMPI DI COMANDI (COPIA-INCOLLA)
# --------------------------
# LOCALS (comportamento storico)
#   python chat_stage.py build --from 1 --dataset asu_table_top_converted_externally_to_rlds_0.1.0
#   python chat_stage.py build --from 10 --dataset utokyo_xarm_pick_and_place_0.1.0 --locals 1,2,3
#   python chat_stage.py status --from 5 --dataset utokyo_pr2_opening_fridge_0.1.0
#   python chat_stage.py rebuild --from 7 --dataset utokyo_pr2_opening_fridge_0.1.0
#   python chat_stage.py clean
#
# ROOT (sempre separati dai locals)
#   python chat_stage.py build-root --from 1 --dataset asu_table_top_converted_externally_to_rlds_0.1.0
#   python chat_stage.py status-root --from 10 --dataset utokyo_pr2_opening_fridge_0.1.0
#   python chat_stage.py rebuild-root --from 3 --dataset utokyo_pr2_opening_fridge_0.1.0
#   python chat_stage.py clean-root
# ==========================
