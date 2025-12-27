# Agentic Teacher Design - Stanford-Google Distillation Strategy

**Purpose:** Generate a high-quality, multi-modal training dataset to distill "Teacher" capabilities (GPT-4o + full video context) into a small "Student" model (Gemma 2B/Qwen 3B + single frame).

**Key Insight:**
Small models cannot perform perception, reasoning, and coding simultaneously with high reliability. We decouple these functions into specialized **Adapters** trained on specific phases of the Teacher's reasoning process.

---

## 1. The "Lossless Trace" Architecture

Instead of generating a single final artifact, the pipeline produces a **Trace** of the entire reasoning chain. This trace is then split offline into specialized datasets.

**Mega-Record Structure (JSONL):**
```json
{
  "instruction": "Put blue can on table",
  "student_image": "frame0.jpg",      // The blind input (Student view)
  "teacher_image": "contact.jpg",     // The privileged input (Teacher view)
  "trace": {
    "semantic_state": { ... },        // Target for Vision Adapter
    "naive_xml": "<root>...</root>",  // Input for Repair Adapter
    "final_xml": "<root>...</root>",  // Target for Logic/Repair Adapter
    "audit_log": [ ... ]
  },
  "verdict": "ACCEPT"
}
```

---

## 2. Agent Pipeline (The Teacher)

### Phase 1: Perception (Vision Adapter Target)
**A. Feasibility Agent**
- **Role:** Gatekeeper. Checks if task is solvable.
- **Output:** `REJECT` (Safety Dataset) or `ACCEPT`.

**B. Scene Analysis Agent**
- **Role:** The "Visual Cortex".
- **Input:** Contact Sheet.
- **Output:** **Structured Semantic State (YAML)**.
  - *Target Entity, Environment, Risks, Affordances.*
- **Goal:** Provide a standard "language" between Vision and Logic.

### Phase 2: Reasoning (Logic Adapter Target)
**C. Architect Agent**
- **Role:** The "Planner".
- **Input:** Semantic State + Image.
- **Output:** **Naive Behavior Tree** with Reasoning Comments (`<!-- Risk: ... -->`).
- **Goal:** Draft the logical structure based on semantic understanding.

**D. Robustness Agent**
- **Role:** The "Engineer".
- **Input:** Naive BT.
- **Output:** **Robust Behavior Tree** (Retries, Fallbacks).
- **Goal:** Harden the plan against identified risks.

**E. Recovery Planner Agent**
- **Role:** The "Recovery Designer".
- **Input:** Robust BT + Semantic State.
- **Output:** Robust BT with meaningful recovery (no redundant fallback-retry patterns).

### Phase 3: Modularization (Logic/Repair Adapter Target)
**F. Subtree Enablement Agent**
- **Role:** The "Architect".
- **Input:** Robust BT.
- **Output:** Modularized BT with standard SubTrees (`T_Navigate`, `T_Manipulate`).

### Phase 4: Quality Assurance (Repair Adapter Target)
**G. Conformance Agent**
- **Role:** The "Linter".
- **Check:** PAL v1 Primitive compliance.
- **Action:** If invalid, trigger repair.

**H. Scorer Agent**
- **Role:** The "Judge".
- **Output:** Final verdict (`ACCEPT`/`REJECT`) and quality score.

---

## 3. The 3-Adapter Distillation Strategy

We train 3 specialized LoRA adapters using the data extracted from the Trace.

### Adapter A: Vision-to-Semantics ("The Eye")
*   **Input:** `Frame 0` + `Instruction`
*   **Output:** `Semantic State (YAML)`
*   **Function:** Grounding text instructions in visual reality.

### Adapter B: Semantics-to-Logic ("The Brain")
*   **Input:** `Frame 0` + `Semantic State` + `Instruction`
*   **Output:** `Final XML` (robust + modular, may include `<SubTree>`)
*   **Function:** Pure planning logic, independent of pixel-level noise.

### Adapter C: Critic & Repair ("The Immunologist")
*   **Input:** `Frame 0` + `Instruction` + `Naive XML`
*   **Output:** `Final XML` (robust + modular, may include `<SubTree>`)
*   **Function:** Self-correction and robustness hardening.

---

## 4. Primitives (PAL v1)

**Allowed Actions:**
`GRASP`, `PLACE_ON_TOP`, `PLACE_INSIDE`, `OPEN`, `CLOSE`, `NAVIGATE_TO`, `RELEASE`,
`TOGGLE_ON`, `TOGGLE_OFF`, `SOAK_UNDER`, `SOAK_INSIDE`, `WIPE`, `CUT`, `PLACE_NEAR_HEATING_ELEMENT`,
`PUSH`, `POUR`, `FOLD`, `UNFOLD`, `SCREW`, `HANG`.

---

## 4.1 XML Invariants (must hold at training + inference)

- `root@main_tree_to_execute` must match the ID of the main `<BehaviorTree>` (the first definition).
- Every `<BehaviorTree>` must have exactly one root child node (wrap steps in a `<Sequence>`).
- `RELEASE` must appear at most once for single-object tasks (avoid duplicating it in both main and place-subtrees).

## 5. Implementation Status

*   **Pipeline:** Implemented in `embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py` (Lossless Trace).
*   **Prompts:**
    *   **Teacher prompts**: `embodied_bt_brain/agentic_teacher/prompts/` (YAML + XML refinement).
    *   **Adapter prompts**: `prompts/inference/` (Frame 0 only; used by `tools/split_dataset.py`).
*   **Tools:**
    *   `tools/split_dataset.py` produces simple (image + prompt + target) JSONL splits (vision/logic/repair).
*   **Inference Prompts:** `prompts/inference/` contains the templates used by `tools/split_dataset.py` and intended for training/inference alignment.

---

## 6. Teacher System Design (Implementation)

This section merges the repo-local system design doc into this single file.

### 6.1 System Architecture

```
Instruction + Contact Sheet (9 frames)     Student adapters see ONLY Frame 0
           ↓
    [Feasibility Agent]          (optional, can skip episode)
           ↓
   [Scene Analysis Agent]        (optional; outputs Semantic State YAML)
           ↓
     [Architect Agent]            (required; drafts BT XML)
           ↓
    [Robustness Agent]           (retries/fallbacks; no SubTree)
           ↓
  [Recovery Planner Agent]       (meaningful recovery; no SubTree)
           ↓
[SubTree Enablement Agent]       (modularizes into SubTrees)
           ↓
   [Conformance Agent]           (PAL v1 validation + repair if needed)
           ↓
   [Final Validator]              (always runs)
           ↓
     [Scorer Agent]                (optional)
           ↓
  Final BT XML + Audit Log + Score + Verdict
```

### 6.2 Where It Lives in Code

- Orchestrator: `embodied_bt_brain/agentic_teacher/teacher_loop.py` (`AgenticTeacherLoop`)
- Teacher prompts: `embodied_bt_brain/agentic_teacher/prompts/`
- PAL spec: `embodied_bt_brain/primitive_library/pal_v1.json`
- Conformance repair:
  - `embodied_bt_brain/agentic_teacher/agents/conformance.py` uses `LLMRepairer(default_prompt="repair_generic")`
  - `embodied_bt_brain/agentic_teacher/prompts/repair_generic.md` is therefore required (it is used)

### 6.3 Teacher Output (Lossless Trace)

The dataset record includes (at minimum):
- `trace.semantic_state` (YAML string; root `semantic_state`)
- `trace.naive_xml` (XML string)
- `trace.final_xml` (XML string, typically modular with `<SubTree>`)
