"""
Frame extraction stage (Step 2A).

- Reads a video file with OpenCV.
- Samples frames at approximately `fps_target`.

Key design principles:
- We compute a "window id" as floor(time_sec / window_seconds)
- We accumulate candidates for the current window into a small in-memory bucket
- When the window changes (or at the end-of-file) we flush the bucket:
    sort by score (desc), keep the top-k, write JPEG + metrics for those, drop the rest
- We still apply the sharpness gate (skip blurry frames images early)


- Notes on metrics for each sampled frame:
    sharpness   = variance of Laplacian (focus measure)
    brightness  = mean of V channel in HSV
    contrast    = standard deviation of Y channel in YCrCb
    score       = 0.7 * sharpness + 0.3 * contrast (let's keep this at the moment)
- Writes each frame to JPEG and its metrics to JSON.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Sequence

import cv2  # OpenCV
import numpy as np

@dataclass
class _Candidate:
    """
    In-memory record for a frame that belongs to the current temporal window.
    We keep both the raw image (for writing JPEG later) and the computed metrics
        
    Attributes:
    frame_idx: int 
        Absolute index of the frame in the decoded stream
    time_sec: float
        Presentation time of the frame in seconds (frame_idx / fps)
    img_bgr : np.ndarray
        The actual image (BGR). Stored only within the current window
    score: float
        Quality score used for ranking in the window
    sharpness, brightness, contrast: float
        Raw metrics components
    """

    frame_idx: int
    time_sec: float
    img_bgr: np.ndarray
    score: float
    sharpness: float
    brightness: float
    contrast: float


def compute_metrics(img_bgr):
    """ Compute quality metrics for BGR frame"""
    # Sharpness : variance of Laplacian
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Intuition: the Laplacian responds strongly to edges and fine detail; 
    # a sharp image has many strong, rapidly changing gradients, 
    # so the variance of Laplacian values is high. 
    # Motion blur or defocus suppress high frequencies, driving this variance down.
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Brightness : mean of V channel in HSV
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # extremely dark or blown-out frames tend to be low-quality for downstream tasks
    brightness = float(hsv[..., 2].mean())

    # Contrast: std-dev of Y channel
    ycrcb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)
    # Intuition: contrast measures how spread out the luminance is. 
    # Strong lighting, shadows, and varied textures increase this number; 
    # flat, uniform regions decrease it.
    contrast = float(ycrcb[..., 0].std())

    # heuristic that must be assessed (maybe we need something else)
    score = 0.7 * sharpness + 0.3 * contrast

    return dict(
        sharpness=sharpness,
        brightness=brightness,
        contrast=contrast,
        score=score
    )


def _flush_window(
        bucket: List[_Candidate],
        out_dir: Path,
        next_id: int,
        keep_top_per_window: int,
) -> int:
    """
    Flush the current window's candidates
    - sort by score (desc)
    - keep top-K
    - write JPEG and metrics for each candidate
    Return the number of frames written (i.e. actually saved)

    Images for non-kept candidates are not persisted
    """

    if not bucket:
        return 0
    
    # Sort candidates by score descending and pick top-k
    bucket.sort(key=lambda c: c.score, reverse=True)
    kept = bucket[: max(1, keep_top_per_window)]

    # Write each kept candidate
    written = 0
    for i, cand in enumerate(kept):
        name = f"{next_id + i:06d}"
        img_path = out_dir / f"{name}.jpg"
        json_path = out_dir / f"{name}.metrics.json"

        # jpeg with a reasonable quality for reproducible experiments
        cv2.imwrite(str(img_path), cand.img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        metrics = {
            # Including time_sec is a forward-looking convenience for downstream stages.
            "time_sec": float(cand.time_sec),
            "score": float(cand.score),
            "sharpness": float(cand.sharpness),
            "brightness": float(cand.brightness),
            "contrast": float(cand.contrast)
        }
        json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        written += 1

    return written
    


def extract_video_frames(
        video_path: Path, 
        out_dir: Path, 
        fps_target: float = 2.0, 
        window_seconds: float = 2.0,
        keep_top_per_window: int = 1,
        sharpness_min: float = 50.0,
        limit_frames: int = -1,
        logger=None
) -> int:
    """
    Extract frames with temporal windowing and quality gating.

    Parameters
    ----------
    video_path : Path
        Input video path (.mp4).
    out_dir : Path
        Where to write NNNNNN.jpg and NNNNNN.metrics.json files.
    fps_target : float
        Approximate sampling rate (frames per second). We realize this by
        decoding 1 frame every 'step = round(fps / fps_target)' source frames.
    window_seconds : float
        Length of each temporal window. We keep only the top-K frames per window.
    keep_top_per_window : int
        How many frames to keep per window (K).
    sharpness_min : float
        Discard frames with sharpness below this threshold to avoid obvious blur.
    limit_frames : int
        If > 0, stop after writing this many frames (useful for quick experiments).
    logger : optional logging.Logger
        If provided, we write informative messages; otherwise we remain silent.

    Returns
    -------
    int
        The number of frames actually written to disk.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video file {video_path}")
    
    # If FPS is not available, fall back to 30.0 to avoid division by zero.
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Subsample by an integer step so that sampled_fps ≈ fps_target.
    step = max(1, int(round(fps / max(fps_target, 1e-6))))

    if logger:
        logger.info(f"[extract] fps={fps:.3f}, step={step}, window_seconds={window_seconds}, top_per_window={keep_top_per_window}")

    frame_idx = -1 # absolute index in the decided stream
    produced_total = 0 # how many frames written so far
    next_id = 0  # next ID to use for output file naming

    current_window_id = -1 # which temporal window we are currently filling
    window_bucket: List[_Candidate] = [] # candidates for the current window

    try:
        while True:
            ok = cap.grab()
            if not ok: 
                # End of file: flush the last window and stop.
                produced_total += _flush_window(window_bucket, out_dir, next_id, keep_top_per_window)
                break

            frame_idx += 1
            if frame_idx % step != 0:
                # Not a sample point, skip decoding to save time
                continue

            ok, frame = cap.retrieve()
            if not ok:
                # Rare recording failure, skip this index
                continue

            # Compute the presentation time and the window id this frame belongs to
            time_sec = frame_idx / fps
            win_id = int(math.floor(time_sec / max(window_seconds, 1e-6)))

            # if we moved to a new window, flush the previous one first.
            if current_window_id !=-1 and win_id != current_window_id:
                wrote = _flush_window(window_bucket, out_dir, next_id, keep_top_per_window)
                produced_total += wrote
                next_id += wrote
                window_bucket.clear()
            
            current_window_id = win_id
            
            # Compute quality metrics for this candidate frame.
            m = compute_metrics(frame)

            # Quality gate: avoid storing obviously blurry content.
            if m["sharpness"] < sharpness_min:
                if logger and (frame_idx % (step * 10) == 0):
                    logger.info(f"[extract] skip (blur) @t={time_sec:.2f}s sharpness={m['sharpness']:.1f} < {sharpness_min}")
                continue

            # Accumulate the candidate in the current window bucket.
            window_bucket.append(
                _Candidate(
                    frame_idx=frame_idx,
                    time_sec=time_sec,
                    img_bgr=frame,
                    score=float(m["score"]),
                    sharpness=float(m["sharpness"]),
                    brightness=float(m["brightness"]),
                    contrast=float(m["contrast"]),
                )
            )

            # Optional global limit: stop soon for quick tests.
            if 0 < limit_frames <= produced_total:
                # We still flush the bucket to ensure we write the best frames so far.
                produced_total += _flush_window(window_bucket, out_dir, next_id, keep_top_per_window)
                window_bucket.clear()
                break

    finally:
        cap.release()
    if logger:
        logger.info(f"[extract] done, wrote {produced_total} frames to {out_dir}")

    return produced_total