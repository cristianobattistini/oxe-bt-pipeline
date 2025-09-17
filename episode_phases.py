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

try:
    from contact_sheet import create_from_dir as _cs_create
except Exception:
    _cs_create = None


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
    filename_mode: str = "original",  # NEW: "original" | "sequential"
):
    """
    Salva:
      - sampled_frames/ (nomi coerenti con filename_mode)
      - preview.gif      (ordine fotogrammi coerente con filename_mode)
      - attributes.json  (chiavi = filename salvato; conserva selected_index = t originale)
      - episode_data.json

    filename_mode:
      - "original":   usa l'indice reale t nel nome file (frame_00xx.jpg)
      - "sequential": ordina per t crescente e salva come frame_00.jpg, frame_01.jpg, ...
    """
    out_dir = os.path.join(ep_dir, phase_name)
    os.makedirs(out_dir, exist_ok=True)

    frames_dir = os.path.join(out_dir, "sampled_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Normalizza frames in lista
    if isinstance(frames, np.ndarray):
        if frames.ndim == 3:
            frames = frames[None, ...]
        frames_list = [frames[i] for i in range(frames.shape[0])]
    else:
        frames_list = frames

    if len(frames_list) != len(frame_indices):
        raise ValueError(
            f"frames_list ({len(frames_list)}) e frame_indices ({len(frame_indices)}) non coincidono."
        )

    # Allinea o genera attributi
    if attributes is None:
        attributes = [{"selected_index": int(t)} for t in frame_indices]
    else:
        if len(attributes) != len(frame_indices):
            raise ValueError(
                f"attributes ({len(attributes)}) e frame_indices ({len(frame_indices)}) non coincidono."
            )

    # Aggrega triplette (t, frame, attr); se richiesto, ordinale per t
    items = list(zip(frame_indices, frames_list, attributes))  # (t, img, attr)
    if filename_mode == "sequential":
        items.sort(key=lambda x: x[0])  # ordine temporale

    # Salvataggio + mapping filename → attr
    rel_paths = []
    attr_data = {}

    if filename_mode == "sequential":
        width = max(2, len(str(len(items) - 1)))  # padding minimo a 2 cifre
        frames_for_gif = []
        for i, (t, img_arr, attr) in enumerate(items):
            img = Image.fromarray(img_arr)
            fname = f"frame_{i:0{width}d}.jpg"
            img.save(os.path.join(frames_dir, fname), quality=95)
            rel_paths.append(os.path.join("sampled_frames", fname))
            # conserva l’indice temporale originale
            attr = dict(attr)
            attr["selected_index"] = int(t)
            attr_data[fname] = to_json_safe(attr)
            frames_for_gif.append(img_arr)
    else:
        frames_for_gif = []
        for (t, img_arr, attr) in items:
            img = Image.fromarray(img_arr)
            fname = f"frame_{t:04d}.jpg"
            img.save(os.path.join(frames_dir, fname), quality=95)
            rel_paths.append(os.path.join("sampled_frames", fname))
            attr = dict(attr)
            attr["selected_index"] = int(attr.get("selected_index", t))
            attr_data[fname] = to_json_safe(attr)
            frames_for_gif.append(img_arr)

    # GIF coerente con l’ordine di salvataggio
    if gif and len(frames_for_gif) >= 2:
        gif_path = os.path.join(out_dir, "preview.gif")
        make_gif(frames_for_gif, gif_path)

    # attributes.json
    with open(os.path.join(out_dir, "attributes.json"), "w") as f:
        json.dump(attr_data, f, indent=2)

    # episode_data.json
    edata = {
        "instruction": instruction,
        "frames": rel_paths,
        "filename_mode": filename_mode,
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
                    filename_mode="sequential"
                )
                print(f"[EMBEDS] selected {len(sel_idx)} frames (k_slicing={sel['k_slicing']}, K={sel['K']}).")

                if _cs_create is not None:
                    phase_root = os.path.join(ep_dir, "final_selected")
                    frames_dir = os.path.join(phase_root, "sampled_frames")  # <- percorso corretto
                    if not os.path.isdir(frames_dir):
                        print(f"[CS][WARN] frames dir not found: {frames_dir}")
                    else:
                        out_cs = os.path.join(phase_root, "episode.jpeg") 
                        try:
                            _cs_create(
                                frames_dir=frames_dir,
                                dataset_id=os.path.basename(os.path.dirname(ep_dir)) or "DATASET",
                                episode_id=f"{os.path.basename(ep_dir)}/final_selected",
                                out_path=out_cs,
                                k=1,            # già selezionati, no ricampionamento
                                n=9,            # 4×2
                                cols=3, rows=3,
                                tile_max_w=960, # aumenta risoluzione tile per qualità
                                force=False
                            )
                            print(f"[CS] wrote {out_cs}")
                        except Exception as e:
                            print(f"[CS][WARN] contact sheet failed: {e}")
                else:
                    print("[CS] contact_sheet module not available; skipped.")
            else:
                print("[EMBEDS] no frames to select (selection returned empty).")
        except Exception as e:
            print(f"[WARN][EMBEDS] selection failed in {ep_dir}: {e}")
