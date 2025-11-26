#!/usr/bin/env python3
"""
Raccoglie le instruction come insiemi (set) per un elenco fisso di dataset,
senza passare argomenti da CLI. Produce:

  analysis/instruction_sets.batch1.json
  analysis/instructions_all_unique.batch1.txt

Per passare al secondo batch, rimuovere i commenti sulle righe dei dataset
al fondo dell'array DATASETS (sezione 'BATCH 2') e, opzionalmente, cambiare TAG.
"""

from pathlib import Path
import json, re

# Radice contenente i dataset già processati (cartelle "out/<dataset>/episode_XXX/")
ROOT = Path("out")

# Elenco fisso dei 10 dataset. Gli ultimi 5 sono COMMENTATI: di default si lavorerà solo sui primi 5.
DATASETS = [
    # ------------------ BATCH 1 (attivo) ------------------
    # "asu_table_top_converted_externally_to_rlds_0.1.0",
    # "austin_buds_dataset_converted_externally_to_rlds_0.1.0",
    # "berkeley_gnm_cory_hall_0.1.0",
    # "cmu_franka_exploration_dataset_converted_externally_to_rlds_0.1.0",
    # "dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0",

    # ------------------ BATCH 2 (commentato) ---------------
    "imperialcollege_sawyer_wrist_cam_0.1.0",
    "nyu_rot_dataset_converted_externally_to_rlds_0.1.0",
    "tokyo_u_lsmo_converted_externally_to_rlds_0.1.0",
    "ucsd_kitchen_dataset_converted_externally_to_rlds_0.1.0",
    "utokyo_xarm_bimanual_converted_externally_to_rlds_0.1.0",
]

# Tag fisso per distinguere i file di output.
TAG = "batch2"

def norm(s: str) -> str:
    """Normalizzazione blanda: trim + collasso di whitespace in singoli spazi."""
    if s is None:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def iter_instruction_files(dataset_dir: Path):
    """Itera i file instruction.txt in tutte le episode_* del dataset."""
    for ep in sorted(dataset_dir.glob("episode_*")):
        p = ep / "instruction.txt"
        if p.exists():
            yield p

def collect_unique_instructions(ds_name: str):
    """Legge e deduplica (per stringa normalizzata) le instruction di un dataset."""
    uniq = set()
    ds_dir = ROOT / ds_name
    if not ds_dir.exists():
        return []
    for p in iter_instruction_files(ds_dir):
        try:
            raw = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = p.read_text(errors="ignore")
        text = norm(raw)
        if text:
            uniq.add(text)
    return sorted(uniq)

def main():
    if not ROOT.exists():
        raise SystemExit(f"Cartella radice non trovata: {ROOT.resolve()}")

    payload = {}
    global_set = set()

    for name in DATASETS:
        ds_dir = ROOT / name
        if not ds_dir.exists():
            print(f"Avviso: dataset mancante o non trovato: {name}")
            continue
        uniq = collect_unique_instructions(name)
        if not uniq:
            print(f"Nota: nessuna instruction trovata in {name}")
            continue
        payload[name] = uniq
        global_set.update(uniq)

    if not payload:
        raise SystemExit("Nessuna instruction raccolta. Verificare l'array DATASETS e la struttura 'out/<dataset>/episode_XXX/'.")

    payload["_all_unique"] = sorted(global_set)

    out_dir = Path("analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"instruction_sets.{TAG}.json"
    txt_path  = out_dir / f"instructions_all_unique.{TAG}.txt"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text("\n".join(payload["_all_unique"]), encoding="utf-8")

    ds_count = len([k for k in payload.keys() if k != "_all_unique"])
    print(f"Creato: {json_path}")
    print(f"Creato: {txt_path}")
    print(f"Dataset coperti: {ds_count} — Istruzioni uniche globali: {len(payload['_all_unique'])}")

if __name__ == "__main__":
    main()
# python tools/collect_instruction_sets.py
