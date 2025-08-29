# Frame Extraction & Run Metadata (Steps 1B–2B)

This document explains the **frame extraction** part of the pipeline, together with the run metadata and logging introduced before the extractor. It covers:
- Step 1B: episode layout and `manifest.json`.
- Step 1C: `pipeline.log` and stub artifacts.
- Step 2A: real frame extraction and metrics.
- Step 2B: temporal windowing and top-K per window.

The goal is to understand what each file does, why the algorithm is structured this way, how to run it reliably, and how to check that outputs are sensible before moving to detection (YOLO) and VLM semantics.

---

## 1) What gets created on disk and why

When you run `python -m main run ...` or `python -m main extract ...`, the pipeline works in an **episode directory** named `out/<episode>`. Inside it you will see three subfolders and a couple of control files:

- `frames/`: where JPEG frames and their per-frame metrics JSONs are written.
- `detections/`: reserved for object detection outputs (to be filled later).
- `vlm/`: reserved for CLIP/caption scores (to be filled later).
- `manifest.json`: a compact identity card for the run (version, params, device, etc.).
- `pipeline.log`: a timestamped log for traceability and debugging.

This structure is idempotent: running the command again does not break if the folders already exist.

### `manifest.json` (run identity)
The manifest records reproducibility and traceability metadata. It contains the pipeline version, timestamp, Python version, OS information, a “device” hint, and the CLI parameters used for that run. When you later attach real models (e.g., YOLO or CLIP), the manifest is where you will also record model names and versions. Having this file next to the outputs lets you answer “how was this generated?” without opening the code.

### `pipeline.log` (audit trail)
The log mirrors key steps on screen and into a file. It helps during debugging, allows you to compare different runs, and is vital when you need to explain to a reviewer which thresholds or parameters were in effect.

### Stub artifacts (from `run`)
The `run` command can create minimal placeholder artifacts so that downstream code has the right files to read even if heavy dependencies are not installed yet. These are simple zeroed JSONs and an empty JPEG used only for wiring and tests.

---

## 2) The extractor module: files and responsibilities

- `pipeline/frame_extract.py` holds the extraction logic.
- `main.py` wires a CLI subcommand named `extract` that calls into that module and sets up logging.

Keeping the extractor in its own module avoids mixing CLI code with image processing code. This separation makes testing easier and mirrors how later stages (detection, VLM, selection) will be plugged in.

---

## 3) What the extractor computes

For each sampled frame, the extractor computes four metrics and writes a pair of files:

- `frames/NNNNNN.jpg`: the image, with a stable zero-padded numeric name.
- `frames/NNNNNN.metrics.json`: a small JSON with metrics.

The metrics JSON has the following fields:

```json
{
  "time_sec": <float>,        // present since Step 2B
  "score": <float>,           // 0.7 * sharpness + 0.3 * contrast
  "sharpness": <float>,       // variance of Laplacian on GRAY
  "brightness": <float>,      // mean V in HSV (0..255)
  "contrast": <float>         // std-dev Y in YCrCb
}
```

### Metric definitions and rationale

**Sharpness** is the variance of the Laplacian on the grayscale image. It is a well-known focus proxy: in-focus images have stronger high-frequency energy, so the variance increases. This is the single most informative signal here and intentionally dominates the score.

**Brightness** is the mean of the V channel in HSV, in [0, 255]. It is not part of the score, but it is useful as a sanity check: extremely low or high brightness often correlates with poor quality, which may depress sharpness and contrast anyway.

**Contrast** is the standard deviation of the Y (luminance) channel in YCrCb. It captures spread in luminance; sharp, well-lit images tend to have higher spread. In combination with sharpness it helps prefer frames that are both in focus and visually informative.

**Score** is `0.7 * sharpness + 0.3 * contrast`. It is deliberately simple and interpretable. The absolute magnitude can vary across videos (resolution, optics, compression), but selection is driven by ranking rather than absolute thresholds, and later stages normalize per-episode.

---

## 4) How frames are sampled

The extractor does not decode all frames. It reads the source FPS from the container, computes an integer `step = round(fps / fps_target)`, and then decodes only indices where `frame_idx % step == 0`. This produces approximately `fps_target` frames per second with much less decoding work. The start index `0` is always kept, so depending on container FPS (e.g., 29.97 vs 30.00) and clip duration you may get off-by-one differences (e.g., 61 frames for ~30 seconds at 2 fps). This is expected.

The pair `grab()`/`retrieve()` is used instead of `read()`: `grab()` advances without decoding, and `retrieve()` decodes only when a frame is actually needed. That keeps the extractor efficient on CPU.

