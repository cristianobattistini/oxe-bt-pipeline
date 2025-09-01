from __future__ import annotations
import pathlib

import config
from loader import load_first_episode, dump_episode, dump_attributes

def _out_dir(root: str, idx: int) -> str:
    return str(pathlib.Path(root) / f"episode_{idx:03d}")

def main() -> None:
    ds = config.dataset
    split = config.split
    out_root = config.out_root

    # Chiavi esplicite (strict, stile Colab)
    image_key = getattr(config, "image_key", "image")
    instruction_key = getattr(config, "instruction_key", "natural_language_instruction")

    max_frames = int(config.max_frames)

    pathlib.Path(out_root).mkdir(parents=True, exist_ok=True)

    epi = load_first_episode(ds, split)
    if epi is None:
        print("[WARN] Nessun episodio trovato.")
        return

    ep_dir = _out_dir(out_root, 0)
    summary = dump_episode(epi, ep_dir, image_key, instruction_key, max_frames)
    attrs_path = dump_attributes(epi, ep_dir)

    print(
        f"[OK] Episode 000 → {summary['frame_count']} frame(s), "
        f"instruction={'yes' if summary['instruction_present'] else 'no'}, "
        f"gif={'yes' if summary['gif'] else 'no'}; dir={ep_dir}"
    )
    print(f"[OK] Attributi completi: {attrs_path}")

if __name__ == "__main__":
    main()
