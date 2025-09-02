# loader.py
# Funzioni di caricamento ed export per OXE (formato RLDS) allineate al notebook ufficiale.
# - iterate_episodes: iteratore di EPISODI TFDS (ognuno con campo 'steps')
# - dump_attributes: salva mappa delle chiavi con shape/dtype (diagnostico)
# - dump_episode_rlds: salva frame JPEG, preview.gif e instruction.txt se presente
# - utility interne per chiavi annidate e conversioni immagini

from typing import Any, Dict, Generator, Sequence, Optional
import os
import json
import numpy as np
import tensorflow_datasets as tfds
from PIL import Image


# =============================================================================
#  Utility: accesso a chiavi annidate ("a/b/c" o "a.b.c")
# =============================================================================
def _get_by_path(d: Dict[str, Any], key: str) -> Any:
    """
    Restituisce d[key] anche se key è 'a/b/c' o 'a.b.c'.
    Se il percorso non esiste, ritorna None.
    """
    if not key:
        return None
    if key in d:
        return d[key]
    parts: Sequence[str] = key.replace(".", "/").split("/")
    cur: Any = d
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


# =============================================================================
#  Costruzione builder TFDS: directory (locale o GCS) oppure nome registrato
# =============================================================================
def _make_builder(name_or_dir: str, data_dir: str | None = None):
    """
    1) Se 'name_or_dir' è un path (esiste su disco o contiene '://'), prova builder_from_directory.
    2) Altrimenti prova builder(name, data_dir=...).
    Nota: anche con data_dir, serve che il builder sia REGISTRATO (pkg open-x-embodiment).
    """
    # caso directory (locale o GCS)
    try:
        if '://' in name_or_dir or name_or_dir.startswith('/') or os.path.exists(name_or_dir):
            return tfds.builder_from_directory(name_or_dir)
    except Exception:
        pass

    # caso nome registrato
    try:
        return tfds.builder(name_or_dir, data_dir=data_dir)
    except Exception as e:
        raise RuntimeError(
            f"TFDS builder not found for '{name_or_dir}'. "
            f"Assicurati di aver installato 'open-x-embodiment' e di aver settato TFDS_DATA_DIR.\n"
            f"data_dir={data_dir!r}. Original error: {e}"
        )


# =============================================================================
#  Iteratore episodi RLDS (come nel notebook OXE)
# =============================================================================
def iterate_episodes(name_or_dir: str, split: str, data_dir: str | None = None) -> Generator[Dict[str, Any], None, None]:
    """
    Restituisce un generatore di EPISODI TFDS (OXE/RLDS) come dict numpy-friendly.
    In OXE un episodio ha tipicamente 'steps/observation/...', 'steps/action/...', ecc.

    Genera EPISODI TFDS (RLDS). Richiede che il builder sia registrato.
    """
    b = _make_builder(name_or_dir, data_dir=data_dir)
    ds = b.as_dataset(split=split, read_config=tfds.ReadConfig(try_autocache=False))
    ds = tfds.as_numpy(ds)
    for episode in ds:
        yield episode

# =============================================================================
#  Conversione immagine → uint8 RGB
# =============================================================================
def to_uint8_rgb(x: Any) -> np.ndarray:
    """
    Converte una singola immagine (H,W,C) o una sequenza (T,H,W,C) in uint8 RGB.
    Float in [0,1] viene scalato, float >1 viene clippato a [0,255].
    """
    arr = np.asarray(x)
    if arr.ndim not in (3, 4):
        raise ValueError(f"Unsupported image shape: {arr.shape}")
    if np.issubdtype(arr.dtype, np.floating):
        if arr.max() <= 1.0:
            arr = (arr * 255.0).clip(0, 255)
        else:
            arr = arr.clip(0, 255)
        arr = arr.astype(np.uint8)
    elif arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    return arr


# =============================================================================
#  Risoluzione immagini e istruzioni in stile RLDS
# =============================================================================
_DEFAULT_IMAGE_CANDIDATES = [
    "steps/observation/image",  # caso standard OXE
    "steps/image",              # alcune varianti
    "image",                    # fallback
]

def _resolve_image_array(episode: Dict[str, Any], image_key: str) -> np.ndarray:
    """
    Trova l'array immagini. Se image_key non esiste, prova candidati standard.
    Ritorna un np.ndarray (H,W,C) o (T,H,W,C).
    """
    arr = _get_by_path(episode, image_key) if image_key else None
    if arr is None:
        for cand in _DEFAULT_IMAGE_CANDIDATES:
            arr = _get_by_path(episode, cand)
            if arr is not None:
                break
    if arr is None:
        raise KeyError(f"Nessuna immagine trovata. key='{image_key}', candidati={_DEFAULT_IMAGE_CANDIDATES}")
    return np.asarray(arr)

