import os
import json
from typing import List, Dict, Optional, Tuple
from PIL import Image
import numpy as np
from glob import glob

from utils import make_gif, to_json_safe  # Assicurati che esista
from loader import sample_every_k, parse_action_fields
from frame_selection import embedding_select_from_raw
import config as CFG


def _load_raw_frames_from_disk(ep_dir: str) -> Tuple[np.ndarray, List[str]]:
    """Carica i frame già salvati in raw_frames/ come array uint8 e lista path."""
    frames_dir = os.path.join(ep_dir, "raw_frames")
    if not os.path.isdir(frames_dir):
        return np.empty((0,), dtype=np.uint8), []
    paths = sorted(glob(os.path.join(frames_dir, "frame_*.jpg")))
    if not paths:
        return np.empty((0,), dtype=np.uint8), []
    imgs = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
    arr = np.stack(imgs, axis=0)  # (T, H, W, C), dtype uint8
    return arr, paths


def _read_instruction_if_any(ep_dir: str) -> str:
    p = os.path.join(ep_dir, "instruction.txt")
    if os.path.isfile(p):
        try:
            return open(p, "r", encoding="utf-8").read().strip()
        except Exception:
            return ""
    return ""


def write_episode_phase(
    ep_dir: str,
    phase_name: str,
    frames: List[np.ndarray] | np.ndarray,
    frame_indices: List[int],
    instruction: str,
    gif: bool = True,
    attributes: List[Dict] = None,
):
    """
    Salva:
      - sampled_frames/
      - preview.gif
      - attributes.json
      - episode_data.json
    """
    out_dir = os.path.join(ep_dir, phase_name)
    os.makedirs(out_dir, exist_ok=True)

    frames_dir = os.path.join(out_dir, "sampled_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # normalizza frames in lista di immagini
    if isinstance(frames, np.ndarray):
        if frames.ndim == 3:
            frames = frames[None, ...]
        frames_list = [frames[i] for i in range(frames.shape[0])]
    else:
        frames_list = frames

    rel_paths = []
    for i, t in enumerate(frame_indices):
        img = Image.fromarray(frames_list[i])
        fname = f"frame_{t:04d}.jpg"
        img.save(os.path.join(frames_dir, fname), quality=95)
        rel_paths.append(os.path.join("sampled_frames", fname))

    # GIF
    if gif and len(frames_list) >= 2:
        gif_path = os.path.join(out_dir, "preview.gif")
        make_gif(frames_list, gif_path)

    # Attributes
    attr_data = {}
    if attributes is not None:
        for i, t in enumerate(frame_indices):
            attr_data[f"frame_{t:04d}.jpg"] = attributes[i]
    else:
        attr_data = {f"frame_{t:04d}.jpg": {"selected_index": int(t)} for t in frame_indices}

    with open(os.path.join(out_dir, "attributes.json"), "w") as f:
        json.dump(to_json_safe(attr_data), f, indent=2)

    # Episode data
    edata = {
        "instruction": instruction,
        "frames": rel_paths,
    }
    with open(os.path.join(out_dir, "episode_data.json"), "w") as f:
        json.dump(edata, f, indent=2)


def build_all_episode_phases(ep_dir: str, episode_steps: Optional[list] = None):
    """
    Versione robusta:
      - legge i frame da raw_frames/ (fonte unica),
      - usa CFG.embeds['k_slicing'] per il campionamento temporale,
      - costruisce una fase sampled_k{K} (K = k_slicing),
      - opzionalmente analizza segnali dalle azioni se episode_steps è fornito,
      - invoca la selezione embedding (embedding_select_from_raw) e crea final_selected/.
    """
    # 0) Carica i frame già esportati
    arr, _ = _load_raw_frames_from_disk(ep_dir)
    if arr.size == 0:
        print(f"[PHASES] skip: no raw_frames in {ep_dir}")
        return
    if arr.dtype != np.uint8:
        # se per qualsiasi motivo non è uint8, normalizza
        if np.issubdtype(arr.dtype, np.floating):
            arr = np.clip(arr * (255.0 if arr.max() <= 1.0 else 1.0), 0, 255).astype(np.uint8)
        else:
            arr = arr.astype(np.uint8)

    T = arr.shape[0]
    instruction = _read_instruction_if_any(ep_dir)

    # 1) campionamento temporale con k_slicing da config
    k = int(CFG.embeds.get("k_slicing", 10))
    sampled_arr, indices = sample_every_k(arr, k)

    # 2) Attributi base (se abbiamo episode_steps, li estraiamo; altrimenti fallback minimale)
    base_attrs = []
    if episode_steps is not None and isinstance(episode_steps, (list, tuple)) and len(episode_steps) == T:
        for i in indices:
            try:
                parsed = parse_action_fields(episode_steps[i])
            except Exception:
                parsed = {"selected_index": int(i)}
            base_attrs.append(to_json_safe(parsed))
    else:
        base_attrs = [{"selected_index": int(i)} for i in indices]

    # 3) Scrivi fase di campionamento puro
    sampled_phase_name = f"sampled_k{k}"
    write_episode_phase(
        ep_dir=ep_dir,
        phase_name=sampled_phase_name,
        frames=sampled_arr,
        frame_indices=indices,
        instruction=instruction,
        gif=True,
        attributes=base_attrs,
    )
    print(f"[PHASES] wrote {sampled_phase_name} with {len(indices)} frames.")

    # 4) Se attivo, selezione via embedding (on-disk) e creazione di final_selected/
    if getattr(CFG, "run_embed_selection", True):
        try:
            sel = embedding_select_from_raw(ep_dir, CFG.embeds)
            if sel and sel.get("selected_indices"):
                sel_idx = sel["selected_indices"]  # indici NELLA SEQUENZA TOTALE
                sel_frames = [arr[t] for t in sel_idx]
                # attributi minimi per i selezionati (ricicla parse_action_fields se possibile)
                sel_attrs = []
                if episode_steps is not None and isinstance(episode_steps, (list, tuple)) and len(episode_steps) == T:
                    for t in sel_idx:
                        try:
                            parsed = parse_action_fields(episode_steps[t])
                        except Exception:
                            parsed = {"selected_index": int(t)}
                        sel_attrs.append(to_json_safe(parsed))
                else:
                    sel_attrs = [{"selected_index": int(t)} for t in sel_idx]

                write_episode_phase(
                    ep_dir=ep_dir,
                    phase_name="final_selected",
                    frames=sel_frames,
                    frame_indices=sel_idx,
                    instruction=instruction,
                    gif=True,
                    attributes=sel_attrs,
                )
                print(f"[EMBEDS] selected {len(sel_idx)} frames (k_slicing={sel['k_slicing']}, K={sel['K']}).")
            else:
                print("[EMBEDS] no frames to select (selection returned empty).")
        except Exception as e:
            print(f"[WARN][EMBEDS] selection failed in {ep_dir}: {e}")
