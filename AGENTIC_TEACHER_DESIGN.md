# Agentic Teacher Design - High-Quality Proposer Dataset Generation

**Purpose:** Generate a proposer training dataset where every BT is:
1. **Executable** - Uses only BEHAVIOR-1K primitives (PAL v1)
2. **Robust** - Includes guards, recovery, explicit termination strategies
3. **Scene-Aware** - Adapted to the specific visual context of the episode
4. **Patchable** - Structured to be easily modified by validator

**Key Insight:** A simple teacher LLM produces linear, brittle BTs. An **agentic teacher loop** with multiple specialized agents produces structured, robust, patchable BTs suitable for training both proposer AND validator.

**Current Scope (this phase):**
- We generate a **proposer-only dataset** from **OXE episodes** (instruction + contact sheet in `out_temp/.../final_selected/`).
- Runtime validator data is a later phase and is **not** produced here.

---

## 1. Agentic Teacher Loop Architecture

### 1.1 Overview

```
Input: (instruction, contact_sheet + 9 frames, PAL_v1, BT_conventions)
  ↓
┌─────────────────── AGENTIC TEACHER LOOP ───────────────────┐
│                                                              │
│  PHASE 1: FEASIBILITY & UNDERSTANDING (COGNITION)            │
│  ────────────────────────────────────────────────            │
│  A. Feasibility Agent                                        │
│     → Check if task possible with PAL primitives            │
│     → SKIP episode if impossible (save cost)                │
│                                                              │
│  B. Scene Analysis Agent                                     │
│     → Deep understanding of 9 frames                        │
│     → Identify favorable/unfavorable conditions             │
│     → Predict possible failures and limitations             │
│     → Leverage LLM creativity before BT constraints         │
│                                                              │
│  PHASE 2: CREATIVE GENERATION (CONSTRUCTION)                 │
│  ───────────────────────────────────────────                 │
│  C. Architect Agent                                          │
│     → Draft BT structure informed by scene analysis         │
│     → Focus on task logic, not validation                   │
│                                                              │
│  C.5 Critic Agent (Socratic Dialogue) **[NEW]**             │
│     → Challenge Architect's design (max 2 iterations)       │
│     → Verify logical coherence + visual grounding           │
│     → Blocking: REJECT if critical flaws persist            │
│                                                              │
│  PHASE 3: REFINEMENT (ENGINEERING)                           │
│  ─────────────────────────────────                           │
│  D. Robustness Agent                                         │
│     → Inject guards, recovery, retry wrappers               │
│                                                              │
│  E. Subtree Enablement Agent                                 │
│     → Modularize into replaceable subtrees                  │
│                                                              │
│  PHASE 4: FINAL VALIDATION (THE "POLICE")                    │
│  ────────────────────────────────────────                    │
│  F. Conformance & Schema Agent                               │
│     → Final gate: Ensure PAL compliance & valid schema      │
│     → Trigger repair if invalid                             │
│                                                              │
│  G. Scorer/Judge Agent                                       │
│     → Quality assessment & final verdict                    │
│                                                              │
│  If rejected: DISCARD (or retry from Architect)             │
│  If accepted: proceed to output                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
  ↓
Output: (bt.xml, audit_log.json, subtree_map.json)
```

### 1.2 Design Philosophy Changes

1.  **Gatekeeping First:** We moved `FeasibilityAgent` to the front to "fast fail" impossible tasks, saving tokens and ensuring data purity.
2.  **Cognition Before Code:** The `SceneAnalysisAgent` runs *before* the Architect. This ensures the BT is grounded in visual reality (obstacles, occlusions) rather than just being a template.
3.  **Safety Sandwich:** Validation (`Conformance`, `Schema`) moved to the *end* of the pipeline. This ensures that any changes made during Refinement (e.g., Subtree refactoring) are also validated.
4.  **Deterministic IDs:** We removed the `IdPatchabilityAgent` (LLM-based). ID assignment should be a deterministic post-processing step to guarantee uniqueness and correctness without hallucination risk.

---

## 2. Agent Specifications

### Agent A: Feasibility Agent (The Gatekeeper)

**Role:** Decide if the task is solvable with PAL v1 primitives.

**Input:**
- Task instruction
- PAL v1 primitive list

**Output:** `feasible: true/false`, `reason`

**Logic:**
- If instruction requires "Cook", "Screw", "Fold" -> REJECT.
- If instruction maps to "Pick", "Place", "Open", "Nav" -> ACCEPT.
- Prevents generating garbage data for impossible tasks.

### Agent B: Scene Analysis Agent (The Vision)

**Role:** Provide a strategic situation report to the Architect.

**Input:**
- Instruction
- 9 Frames (Contact Sheet)

**Output:** Structured Text Report
1.  **Scene Description:** Entities, relations.
2.  **Dynamic Progression:** What happens in the video?
3.  **Strategic Assessment:** Favorable (e.g., "Drawer open") vs Unfavorable (e.g., "Clutter") conditions.
4.  **Planner Hints:** Specific advice for the BT (e.g., "Use high clearance grasp").

### Agent C: Architect Agent (The Builder)

**Role:** Draft the Behavior Tree logic.

**Input:**
- Instruction
- **Scene Analysis Report** (from Agent B)

**Strategy:**
- Use the Scene Analysis to make decisions (e.g., skip `OPEN` if analysis says "Door is open").
- Focus on logical flow (Sequence of phases).
- Do not worry about perfect syntax or guards yet.

