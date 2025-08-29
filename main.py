"""
Minimal pipeline package marker
We will add real modules step by step
"""

from __future__ import annotations
from pathlib import Path
import sys
import argparse
import json
import platform
import getpass
from datetime import datetime
import logging

# import pipeline packet version if available
try:
    from pipeline import __version__ as PIPELINE_VERSION
except Exception:
    PIPELINE_VERSION = "0.0-dev"

# create parser with subcommands
def build_parser() -> argparse.ArgumentParser:
    """
    Build the top-level parser and register subcommands.
    Subcommands:
      - run
      - extract
      - detect
    """
    # Top-level parser (keep this in a variable named 'parser' to avoid confusion)
    parser = argparse.ArgumentParser(prog="main", description="OXE-BT-PIPELINE CLI")

    # Container for subcommands; 'required=True' forces the user to pick one
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- run subcommand ---
    sp_run = sub.add_parser("run", help="End-to-end orchestrator (creates layout, manifest, stubs)")
    sp_run.add_argument("--out", type=Path, required=True, help="Output episode directory: out/<episode>")
    sp_run.add_argument("--desc", type=str, default="", help="Episode short description")
    sp_run.add_argument("--use_vlm", type=str, default="false", help="true/false (string for now)")
    sp_run.add_argument("--dry_run", action="store_true", help="No heavy work, just a stub in this step")

    # --- extract subcommand ---
    sp_extract = sub.add_parser("extract", help="Extract frames from video")
    sp_extract.add_argument("--video", type=Path, required=True, help="Input video file")
    sp_extract.add_argument("--out", type=Path, required=True, help="Output episode directory (root of the episode)")
    sp_extract.add_argument("--fps_target", type=float, default=2.0, help="Target sampling FPS (approximate)")
    sp_extract.add_argument("--window_seconds", type=float, default=2.0, help="Window length in seconds")
    sp_extract.add_argument("--keep_top_per_window", type=int, default=1, help="How many frames to keep per window")
    sp_extract.add_argument("--sharpness_min", type=float, default=50.0, help="Drop frames below this sharpness")
    sp_extract.add_argument("--limit_frames", type=int, default=-1, help="If >0, stop after writing this many frames")

    # --- detect subcommand ---
    sp_detect = sub.add_parser("detect", help="Run object detection over extracted frames")
    sp_detect.add_argument("--out", type=Path, required=True, help="Output episode directory: out/<episode>")
    sp_detect.add_argument("--conf_threshold", type=float, default=0.25, help="Confidence threshold (0..1)")
    sp_detect.add_argument("--iou_threshold", type=float, default=0.50, help="IoU threshold for NMS (0..1)")
    sp_detect.add_argument("--allowed_nouns", type=str, default="", help='Comma-separated whitelist, e.g. "mug,table"')
    sp_detect.add_argument("--device", type=str, default="cpu", choices=("cpu", "cuda"), help="Inference device")

    # Always return the top-level parser, not a subparser
    return parser


def ensure_episode_layout(ep_dir: Path) -> None:
    """
    Create the structure:
       <ep_dir>/
         frames/
         detections/
         vlm/
    Do not raise errors if it already exists  
    """

    ep_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("frames", "detections", "vlm"):
        (ep_dir / sub).mkdir(parents=True, exist_ok=True)



def setup_logger(ep_dir: Path) -> logging.Logger:
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(ep_dir / "pipeline.log", mode="a", encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

# The manifest.json acts as an identity card for each pipeline run.
# It records:
#   - Reproducibility: allows rerunning with exactly the same parameters.
#   - Traceability: every episode folder has its own manifest, so you can
#     always track how it was generated.
#   - Sharing: collaborators can see which models/parameters were used
#     without asking, just by opening the manifest.
#   - Debugging: helps diagnose issues related to Python version, device,
#     or different parameter settings.
def write_manifest(ep_dir: Path, args: argparse.Namespace) -> None:
    """
    Write manifest.json (minimal), keeping only reproducible info and no heavy library. 
    'device' is 'cpu' at this moment.
    """
    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user": getpass.getuser(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "device": "cpu",  # niente torch ancora; verrà aggiornato più avanti
        "params": {
            "desc": args.desc,
            "use_vlm": args.use_vlm,      # lascio stringa; parser booleano arriverà dopo
            "dry_run": bool(args.dry_run)
        },
        "models": {
            "detector": None,
            "vlm": None
        }
    }
    path = ep_dir / "manifest.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return path



