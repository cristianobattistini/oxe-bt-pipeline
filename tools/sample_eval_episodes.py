import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.dataset_proposer_agentic.input_sources.oxe_episodes import iter_oxe_episodes


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Sample up to N episodes per dataset from out_temp for evaluation."
    )
    ap.add_argument("--out-root", default="out_temp", help="Path to exported episodes root.")
    ap.add_argument(
        "--datasets",
        default="",
        help="Comma-separated dataset folder names to include (optional).",
    )
    ap.add_argument("--max-per-dataset", type=int, default=2, help="Max episodes to sample per dataset.")
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for reproducible sampling.")
    ap.add_argument(
        "--allow-missing-contact-sheet",
        action="store_true",
        help="Allow episodes without final_selected/contact_sheet.* (not recommended).",
    )
    ap.add_argument(
        "--output",
        default="eval_samples.jsonl",
        help="Output JSONL with dataset_id/episode_id/instruction/frame0/contact_sheet.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    out_root = args.out_root
    max_per_dataset = max(0, int(args.max_per_dataset))
    rng = random.Random(args.seed)
    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]

    # Collect candidates per dataset.
    per_dataset: Dict[str, List[Dict[str, Any]]] = {}
    for ep in iter_oxe_episodes(
        out_root,
        datasets=datasets or None,
        require_contact_sheet=not args.allow_missing_contact_sheet,
    ):
        ds = str(ep["dataset_id"])
        per_dataset.setdefault(ds, []).append(ep)

    if not per_dataset:
        raise SystemExit(
            "No episodes found. Check --out-root and whether contact sheets exist. "
            "If needed run: python processing/tools/generate_contact_sheets_out.py --out-root out_temp"
        )

    samples: List[Dict[str, Any]] = []
    for ds, eps in sorted(per_dataset.items()):
        rng.shuffle(eps)
        picked = eps[:max_per_dataset] if max_per_dataset else []
        for ep in picked:
            frames = ep.get("frames") or []
            frame0 = frames[0] if isinstance(frames, list) and frames else None
            samples.append(
                {
                    "dataset_id": ep["dataset_id"],
                    "episode_id": ep["episode_id"],
                    "instruction": ep["instruction"],
                    "frame0": frame0,
                    "contact_sheet": ep.get("contact_sheet"),
                    "final_selected_dir": ep.get("final_selected_dir"),
                }
            )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in samples:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[OK] wrote {len(samples)} samples to {out_path} ({len(per_dataset)} datasets).")


if __name__ == "__main__":
    main()
