# pipeline/detect.py
"""
Object Detection Stage — Step 3 (YOLO if available, robust fallback otherwise).

Purpose
-------
Given the frames extracted in earlier steps (under out/<episode>/frames/*.jpg),
this module runs object detection and writes, for *each* frame, a JSON file
out/<episode>/detections/NNNNNN.json following the required schema:

[
  {
    "frame_id": "NNNNNN",
    "det_id": 0,
    "noun": "person",           # lowercase label
    "score": 0.92,              # confidence ∈ [0,1]
    "bbox": [x1, y1, x2, y2],   # floats, pixel coordinates
    "source": "yolov8n"
  },
  ...
]

Additionally, it maintains a vocabulary.json summarizing detections across the episode:
{
  "vocab": {
    "person": {"count": 10, "avg_score": 0.71},
    "cup":    {"count":  3, "avg_score": 0.64}
  },
  "stats": {
    "total_images": 42,
    "last_updated": "YYYY-MM-DDTHH:MM:SS"
  }
}

Design Goals
------------
- CPU-first: if Ultralytics YOLO is installed, we run it on CPU by default;
  you can pass device="cuda" if you have GPU support.
- Best-effort: if YOLO is not installed (or any import/inference error occurs),
  we still write valid empty detection JSONs so the pipeline remains runnable.
- Sanity checks: scores are clamped to [0,1]; bounding boxes are clamped to
  image bounds and discarded if degenerate; labels are lowercased.
- Deterministic, clean artifacts: one JSON per frame + a canonical vocabulary.json.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from datetime import datetime
import json

import cv2  # OpenCV for image loading and shape
import numpy as np



# ---------------------------------------------------------------------------
# YOLO: optional dependency (Ultralytics).
# We keep imports *inside* helper functions so that importing this module does
# not fail on systems without Ultralytics installed.
# ---------------------------------------------------------------------------

def _load_yolo_model(weights: str = "yolov8n.pt", device: str = "cpu"):
    """
    Try to import and instantiate Ultralytics Yolo. On success, return the model;
    otherwise return None
    """
    try:
        from ultralytics import YOLO
    except Exception:
        return None
    
    try:
        model = YOLO(weights)
        model._oxe_device = device  # attach user-requested device string
        return model
    except Exception:
        return None
    

def _yolo_predict(model, img_bgr: np.ndarray, conf: float, iou: float):
    """
    Run YOLO inference on one BGR image, returning raw triplets:
    List[ (label:str, score: float, bbox: [x1,y1,x2,y2]) ]

    Any exception results in an empty list
    """
    try:
        device = getattr(model, "_oxe_device", "cpu")
        results = model.predict(img_bgr, conf=conf, iou=iou, device=device, verbose=False)
        if not results:
            return []
        r = results[0]
        names = getattr(model, "names", {})  # mapping from class index to label 
        out = []

        # Extract tensors from r.boxes, convert to numpy on CPU for portability
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            return []


        xyxy = boxes.xyxy.detach().cpu().numpy()       # shape: [N, 4]
        confs = boxes.conf.detach().cpu().numpy()      # shape: [N]
        clsi = boxes.cls.detach().cpu().numpy().astype(int)  # shape: [N], ints

        # Iterate over detections, convert to plain Python values
        for k in range(xyxy.shape[0]):
            label = str(names.get(int(clsi[k]), int(clsi[k]))).lower()  # ensure lowercase
            score = float(confs[k])                                      # float in [0,1] typically
            x1, y1, x2, y2 = [float(v) for v in xyxy[k].tolist()]        # four floats
            out.append((label, score, [x1, y1, x2, y2]))
        return out
    except Exception:
        return []  # any error → treat as “no detections” for this image

    

# ---------------------------------------------------------------------------
# Utility functions: clamping scores and bboxes, listing frames.
# ---------------------------------------------------------------------------

def _clamp01(x: float) -> float:
    """Clamp a float to the inclusive range [0, 1]."""
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _clamp_bbox(x1: float, y1: float, x2: float, y2: float, w: int, h: int) -> Optional[Tuple[float, float, float, float]]:
    """
    Clamp a bounding box to image bounds and enforce coordinate ordering.

    Parameters
    ----------
    x1, y1, x2, y2 : float
        Possibly unordered / out-of-range coordinates.
    w, h : int
        Image width and height.

    Returns
    -------
    (x1, y1, x2, y2) with 0 <= x1 < x2 <= (w-1), 0 <= y1 < y2 <= (h-1),
    or None if the clamped box is degenerate (zero or negative area).
    """
    # Clamp to [0, w-1] x [0, h-1]
    x1 = max(0.0, min(float(w - 1), x1))
    y1 = max(0.0, min(float(h - 1), y1))
    x2 = max(0.0, min(float(w - 1), x2))
    y2 = max(0.0, min(float(h - 1), y2))

    # Ensure correct ordering
    # Ensure left<right and top<bottom (swap if they came reversed)
    x1_, x2_ = (x1, x2) if x1 <= x2 else (x2, x1)
    y1_, y2_ = (y1, y2) if y1 <= y2 else (y2, y1)

    # Drop degenerate boxes
    # Reject boxes with no area (avoid downstream divide-by-zero or drawing issues)
    if (x2_ - x1_) <= 1e-6 or (y2_ - y1_) <= 1e-6:
        return None
    return (x1_, y1_, x2_, y2_)

def _list_frames(frames_dir: Path) -> List[Path]:
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    files: List[Path] = []
    for pat in patterns:
        files.extend(frames_dir.glob(pat))
    return sorted(set(files))




# =============================================================================
# PUBLIC API — process all frames and write detections + vocabulary.json
# =============================================================================

def detect_episode_frames(
    frames_dir: Path,
    det_dir: Path,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.50,
    allowed_nouns: Optional[Sequence[str]] = None,
    device: str = "cpu",
    logger=None,
) -> int:
    """
    Run detection over frames_dir/*.jpg and write one JSON per frame into det_dir.
    Also write a vocabulary.json that summarizes label counts and average scores.

    Arguments:
      frames_dir        : path to 'out/<episode>/frames'
      det_dir           : path to 'out/<episode>/detections' (created if missing)
      conf_threshold    : confidence threshold passed to YOLO (0..1)
      iou_threshold     : IoU threshold for NMS passed to YOLO (0..1)
      allowed_nouns     : optional whitelist; keep detections only for these labels
      device            : 'cpu' (default) or 'cuda'
      logger            : optional logger for info/warnings

    Returns:
      processed         : number of images for which we wrote a per-frame JSON
    """
    # Ensure output directory exists
    det_dir.mkdir(parents=True, exist_ok=True)

    # Normalize the whitelist to a lowercase set for O(1) memberhsip tests
    allowed: Optional[set] = None
    if allowed_nouns:
        allowed = { str(s).strip().lower() for s in allowed_nouns if s and str(s).strip() }
    
    # Try loading YOLO once; if it fails, we will produce empty detections
    model = _load_yolo_model(device=device)
    yolo_ok = model is not None
    if logger:
        logger.info(f"[detect] YOLO model load {'succeeded' if yolo_ok else 'failed'}, device={device}")

    # List frames to process; if none found, we preder to fail early with a clear error
    frames = _list_frames(frames_dir)
    if not frames:
        raise FileNotFoundError(f"No frames found in {frames_dir}")
    
    # Prepare accumulators for the vocabulary summary
    vocab_counts: Dict[str,int] = {} # label -> number of occurences
    vocab_score_sum: Dict[str,float] = {} # label -> sum of scores (for average)

    processed = 0  # count how many per-frame JSONs we wrote

  # main loop: one iteration per image file
    for fpath in frames:
        # Read the image from disk; None means unreadable/corrupt
        img_bgr = cv2.imread(str(fpath), cv2.IMREAD_COLOR)
        base = fpath.stem  # e.g., "000012" (used for output file names and frame_id)

        if img_bgr is None:
            if logger:
                logger.warning(f"[detect] cannot read image: {fpath.name} (writing empty [] for this frame)")
            # Still write an empty JSON so 'processed' reflects this file
            (det_dir / f"{base}.json").write_text("[]", encoding="utf-8")
            processed += 1
            continue  # move on to the next file

        # Collect basic shape info for clamping bboxes
        h, w = img_bgr.shape[:2]

        # Run YOLO if we have a model; otherwise pretend it returned zero detections
        raw = _yolo_predict(model, img_bgr, conf=conf_threshold, iou=iou_threshold) if yolo_ok else []

        # We will build a list of dictionary objects matching the required schema
        dets: List[dict] = []
        det_id = 0  # monotonically increasing id per frame

        # Convert raw tuples into schema-compliant dicts with sanity checks
        for (label, score, bbox) in raw:
            noun = label.lower()  # ensure lowercase for stable vocabulary keys

            # if a whitelist is provided, drop anything not in the list
            if allowed is not None and noun not in allowed:
                continue

            # Clamp score to [0,1]; clamp box to image bounds; drop degenerate boxes
            score = _clamp01(float(score))
            clamped = _clamp_bbox(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]), w, h)
            if clamped is None:
                continue

            x1, y1, x2, y2 = clamped

            # Append a detection record following the DetectionsJSON schema
            dets.append({
                "frame_id": base,
                "det_id": det_id,
                "noun": noun,
                "score": score,
                "bbox": [x1, y1, x2, y2],
                "source": "yolov8n" if yolo_ok else "none",
            })
            det_id += 1

            # Update vocabulary aggregations for nouns we actually kept
            vocab_counts[noun] = vocab_counts.get(noun, 0) + 1
            vocab_score_sum[noun] = vocab_score_sum.get(noun, 0.0) + score

    # Persist per-frame detections (empty list is still a valid artifact)
    out_json = det_dir / f"{base}.json"
    out_json.write_text(json.dumps(dets, indent=2), encoding="utf-8")
    processed += 1


    # Build the vocabulary.json summary from the accumulators
    vocab_obj = {
        "vocab": {
            noun: {
                "count": vocab_counts[noun],
                "avg_score": (vocab_score_sum[noun] / max(1, vocab_counts[noun])),
            }
            for noun in sorted(vocab_counts.keys())  # sort keys for stable diffs
        },
        "stats": {
            "total_images": processed,  # number of per-frame JSONs written
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        },
    }

    # Write vocabulary.json beside the per-frame JSONs
    (det_dir / "vocabulary.json").write_text(json.dumps(vocab_obj, indent=2), encoding="utf-8")

    # Optional log at the end for quick inspection
    if logger:
        logger.info(f"[detect] processed={processed} images, nouns={len(vocab_counts)}")

    # Return how many images we processed (useful for tests and logs)
    return processed