"""
utils.py — Funzioni di utilità riusabili e indipendenti dal dataset.

Contiene:
- ensure_dir: crea directory in sicurezza.
- to_uint8_rgb: normalizza array immagine a RGB uint8 contiguo (per PIL).
- save_jpeg: salva JPEG con impostazioni sicure.
- save_gif: compone una GIF di anteprima da una lista di frame.
- summarize_nested: ispeziona un nested-dict e riassume tipo/shape/dtype di ogni foglia.

Queste utility sono "pure": nessun side-effect oltre all'I/O esplicito richiesto.
"""

from __future__ import annotations
import pathlib
from typing import Any, Dict, List

import numpy as np
from PIL import Image


# ------------------------------ FS utils ------------------------------------ #

def ensure_dir(p: str | pathlib.Path) -> None:
    """Crea la directory (e genitori) se non esiste."""
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)


# ------------------------------ Image utils --------------------------------- #

def to_uint8_rgb(arr: np.ndarray) -> np.ndarray:
    """
    Converte un array immagine a RGB uint8 contiguo (C-contiguous) per PIL.

    Casi gestiti:
      - float in [0,1] o [-1,1] → scaling a [0,255]
      - altri float → min-max scaling a [0,255]
      - interi → clip [0,255]
      - (H,W) → (H,W,3) replicando, (H,W,4) → drop alpha, (1,H,W,C) → squeeze
    """
    if not isinstance(arr, np.ndarray):
        arr = np.asarray(arr)
    if arr.ndim >= 4 and arr.shape[0] == 1:
        arr = arr.squeeze(0)

    a = arr.astype(np.float32, copy=False)
    mn, mx = float(a.min()), float(a.max())
    if a.dtype.kind == "f":
        if 0.0 <= mn and mx <= 1.0:
            a = a * 255.0
        elif -1.0 <= mn and mx <= 1.0:
            a = (a * 0.5 + 0.5) * 255.0
        else:
            rng = max(1e-12, mx - mn)
            a = (a - mn) * (255.0 / rng)
    else:
        a = np.clip(a, 0, 255)
    a = np.clip(a, 0, 255).astype(np.uint8, copy=False)

    if a.ndim == 2:
        a = np.stack([a, a, a], axis=-1)
    elif a.ndim == 3:
        if a.shape[-1] == 4:
            a = a[..., :3]
        elif a.shape[-1] == 1:
            a = np.tile(a, (1, 1, 3))
        elif a.shape[-1] >= 3:
            a = a[..., :3]
    else:
        raise ValueError(f"Unexpected image shape {a.shape}")

    if not a.flags.c_contiguous:
        a = np.ascontiguousarray(a)
    return a


def save_jpeg(rgb_uint8: np.ndarray, path: str) -> None:
    """Salva un RGB uint8 come JPEG con impostazioni sicure."""
    ensure_dir(pathlib.Path(path).parent)
    Image.fromarray(rgb_uint8, mode="RGB").save(
        path, format="JPEG", quality=95, subsampling=0, optimize=True
    )


def save_gif(frames: List[np.ndarray], out_path: str, fps: int = 6) -> None:
    """Crea una GIF di anteprima da frame arbitrari (converte a RGB uint8)."""
    ensure_dir(pathlib.Path(out_path).parent)
    imgs = [Image.fromarray(to_uint8_rgb(f)) for f in frames]
    if not imgs:
        return
    duration_ms = max(1, int(1000 / fps))
    imgs[0].save(
        out_path,
        save_all=True,
        append_images=imgs[1:],
        duration=duration_ms,
        loop=0,
        format="GIF",
    )


# ----------------------------- Introspection -------------------------------- #

def _summ_item(x: Any) -> Dict[str, Any]:
    """Riassunto compatto per una foglia (tipo; per ndarray: shape/dtype/size; per bytes/list: len)."""
    t = type(x).__name__
    out: Dict[str, Any] = {"type": t}
    if isinstance(x, np.ndarray):
        out.update({"shape": list(x.shape), "dtype": str(x.dtype), "size": int(x.size)})
    elif isinstance(x, (bytes, bytearray)):
        out.update({"len": len(x)})
    elif isinstance(x, (list, tuple)):
        out.update({"len": len(x)})
    return out


def summarize_nested(obj: Any, prefix: str = "") -> Dict[str, Any]:
    """
    Visita ricorsivamente un nested-dict e produce una mappa:
      dot.path → summary (tipo/shape/dtype/...).
    """
    out: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(summarize_nested(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = _summ_item(obj)
    return out