# main() separates "parser construction" from the "execution logic" as a good practice for tests
def main(argv: list[str] | None = None) -> int:
    """
    Main entry-point called by 'python -m main ...'
    Parses args and print what we got.
    """

    argv = argv if argv is not None else sys.argv[1:]
    print(f"sys.argv", sys.argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "run":
        print("[RUN] parsed arguments:")
        print(f"    out     = {args.out}")
        print(f"    desc    = {args.desc}")
        print(f"    use_vlm = {args.use_vlm}")
        print(f"    dry_run = {args.dry_run}")
        print("\nOk: the CLI skeleton is working. Next step we will create files")

        ep_dir = args.out
        ensure_episode_layout(ep_dir)
        man_path = write_manifest(ep_dir, args)

        print(f"[RUN] Episode dir: {ep_dir}")
        print(f"[RUN] Manifest path: {man_path}")
        if args.dry_run:
            print("[RUN] Dry run: structur and manifest created, nothing else to execute")
        else:
            print("[RUN] Nothing else to execute")
        return 0
    
    if args.cmd == "extract":
        #Lazily import the implementation to keep main.py lightweight
        from pipeline.frame_select import extract_video_frames
        ep = args.out
        ensure_episode_layout(ep)
        logger = setup_logger(ep)
        frames_dir = ep / "frames"

        logger.info(
            f"extract: video={args.video} fps_target={args.fps_target} "
            f"window_seconds={args.window_seconds} keep_top_per_window={args.keep_top_per_window} "
            f"sharpness_min={args.sharpness_min} limit_frames={args.limit_frames}"
        )
        written = extract_video_frames(
            video_path=args.video,
            out_dir=frames_dir,
            fps_target=args.fps_target,
            window_seconds=args.window_seconds,
            keep_top_per_window=args.keep_top_per_window,
            sharpness_min=args.sharpness_min,
            limit_frames=args.limit_frames,
            logger=logger,
        )
        logger.info(f"extract: wrote {written} frames -> {frames_dir}")
        print(f"[EXTRACT] Wrote {written} frames in {frames_dir.resolve()}")
        return 0
    if args.cmd == "detect":
        # Import here so the rest of main.py does not require ultralytics installed
        from pipeline.detect import detect_episode_frames

        ep = args.out
        ensure_episode_layout(ep)         # make sure detections/ exists, etc.
        logger = setup_logger(ep)         # write to out/<episode>/pipeline.log
        frames_dir = ep / "frames"        # where JPEGs live
        det_dir = ep / "detections"       # where we will write JSONs

        # Transform "mug,table" → ["mug", "table"]; or None if string is empty/whitespace
        allowed = [s.strip() for s in args.allowed_nouns.split(",")] if args.allowed_nouns.strip() else None

        # Log the configuration so you can reproduce later
        logger.info(
            f"detect: frames_dir={frames_dir} conf={args.conf_threshold} iou={args.iou_threshold} "
            f"allowed={allowed} device={args.device}"
        )

        # Run the detection stage; this will write one JSON per frame and a vocabulary.json
        processed = detect_episode_frames(
            frames_dir=frames_dir,
            det_dir=det_dir,
            conf_threshold=args.conf_threshold,
            iou_threshold=args.iou_threshold,
            allowed_nouns=allowed,
            device=args.device,
            logger=logger,
        )

        # Mirror a concise summary to stdout as well
        logger.info(f"detect: processed {processed} images -> {det_dir}")
        print(f"[DETECT] Wrote {processed} detection JSON files in {det_dir.resolve()}")
        return 0

    parser.error(f"Unknown command: {args.cmd}")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())


    