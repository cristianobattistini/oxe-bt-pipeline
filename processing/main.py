# main.py
# Orchestratore Step 1: esporta fino a N episodi per ciascun dataset OXE (RLDS).
# Per ogni episodio salva: frame JPEG, preview.gif (se ≥2 frame), instruction.txt (se presente), attributes.json.

try:
    from ._bootstrap import ensure_repo_root
except ImportError:
    from _bootstrap import ensure_repo_root

ensure_repo_root()

import os
import re
import json
from datetime import datetime
import processing.utils.config as CFG
from processing.utils.loader import iterate_episodes, dump_attributes, dump_episode_rlds, parse_action_fields
from processing.utils.episode_phases import build_all_episode_phases


def _sanitize(s: str) -> str:
    """
    Rende il nome del dataset sicuro come nome di cartella.
    Sostituisce caratteri non alfanumerici con '_'.
    Esempio: 'utokyo_xarm_pick_and_place/0.1.0' → 'utokyo_xarm_pick_and_place_0.1.0'
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

def _existing_episode_indices(ds_root: str) -> list[int]:
    """
    Ritorna gli indici episode_XXX già presenti (numerici).
    """
    indices = []
    if not os.path.isdir(ds_root):
        return indices
    for name in os.listdir(ds_root):
        if not name.startswith("episode_"):
            continue
        tail = name.split("_", 1)[-1]
        if tail.isdigit():
            indices.append(int(tail))
    return sorted(indices)

def _resolve_dataset_list() -> list[str]:
    """
    Se CFG.datasets è non vuota, usa quella; altrimenti usa [CFG.dataset].
    Consente sia il caso singolo sia più dataset nello stesso run.
    """
    if hasattr(CFG, "datasets") and CFG.datasets:
        return CFG.datasets
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
    per_ds_limit = getattr(CFG, "limit_episodes_per_dataset", None)
    data_dir     = getattr(CFG, "tfds_data_dir", None)
    k_sampling   = getattr(CFG, "k_sampling", 10)
    mode            = getattr(CFG, "export_mode", "full")
    filename_mode   = getattr(CFG, "filename_mode", "original")
    normalize_names = getattr(CFG, "normalize_names", False)
    prune_only      = getattr(CFG, "prune_only", False)
    resume_from_existing = getattr(CFG, "resume_from_existing", False)
    skip_existing        = getattr(CFG, "skip_existing", True)

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

        existing = _existing_episode_indices(ds_root) if resume_from_existing else []
        start_idx = (max(existing) + 1) if existing else 0
        if resume_from_existing:
            print(f"[RESUME] {ds}: start_idx={start_idx} existing={len(existing)}")
            if per_ds_limit and start_idx >= per_ds_limit:
                print(f"[RESUME] {ds}: limit {per_ds_limit} already reached, skipping.")
                continue

        exported = 0
        skip_for_iter = start_idx if resume_from_existing else 0
        for offset, episode in enumerate(iterate_episodes(ds, split, data_dir=data_dir, skip=skip_for_iter)):
            episode_idx = start_idx + offset
            if per_ds_limit and episode_idx >= per_ds_limit:
                break

            ep_dir = os.path.join(ds_root, f"episode_{episode_idx:03d}")
            if skip_existing and os.path.isdir(ep_dir):
                continue
            os.makedirs(ep_dir, exist_ok=True)

            # 1) attributes.json per ispezione rapida della struttura
            dump_attributes(episode, ep_dir)

            # 2) frame + gif + instruction
            try:
                print(f"[INFO] Dumping ep#{episode_idx:03d}...")
                summary = dump_episode_rlds(
                    episode=episode,
                    out_dir=ep_dir,
                    image_key=image_key,
                    instruction_key=instruction_key,
                    max_frames=max_frames,
                )
                print(f"[INFO] Dump success, now building all phases...")

                # Prova a estrarre i passi (se l'episodio è un dict OXE/RLDS)
                steps = None
                try:
                    if isinstance(episode, dict):
                        steps = episode.get("steps", None)
                except Exception:
                    steps = None

                build_all_episode_phases(
                    ep_dir=ep_dir,
                    episode_steps=steps,          # per arricchire attributes se disponibili
                    export_mode=mode,             # "full" | "final_only"
                    filename_mode=filename_mode,  # "original" | "sequential"
                    normalize_names=normalize_names,
                    prune_only=prune_only,        # se True, ripulisce fasi intermedie
                )

                print(f"[INFO] All phases built for ep#{episode_idx:03d}")

            except Exception as e:
                print(f"[WARN] {ds} ep#{episode_idx:03d} skipped: {e}")

            exported += 1
            grand_total += 1

        print(f"[SUMMARY] {ds} → {exported} episodio/i esportati. Output: {ds_root}")

    print(f"\n[DONE] started={run_started}  total_exported={grand_total}  out_root={out_root}")


if __name__ == "__main__":
    main()
