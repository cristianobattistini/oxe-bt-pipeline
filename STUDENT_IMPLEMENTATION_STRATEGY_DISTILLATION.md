# Student Implementation Strategy: Distillation
**Operational Guide for Implementing the 3-Adapter Strategy**

This document maps the high-level strategy to specific code locations and implementation steps. Use this as a checklist.

---

## 1. Pipeline Upgrade (Phase 1) - **STATUS: DONE**
The data generation pipeline has been updated to produce the "Mega-Trace".

*   **File:** `embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py`
    *   **Change:** Added `build_rich_record` call.
    *   **Logic:** Captures `steps` (trace) and extract `frame0.jpg` vs `contact_sheet.jpg`.
*   **File:** `embodied_bt_brain/agentic_teacher/teacher_loop.py`
    *   **Change:** `generate_bt` now returns `result` even on failure (Feasibility REJECT).
    *   **Logic:** Ensures "Safety" negatives are captured.
*   **File:** `embodied_bt_brain/agentic_teacher/prompts/scene_analysis.md`
    *   **Change:** Output format forced to Structured Semantic State (Target, Env, Risks).
*   **File:** `embodied_bt_brain/agentic_teacher/prompts/architect.md`
    *   **Change:** Input now includes "Semantic State". Output requires XML comments (`<!-- Risk: ... -->`).

---

## 2. Data Generation (Phase 2) - **ACTION REQUIRED**
Run the pipeline to generate the raw `trace.jsonl`.

**Command:**
```bash
python3 embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_distillation_v1 \
  --output-mode jsonl \
  --copy-images \
  --no-resume \
  --limit 500  # Adjust as needed
```
**Output:** `dataset_distillation_v1/train/data.jsonl` (The "Mega-JSONL").

---

## 3. Offline Processing / Splitting (Phase 3) - **CODE TO WRITE**
You need a new script (e.g., `tools/split_dataset.py`) to parse the Mega-JSONL and emit the 3 adapter datasets.

### Logic Mapping

#### Adapter A: Vision-to-Semantics (`train_vision.jsonl`)
*   **Input Image:** `record["student_image_path"]` (Frame 0)
*   **Input Text:** `record["instruction"]`
*   **Target Output:** `record["trace"]["scene_analysis"]["content"]` (The Semantic State YAML)
*   **Filter:** Include only if `verdict == "ACCEPT"`.

#### Adapter B: Semantics-to-Logic (`train_logic.jsonl`)
*   **Input Image:** `record["student_image_path"]` (Visual Anchor)
*   **Input Text:**
    ```text
    Instruction: {instruction}
    Semantic State: {trace.scene_analysis.content}
    ```
*   **Target Output:** `record["trace"]["steps"][-1]["bt_xml"]` (Final Robust XML from Conformance/Scorer)
*   **Filter:** Include only if `verdict == "ACCEPT"`.

#### Adapter C: Critic & Repair (`train_repair.jsonl`)
*   **Input Image:** `record["student_image_path"]`
*   **Input Text:**
    ```text
    Instruction: {instruction}
    Broken XML: {trace.steps["architect"]["bt_xml"]}  <-- The Naive Draft
    ```
*   **Target Output:** `record["trace"]["steps"][-1]["bt_xml"]` (The Fixed XML)
*   **Filter:** Include only if `verdict == "ACCEPT"` AND `naive_xml != final_xml`.

---

## 4. Implementation Snippet (Python)

Create `process_traces.py`:

```python
import json

def process_line(line):
    record = json.loads(line)
    verdict = record.get("verdict")
    
    # Strict Positive Filtering: Ignore failures
    if verdict != "ACCEPT":
        return

    trace = record.get("trace", {})
    # Extract intermediate steps
    steps = {s["agent"]: s for s in trace.get("steps", [])}
    scene_txt = steps.get("scene_analysis", {}).get("content", "")
    naive_xml = steps.get("architect", {}).get("bt_xml", "")
    final_xml = record["messages"][-1]["content"][0]["text"] # Or last step

    # 1. Vision Adapter
    yield "vision", {
        "image": record["student_image_path"],
        "instruction": record["instruction"],
        "output": scene_txt
    }

    # 2. Logic Adapter
    yield "logic", {
        "image": record["student_image_path"],
        "instruction": record["instruction"],
        "context": scene_txt,
        "output": final_xml
    }

    # 3. Repair Adapter (Only if difference exists)
    if naive_xml and naive_xml != final_xml:
        yield "repair", {
            "image": record["student_image_path"],
            "instruction": record["instruction"],
            "broken_xml": naive_xml,
            "output": final_xml
        }
```

---

## 5. Training Configs (Hyperparameters)
*   **Model:** Gemma 2B or Qwen 3B (good vision encoders).
*   **LoRA Rank:** 
    *   Vision Adapter: `r=64` (needs capacity for perception).
    *   Logic Adapter: `r=32` (reasoning).
    *   Repair Adapter: `r=16` (syntax focus).
*   **Sequence Length:** 2048 (XML can be verbose).