def _first_nonempty_string(seq) -> Optional[str]:
    for x in seq:
        if isinstance(x, (bytes, bytearray)):
            try:
                x = x.decode("utf-8")
            except Exception:
                x = str(x)
        elif hasattr(x, "item"):
            x = x.item()
        if isinstance(x, str) and x.strip():
            return x.strip()
    return None

def resolve_instruction(episode: Dict[str, Any], instruction_key: str) -> Optional[str]:
    """
    Recupera l'istruzione:
      1) prova a livello EPISODIO (es. 'natural_language_instruction', 'task/language_instruction');
      2) in fallback prova a livello STEPS (es. 'steps/...'): prima stringa non vuota.
    Restituisce None se non trovata (alcuni dataset non la contengono).
    """
    # episodio-level
    txt = _get_by_path(episode, instruction_key) if instruction_key else None
    if txt is not None:
        if isinstance(txt, (bytes, bytearray)):
            try:
                txt = txt.decode("utf-8")
            except Exception:
                txt = str(txt)
        elif hasattr(txt, "item"):
            txt = txt.item()
        if isinstance(txt, str) and txt.strip():
            return txt.strip()

    # steps-level
    step_key = f"steps/{instruction_key}" if instruction_key else None
    if step_key:
        arr = _get_by_path(episode, step_key)
        if arr is not None:
            arr = np.asarray(arr)
            if arr.ndim == 1:
                cand = _first_nonempty_string(list(arr))
                if cand:
                    return cand

    # alias comuni di fallback
    for cand in ("natural_language_instruction", "task/language_instruction"):
        txt = _get_by_path(episode, cand)
        if isinstance(txt, (bytes, bytearray)):
            try:
                txt = txt.decode("utf-8")
            except Exception:
                txt = str(txt)
        elif hasattr(txt, "item"):
            txt = txt.item()
        if isinstance(txt, str) and txt.strip():
            return txt.strip()

    for cand in ("steps/natural_language_instruction", "steps/task/language_instruction"):
        arr = _get_by_path(episode, cand)
        if arr is not None:
            arr = np.asarray(arr)
            if arr.ndim == 1:
                cand_txt = _first_nonempty_string(list(arr))
                if cand_txt:
                    return cand_txt
    return None


# =============================================================================
#  Dump diagnostico attributi
# =============================================================================
def dump_attributes(example: Dict[str, Any], out_dir: str) -> str:
    """
    Scrive attributes.json con chiavi e tipi serializzabili.
    Non salva tensori completi: per np.ndarray memorizza solo shape e dtype.
    """
    os.makedirs(out_dir, exist_ok=True)

    def _to_serializable(obj: Any):
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return {"__ndarray__": True, "shape": list(obj.shape), "dtype": str(obj.dtype)}
        if isinstance(obj, (bytes, bytearray)):
            try:
                return obj.decode("utf-8")
            except Exception:
                return str(obj)
        if isinstance(obj, dict):
            return {k: _to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_serializable(v) for v in obj]
        return obj

    path = os.path.join(out_dir, "attributes.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_to_serializable(example), f, ensure_ascii=False, indent=2)
    return path


# =============================================================================
#  Dump episodio: frame JPEG, preview.gif, instruction.txt
# =============================================================================
def dump_episode_rlds(
    episode: Dict[str, Any],
    out_dir: str,
    image_key: str,
    instruction_key: str,
    max_frames: int,
) -> Dict[str, Any]:
    """
    Estrae i frame da un EPISODIO RLDS e li salva in out_dir/raw_frames.
    Crea preview.gif se i frame salvati sono ≥2.
    Se trova un'istruzione testuale, crea out_dir/instruction.txt.
    Ritorna un sommario con conteggi e flag.
    """
    os.makedirs(out_dir, exist_ok=True)
    frames_dir = os.path.join(out_dir, "raw_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 1) immagini
    arr = _resolve_image_array(episode, image_key)
    arr = to_uint8_rgb(arr)
    if arr.ndim == 3:   # (H,W,C) → singolo frame
        arr = arr[None, ...]
    T = min(arr.shape[0], max_frames)

    saved = 0
    for t in range(T):
        img = Image.fromarray(arr[t])
        fp = os.path.join(frames_dir, f"frame_{t:04d}.jpg")
        img.save(fp, quality=95)
        saved += 1

    # 2) GIF
    gif_flag = False
    if saved >= 2:
        gif_path = os.path.join(out_dir, "preview.gif")
        imgs = [Image.fromarray(arr[t]) for t in range(T)]
        imgs[0].save(gif_path, save_all=True, append_images=imgs[1:], duration=120, loop=0)
        gif_flag = True

    # 3) instruction
    instr_flag = False
    instr = resolve_instruction(episode, instruction_key)
    if instr:
        with open(os.path.join(out_dir, "instruction.txt"), "w", encoding="utf-8") as f:
            f.write(instr)
        instr_flag = True

    return {
        "frames_saved": saved,
        "preview_gif": gif_flag,
        "instruction": instr_flag,
        "out_dir": out_dir,
    }
