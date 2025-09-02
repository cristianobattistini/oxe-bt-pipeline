# main.py
# Orchestratore Step 1: esporta fino a N episodi per ciascun dataset OXE (RLDS).
# Per ogni episodio salva: frame JPEG, preview.gif (se ≥2 frame), instruction.txt (se presente), attributes.json.

import os
import re
from datetime import datetime
import config as CFG
from loader import iterate_episodes, dump_attributes, dump_episode_rlds

def _sanitize(s: str) -> str:
    """
    Rende il nome del dataset sicuro come nome di cartella.
    Sostituisce caratteri non alfanumerici con '_'.
    Esempio: 'utokyo_xarm_pick_and_place/0.1.0' → 'utokyo_xarm_pick_and_place_0.1.0'
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

def _resolve_dataset_list() -> list[str]:
    """
    Se CFG.datasets è non vuota, usa quella; altrimenti usa [CFG.dataset].
    Consente sia il caso singolo sia più dataset nello stesso run.
    """
    if hasattr(CFG, "datasets") and CFG.datasets:
        return CFG.datasets
    # fallback singolo dataset (stringa non vuota)
    if getattr(CFG, "dataset", ""):
        return [CFG.dataset]
    raise ValueError("Nessun dataset specificato: configura 'dataset' o 'datasets' in config.py.")

def _keys_for_dataset(ds_name: str) -> tuple[str, str]:
    """
    Restituisce (image_key, instruction_key) per il dataset corrente.
    1) Cerca override in CFG.dataset_keys
    2) Altrimenti usa i fallback globali in config.py
    """
    dmap = getattr(CFG, "dataset_keys", {}) or {}
    if ds_name in dmap:
        return dmap[ds_name][0], dmap[ds_name][1]
    return getattr(CFG, "image_key", "steps/observation/image"), \
           getattr(CFG, "instruction_key", "natural_language_instruction")

def main():
    out_root     = CFG.out_root
    split        = CFG.split
    max_frames   = CFG.max_frames
    per_ds_limit = getattr(CFG, "limit_episodes_per_dataset", 10)
    data_dir    = getattr(CFG, "tfds_data_dir", None)


    os.makedirs(out_root, exist_ok=True)
    run_started = datetime.utcnow().isoformat()

    datasets = _resolve_dataset_list()
    grand_total = 0

    for ds in datasets:
        ds_dirname = _sanitize(ds)
        ds_root = os.path.join(out_root, ds_dirname)
        os.makedirs(ds_root, exist_ok=True)

        image_key, instruction_key = _keys_for_dataset(ds)
        print(f"\n[DATASET] {ds}  split={split}  limit={per_ds_limit}")
        print(f"          image_key='{image_key}'  instruction_key='{instruction_key}'")

        exported = 0
        for episode in iterate_episodes(ds, split, data_dir=data_dir):
            ep_dir = os.path.join(ds_root, f"episode_{exported:03d}")
            os.makedirs(ep_dir, exist_ok=True)

            # 1) attributes.json per ispezione rapida della struttura
            dump_attributes(episode, ep_dir)

            # 2) frame + gif + instruction
            try:
                summary = dump_episode_rlds(
                    episode=episode,
                    out_dir=ep_dir,
                    image_key=image_key,
                    instruction_key=instruction_key,
                    max_frames=max_frames,
                )
                print(f"[OK] {ds} ep#{exported:03d} → frames={summary['frames_saved']}  "
                      f"instr={summary['instruction']}  gif={summary['preview_gif']}")
            except Exception as e:
                # Non blocchiamo il run intero: saltiamo l’episodio problematico
                print(f"[WARN] {ds} ep#{exported:03d} skipped: {e}")

            exported += 1
            grand_total += 1
            if exported >= per_ds_limit:
                break

        print(f"[SUMMARY] {ds} → {exported} episodio/i esportati. Output: {ds_root}")

    print(f"\n[DONE] started={run_started}  total_exported={grand_total}  out_root={out_root}")

if __name__ == "__main__":
    main()
