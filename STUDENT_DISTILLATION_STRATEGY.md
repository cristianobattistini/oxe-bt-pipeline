# Stanford-Google Distillation Strategy
**Goal:** Train a small, efficient "Student" model (e.g., Gemma 2B, Qwen 3B) to execute robust, grounded robotic manipulation tasks.

**Core Philosophy:**
Small models cannot do everything at once. We must decouple **Perception** (Vision), **Reasoning** (Logic), and **Correction** (Repair) into specialized modules (Adapters) that share a common language: the **Semantic State**.

---

## 1. The Common Language: Semantic State (YAML)
Instead of forcing the Student to jump from `Pixel -> XML`, we introduce an intermediate representation.
*   **Format:** Structured YAML describing Target, Environment, Risks, and Affordances.
*   **Role:** Acts as the output for the Vision Adapter and the input for the Logic Adapter. Anchors the text to physical reality.

---

## 2. The 3-Adapter Architecture

### Adapter A: Vision-to-Semantics ("The Eye")
*   **Input:** `Frame 0 (Image)` + `Instruction`
*   **Output:** `Semantic State (YAML)`
*   **Task:** "What do I see? What are the risks?"
*   **Why:** Specializes the Vision Encoder to detect affordances (graspability, obstacles) without worrying about XML syntax.

### Adapter B: Semantics-to-Logic ("The Brain")
*   **Input:** `Frame 0 (Image)` + `Semantic State (YAML)` + `Instruction`
*   **Output:** `Robust Behavior Tree (XML)` with Reasoning Comments.
*   **Task:** "Given this state, plan the robust sequence."
*   **Why:** Focuses purely on planning logic, fallbacks, and BT structure. Uses the Image as a "visual anchor" but relies on the YAML for explicit constraints.

### Adapter C: Critic & Repair ("The Immunologist")
*   **Input:** `Frame 0 (Image)` + `Instruction` + `Broken/Naive XML`
*   **Output:** `Fixed/Robust XML`
*   **Task:** "Fix this code."
*   **Why:** Teaches the model to recover from its own syntax errors or naive planning (missing fallbacks).

---

## 3. Data Generation Pipeline (Lossless Trace)

We do not generate 3 separate datasets manually. We generate a single **"Mega-Trace"** for each episode and split it offline.

**Pipeline Config:**
1.  **Feasibility Check:** Don't filter hard. If it fails, save it as a "Safety Negative".
2.  **Scene Analysis:** Generates the **Semantic State (YAML)**.
3.  **Architect:** Uses YAML + Image to draft a plan.
4.  **Robustness:** Hardens the plan (adds Fallbacks/Retries).
5.  **Output:** A JSONL record containing *all* these steps.

**The "Mega-Record" Structure:**
```json
{
  "instruction": "Put blue can on table",
  "student_image": "path/to/frame0.jpg",  // The blind input
  "teacher_image": "path/to/contact.jpg", // The privileged input
  "trace": {
    "semantic_state": "Target: blue can\nRisks: ...", // Target for Adapter A
    "naive_xml": "<root>...</root>",                   // Input for Adapter C
    "final_xml": "<root>...</root>",                  // Target for Adapter B & C
      }
}
```

---

## 4. Execution Plan (Your Job)

### Phase 1: Pipeline Upgrade
1.  **Prompts**: Ensure `scene_analysis` outputs strict YAML. Ensure `architect` reads YAML.
2.  **Writer**: Ensure `generate_dataset.py` saves the full `trace` (including intermediate XMLs) and the extracted `frame0.jpg`.

### Phase 2: Data Generation
1.  Run the pipeline on the full Open X Embodiment subset.
2.  This produces `raw_traces.jsonl`.

### Phase 3: Offline Splitting (The Refinery)
Write a script to process `raw_traces.jsonl` into training files:
*   `train_vision.jsonl`: Input=`Frame0`, Output=`SemanticState`.
*   `train_logic.jsonl`: Input=`Frame0 + SemanticState`, Output=`FinalXML`.
*   `train_repair.jsonl`: Input=`Frame0 + NaiveXML`, Output=`FinalXML`.
*   `train_safety.jsonl`: Input=`Frame0` (from REJECT episodes), Output=`"I cannot..."`.

### Phase 4: Training
1.  Train Adapter A (Vision).
2.  Train Adapter B (Logic).
3.  Train Adapter C (Repair).
4.  (Optional) Merge them or serve them as a Multi-Head Mixture of Experts.