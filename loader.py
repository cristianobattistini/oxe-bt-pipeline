from __future__ import annotations
import json
import pathlib
import re
from typing import Any, Dict, Iterator, Optional, List

import numpy as np
import tensorflow_datasets as tfds  # type: ignore

from utils import ensure_dir, to_uint8_rgb, save_jpeg, save_gif, summarize_nested


# -------------------------- TFDS / OXE loading ------------------------------ #

def dataset2path(name: str) -> str:
    p = pathlib.Path(name)
    if p.exists() and p.is_dir():
        return str(p.resolve())
    return name

def _make_builder(name: str):
    path = dataset2path(name)
    try:
        return tfds.builder_from_directory(path)
    except Exception:
        return tfds.builder(name)

def load_episodes(dataset: str, split: str) -> Iterator[Dict[str, Any]]:
    builder = _make_builder(dataset)
    ds = builder.as_dataset(split=split)
    for example in tfds.as_numpy(ds):
        yield dict(example) if not isinstance(example, dict) else example

def load_first_episode(dataset: str, split: str) -> Optional[Dict[str, Any]]:
    for ex in load_episodes(dataset, split):
        return ex
    return None


# ------------------------------ Episode dump -------------------------------- #

_WHITESPACE_RE = re.compile(r"\s+")

def dump_episode(
    episode: Dict[str, Any],
    out_dir: str,
    image_key: str,
    instruction_key: str,
    max_frames: int,
) -> Dict[str, Any]:
    """
    Strict mode (stile Colab): usa SOLO `image_key` e `instruction_key` forniti.
    """
    out_dir = str(out_dir)
    raw_dir = pathlib.Path(out_dir) / "raw_frames"
    ensure_dir(raw_dir)

    # 1) Immagini
    img_container = episode.get(image_key, None)
    frames: List[np.ndarray] = []
    if img_container is None:
        pass
    elif isinstance(img_container, (list, tuple)):
        frames = list(img_container)
    else:
        arr = np.asarray(img_container)
        frames = [arr[i] for i in range(arr.shape[0])] if arr.ndim >= 4 else [arr]

    saved = 0
    collected_for_gif: List[np.ndarray] = []
    for frame in frames:
        if saved >= max_frames:
            break
        try:
            rgb = to_uint8_rgb(frame)
        except Exception:
            continue
        save_jpeg(rgb, str(raw_dir / f"frame_{saved:04d}.jpg"))
        collected_for_gif.append(rgb)
        saved += 1

    if collected_for_gif:
        save_gif(collected_for_gif, str(pathlib.Path(out_dir) / "preview.gif"), fps=6)

    # 2) Istruzione — salvataggio RAW (nessuna normalizzazione)
    instr = episode.get(instruction_key, None)
    if instr is not None:
        if isinstance(instr, bytes):
            raw = instr.decode("utf-8", errors="ignore")
        elif isinstance(instr, (np.ndarray,)):
            v = instr.item() if getattr(instr, "shape", None) == () else instr
            raw = v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else str(v)
        else:
            raw = str(instr)
        with open(pathlib.Path(out_dir) / "instruction.txt", "w", encoding="utf-8") as f:
            f.write(raw)

    return {
        "out_dir": out_dir,
        "frame_count": saved,
        "instruction_present": instr is not None,
        "gif": collected_for_gif != [],
    }


def dump_attributes(episode: Dict[str, Any], out_dir: str) -> str:
    """
    Scrive out_dir/attributes.json con la mappa chiave→summary (tipo/shape/dtype/len).
    """
    summary = summarize_nested(episode)
    path = pathlib.Path(out_dir) / "attributes.json"
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return str(path)