---

## 5) Temporal windowing (Step 2B)

Uniform sampling still allows “bursts” of near-identical frames when something sharp happens. Step 2B adds a temporal structure:

- The timeline is partitioned into windows of `window_seconds` (default 2.0).
- Within each window, frames are **ranked by score** and only the best `keep_top_per_window` frames (default 1) are persisted.
- Frames with `sharpness < sharpness_min` are filtered out early and never reach the in-memory ranking.

Internally, the extractor keeps a small **bucket** of candidates for the current window. When it detects a window change (based on `floor(time_sec / window_seconds)`), it **flushes** the bucket: sort by score, keep top-K, write JPEGs and JSONs, and discard the rest. At end-of-file, it flushes the last window too.

Expected behavior: for a 30-second clip, with `fps_target = 2.0`, `window_seconds = 2.0`, and `keep_top_per_window = 1`, you typically persist around 15 frames, one per window, covering the whole episode more uniformly.

---

## 6) Parameters you can tune

- `fps_target`: desired sampling rate. Higher values produce more candidates and more compute; lower values are cheaper and more diverse.
- `window_seconds`: length of each temporal slice. Short windows produce more windows; long windows give more competition inside each window.
- `keep_top_per_window`: how many frames per window to keep. Set to 1 to enforce strong temporal diversity; set to 2–3 to keep a couple of alternatives per moment.
- `sharpness_min`: a conservative blur gate. Set to 0 to keep everything for debugging; raise it gradually to drop obviously out-of-focus frames.
- `limit_frames`: stop after writing a maximum number of frames, flushing the current window first. Useful for quick tests.

Choose parameters based on downstream goals. If detection will be robust and you need fewer training frames, keep `keep_top_per_window` low. If the clip’s action is very fast, reduce `window_seconds` to avoid missing brief but important poses.

---

## 7) Running and verifying

Minimal real run:

```bash
python -m main extract   --video sample_data/example.mp4   --out out/episode02   --fps_target 2.0   --window_seconds 2.0   --keep_top_per_window 1   --sharpness_min 0
```

What to check:

- The count of `*.jpg` roughly matches `duration_seconds / window_seconds` (±1).
- Two random `*.metrics.json` files show sensible values. The frame selected within a window should have higher `sharpness`, and therefore higher `score`, than neighbors sampled in the same window.  
- `pipeline.log` contains a short trace with FPS, step, window length, and final counts.

If you instead run `python -m main run ...`, you will get the layout and the stub artifacts; use this mode for wiring tests or when you are preparing the environment on a new machine.

---

## 8) Design choices and their implications

The score favors sharpness because focus is a hard constraint for most downstream tasks. Contrast complements sharpness by favoring informative lighting and textures. Brightness is tracked but not scored to avoid biasing against strongly lit scenes where sharpness remains high. JPEG quality is set to 95 to preserve detail without generating massive files; you can adjust this if storage is a concern.

Temporal windowing trades a modest increase in memory (an in-RAM bucket for the current window) for better temporal coverage. The bucket is small in practice because it only accumulates candidates for a single window at a time.

Per-episode normalization of image quality is intentionally delayed to the selection stage, where we compute min-max normalization **within** the episode so frame scores are comparable during multi-signal fusion.

---

## 9) Troubleshooting and common pitfalls

If OpenCV is missing, install `opencv-python-headless`. If FPS is reported as zero by a peculiar container, the extractor falls back to 30.0; the absolute number of frames may shift slightly, but the temporal windowing still behaves as expected. If you get exactly zero frames written, either the video path is wrong, or the sharpness gate is too strict for your material; set `--sharpness_min 0` to inspect the raw metric distribution and then pick a threshold.

If you see 61 frames for 30 seconds at 2 fps before windowing, this is normal due to integer stepping and container FPS. After enabling windowing with `keep_top_per_window=1` and `window_seconds=2.0`, you should see about 15 frames persisted.

---

## 10) How this prepares for detection and VLM

The extractor gives you a compact, high-quality, temporally spread set of frames annotated with basic quality metrics and timestamps. Object detection (YOLO) will read `frames/` and write one JSON per frame into `detections/`, plus an evolving `vocabulary.json`. VLM semantics (CLIP and optional caption) will score each frame against a short text description into `vlm/`. After both are in place, the selection stage will fuse these signals into an append-only `dataset_summary.json`.

Keeping the extraction clean and deterministic makes later debugging tractable: if something looks off downstream, you can always inspect `*.metrics.json` and the log to confirm that the inputs were sensible.