---

### Agent C.5: Critic Agent (The Socratic Challenger) **[NEW]**

**Role:** Challenge Architect's design through Socratic dialogue.

**Mode:** Socratic (Question-based critique with iterative revision)

**Input:**
- BT from Architect
- Instruction
- Scene Analysis Report
- Reference to Architect (for revisions)

**Output:** Improved BT after 0-2 iterations of dialogue

**Evaluation Dimensions:**

1. **Logical Coherence (0-10):**
   - Does BT accomplish the instruction?
   - Are actions in correct order?
   - Any logical impossibilities? (PLACE before GRASP)
   - Missing critical steps?
   - Control flow semantics correct?

2. **Visual Grounding (0-10):**
   - Did Architect use scene analysis?
   - Scene mentioned obstacles → navigation adjusted?
   - Scene predicted failures → mitigation added?
   - BT matches visual reality?

**Process:**
1. **Iteration 1:** Critic reviews initial BT
   - Asks pointed questions: "Why PLACE_ON_TOP when scene shows drawer?"
   - Identifies critical issues: "No NAVIGATE_TO before GRASP"
   - Provides suggestions: "Consider adding Fallback here"

2. **Architect responds:**
   - Justifies choices OR revises BT
   - Addresses critical issues
   - Incorporates relevant suggestions

3. **Iteration 2 (if needed):** Critic re-reviews
   - Checks if issues addressed
   - Final accept/concerns/reject verdict

4. **Max 2 iterations** - prevents infinite loops

**Verdicts:**
- **ACCEPT:** Logical and grounded → proceed to Robustness
- **CONCERNS:** Fixable issues → revision requested
- **REJECT:** Critical flaws → SKIP episode (blocking)

**Blocking Behavior:**
- In strict mode (default), REJECT verdict after 2 iterations → skip episode
- This ensures only quality BTs enter the dataset
- Prevents "garbage in, garbage out" problem

**Why This Agent?**
- **Enforces scene grounding:** Prevents templated BTs that ignore visual context
- **Catches logic errors early:** Before expensive Robustness/Subtree work
- **Dialectical improvement:** Thesis (draft) → Antithesis (critique) → Synthesis (improved BT)
- **Training data quality:** Logs entire reasoning dialogue for analysis

**Example Dialogue:**

```
Critic: "Scene analysis says 'cup near table edge' with predicted failure
'grasp might fail'. Your BT has bare <Action ID='GRASP'/> with no mitigation.
Why?"

Architect (Revision): "Added Fallback with recovery: if GRASP fails,
NAVIGATE_TO cup from different angle, retry GRASP."

Critic: "Good. But scene also says 'tray has raised edges'. Your PLACE_ON_TOP
doesn't account for precise placement. How will you handle this?"

Architect (Revision): "Changed to Sequence: NAVIGATE_TO tray_center,
PLACE_ON_TOP tray, RELEASE with delay."

Critic: "ACCEPT - logical flow is sound and grounded in scene analysis."
```

---

### Agent D: Robustness Agent (The Engineer)

**Role:** Harden the tree against runtime failure.

**Input:** Skeleton BT

**Action:**
- Wrap critical actions in `RetryUntilSuccessful`.
- Add `Fallback` nodes with recovery sequences (e.g., "If grasp fails, re-navigate").

### Agent E: Subtree Enablement Agent (The Modularizer)

**Role:** Refactor into standard SubTrees.

**Input:** Robust BT

**Action:**
- Identify patterns (`NAVIGATE_TO`, `GRASP`).
- Replace with standard SubTree definitions (`T_Navigate`, `T_Manipulate_Grasp`).
- Ensure modularity for the Validator.

### Agent F: Conformance & Schema Agent (The Police)

**Role:** Final validation of the artifact.

**Checks:**
- **XML Syntax:** Is it valid XML?
- **PAL Compliance:** Are all primitives in the allowed list? (No "PickUp", "MoveTo").
- **Parameter Flow:** Do `{target}` substitutions match?

**Action:**
- If issues found -> Trigger `LLMRepairer`.
- If issues persist -> REJECT episode.

### Agent G: Scorer (The Judge)

**Role:** Final quality assessment.

**Criteria:**
- Structure (Depth, Branching)
- Robustness (Retries present)
- Compliance (PAL v1 only)
- Visual Grounding (Does it match the instruction?)

---

## 3. Primitives (PAL v1)

**Allowed Actions:**
`GRASP`, `PLACE_ON_TOP`, `PLACE_INSIDE`, `OPEN`, `CLOSE`, `NAVIGATE_TO`, `RELEASE`, `TOGGLE_ON`, `TOGGLE_OFF`, `SOAK_UNDER`, `SOAK_INSIDE`, `WIPE`, `CUT`, `PLACE_NEAR_HEATING_ELEMENT`.

**Implicit Rules:**
- `obj` parameter required for all except `RELEASE`.
- No `timeout_ms` parameter.

---

## 4. Implementation Plan

1.  **Prompts:** Ensure `feasibility.md` and `scene_analysis.md` are robust.
2.  **Pipeline:** Update `teacher_loop.py` to reflect the new order (A -> B -> C -> D -> E -> F -> G).
3.  **Repair:** Ensure `LLMRepairer` is accessible to Agent F.
4.  **Deterministic IDs:** Implement a python utility to assign `node_01`, `node_02` IDs at the very end (post-XML generation).