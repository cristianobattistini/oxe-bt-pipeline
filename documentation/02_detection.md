# Detection Stage – User Guide

This document explains **everything related to the Detection stage** of the pipeline, aligned with the code in `pipeline/detect.py` and the CLI in `main.py`. It covers purpose, inputs/outputs, parameters, the `allowed_nouns` filter, vocabulary aggregation, sanity checks, troubleshooting, and example commands.

---

## 1) What the Detection stage does

Given frames previously extracted into `out/<episode>/frames/`, the stage:

1. **Loads YOLO** (Ultralytics) if available; otherwise it proceeds in a **safe fallback** mode (writing valid empty detections).
2. Iterates every frame image (supports `.jpg`, `.jpeg`, `.png`).
3. Runs detection (if YOLO is available), **filters** and **sanity-checks** results.
4. Writes **one JSON per frame** into `out/<episode>/detections/NNNNNN.json`.
5. Updates `out/<episode>/detections/vocabulary.json`, a compact summary of labels across the episode.

This stage is **CPU-first**, robust to missing dependencies and unreadable images, and produces deterministic, schema-compliant artifacts.

---

## 2) Input and output layout

**Input (produced by Extract stage):**
```
out/<episode>/
  frames/
    000000.jpg
    000000.metrics.json
    000001.jpg
    000001.metrics.json
    ...
```

**Output (produced by Detection stage):**
```
out/<episode>/
  detections/
    000000.json
    000001.json
    ...
    vocabulary.json
```

Each `NNNNNN.json` is an **array** (possibly empty) of objects with fields:
```json
[
  {
    "frame_id": "000123",
    "det_id": 0,
    "noun": "person",
    "score": 0.92,
    "bbox": [x1, y1, x2, y2],
    "source": "yolov8n"
  }
]
```

`vocabulary.json` summarizes detections **kept after filtering**:
```json
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
```

---

## 3) CLI usage

Top-level help:
```bash
python -m main detect --help
```

Typical run (CPU):
```bash
python -m main detect --out out/episode02 --device cpu
```

With thresholds and a whitelist:
```bash
python -m main detect   --out out/episode02   --conf_threshold 0.25   --iou_threshold 0.50   --allowed_nouns "person,bottle"   --device cpu
```

> Tip: if you pass a label not present in the model’s label set (e.g. `planet` for COCO), **all detections will be filtered out** and files will contain `[]`.

---

## 4) Parameters (meaning and defaults)

- `--out` **(required)**: episode directory, e.g. `out/episode02`.
- `--conf_threshold` *(default 0.25)*: minimum confidence for a YOLO detection to be considered (before our own filtering/sanity checks).
- `--iou_threshold` *(default 0.50)*: IoU threshold used by YOLO for NMS.
- `--allowed_nouns` *(default empty)*: comma-separated whitelist of labels to keep (case-insensitive). If empty, keep **all** labels.
- `--device` *(cpu|cuda, default cpu)*: inference device. On machines without CUDA, use `cpu`.

---

## 5) Filtering and sanity checks

**Filtering:**
- If `--allowed_nouns` is provided, detections whose `noun` is **not** in the list are **dropped**.
- Labels are **lowercased** to keep vocabulary keys consistent.

**Sanity checks:**
- `score` is **clamped** to `[0,1]`.
- `bbox` is **clamped to image bounds** and coordinate **ordering** is enforced (`x1<x2`, `y1<y2`). Degenerate boxes are dropped.

These checks ensure downstream stages receive consistent, bounded values.

---

## 6) Vocabulary aggregation

For every kept detection, we update two accumulators per noun:
- `count`  → how many detections with that label were kept (across all frames).
- `avg_score` → average confidence for that label.

The final `vocabulary.json` is built from these accumulators and includes:
- `vocab`  → `{ label: {count, avg_score}, ... }`
- `stats.total_images` → number of **per-frame JSON files written** (i.e., how many images were processed), even if a file is empty.

---

## 7) Reading results correctly

- An **empty** per-frame file `[]` means: no kept detections for that image (either none above thresholds or all filtered out by `--allowed_nouns`).
- An **empty** `vocab` with `"total_images": N` means: we processed `N` images but **no kept labels** across the episode.

Example from a run with `--allowed_nouns "planet"` on a COCO-trained YOLO model (which does **not** include “planet”):
```
detections/000015.json  → []
detections/vocabulary.json → { "vocab": {}, "stats": { "total_images": 1, ... } }
```
This is expected given the filter.

---

## 8) Optional dependencies and fallbacks

- If Ultralytics YOLO is **installed** and can be initialized, we run it.
- If not, detection still runs and writes valid per-frame JSONs (empty arrays) and a `vocabulary.json` with zero entries. This keeps the pipeline usable on minimal environments.

**Verifications (inside the active environment):**
```bash
python -c "import ultralytics; print('ultralytics', ultralytics.__version__)"
python -c "import torch; print('torch', torch.__version__)"
```

---

## 9) Troubleshooting

- **`processed=0`**: the detector did not see any image. Check your frames folder or supported extensions. Our implementation accepts `.jpg/.jpeg/.png`.
- **All files are `[]`**:
  - Your `--allowed_nouns` filtered everything. Try without the flag or use known labels (e.g., `person`, `cup`, `chair`).
  - Thresholds are too strict; try `--conf_threshold 0.10`.
- **YOLO fails to load**:
  - Install requirements in the active environment (CPU-only example):
    ```bash
    python -m pip install ultralytics
    python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    ```
  - If downloads are blocked, provide a local weights path and adapt the loader accordingly.

---

## 10) Internal implementation notes (for maintainers)

- `pipeline/detect.py` keeps Ultralytics imports **inside helper functions** to avoid hard dependencies at import time.
- `_list_frames` matches multiple extensions and returns a **sorted** list for deterministic order.
- Unreadable images still get a per-frame JSON written (`[]`) so `stats.total_images` reflects the files encountered.
- The field `source` in each detection is `"yolov8n"` when YOLO ran, or `"none"` in fallback mode.

---

## 11) Practical examples

**Simple CPU run:**
```bash
python -m main detect --out out/episode02 --device cpu
```

**Keep only people and bottles:**
```bash
python -m main detect --out out/episode02 --allowed_nouns "person,bottle" --device cpu
```

**Lower confidence threshold:**
```bash
python -m main detect --out out/episode02 --conf_threshold 0.10 --device cpu
```

**After ingestion from real data (local images):**
```bash
python -m main ingest --source local --dataset_root D:eal_data --out_root out --limit 10
python -m main detect --out out/oxe_000000 --device cpu
```

---

## 12) Schema quick reference

**Per-frame Detections JSON** (`detections/NNNNNN.json`):
```json
[
  {
    "frame_id": "string",
    "det_id": 0,
    "noun": "string",
    "score": 0.0,
    "bbox": [0.0, 0.0, 0.0, 0.0],
    "source": "yolov8n"
  }
]
```

**Vocabulary JSON** (`detections/vocabulary.json`):
```json
{
  "vocab": { "noun": { "count": 0, "avg_score": 0.0 } },
  "stats": { "total_images": 0, "last_updated": "..." }
}
```

---

## 13) Reproducibility notes

- Deterministic ordering of frames makes diffs across runs stable.
- `vocabulary.json` includes a timestamp and the total image count.
- Device is chosen via CLI; default is CPU to maximize portability.

---

*End of document.*
