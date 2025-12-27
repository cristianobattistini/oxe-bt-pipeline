# Agentic Teacher - System Design Documentation

## Overview

The **Agentic Teacher** is a multi-agent pipeline that automatically generates Behavior Tree (BT) XML from robot task instructions and visual observations. The system orchestrates multiple specialized agents, each responsible for a specific aspect of BT generation, validation, and refinement.

## System Architecture

```
Instruction + Contact Sheet (9 frames)
           ↓
    [Feasibility Agent]          (optional, can skip episode)
           ↓
   [Scene Analysis Agent]        (optional)
           ↓
     [Architect Agent]            (required)
           ↓
    [Robustness Agent]            (configurable)
           ↓
  [Recovery Planner Agent]       (configurable; meaningful fallbacks)
           ↓
[SubTree Enablement Agent]       (configurable)
           ↓
   [Conformance Agent]            (configurable)
           ↓
   [Final Validator]              (always runs)
           ↓
     [Scorer Agent]                (optional)
           ↓
  Final BT XML + Audit Log + Score + Verdict
```

**Note**: All agents except Architect and Final Validator are optional and can be enabled/disabled via configuration.

---

## Pipeline Execution Flow

The `AgenticTeacherLoop` orchestrates the following sequence:

1. **Optional Preflight**: Feasibility check (can skip episode if infeasible)
2. **Optional Scene Analysis**: Deep visual and strategic analysis
3. **Architecture**: Draft initial BT structure
4. **Refinement Pipeline**: Robustness → Recovery Planner → SubTree Enablement → Conformance
5. **Final Validation**: Hard XML and PAL v1 compliance check
6. **Scoring**: Quality evaluation and verdict

---

## Agent Specifications

### 1. Feasibility Agent

**Purpose**: Determine if a task is feasible using PAL v1 primitives

**Inputs**:
- `instruction` (str): Natural language task description
- `contact_sheet_path` (str): Path to 3x3 grid of 9 frames (images)

**Processing**:
- Uses LLM with vision (multimodal)
- Prompt: `prompts/feasibility.md`
- Temperature: 0.0
- Max tokens: 600

**Output** (JSON):
```json
{
  "feasible": true|false,
  "reason": "short explanation",
  "required_primitives": ["GRASP", "NAVIGATE_TO", ...],
  "missing_capabilities": []
}
```

**Audit Log Entry**:
```json
{
  "agent": "Feasibility",
  "status": "ok",
  "feasible": true,
  "reason": "...",
  "required_primitives": [...],
  "missing_capabilities": [...],
  "used_llm": true
}
```

**Behavior**:
- If `feasible: false`, raises `SkipEpisode` exception
- Frame 0 is treated as initial state
- Frames 1-8 used only for risk assessment (anti-leakage rule)

---

### 2. Scene Analysis Agent

**Purpose**: Generate detailed visual analysis and strategic planning hints

**Inputs**:
- `instruction` (str): Natural language task description
- `contact_sheet_path` (str): Path to 3x3 contact sheet

**Processing**:
- Uses LLM with vision (multimodal)
- Prompt: `embodied_bt_brain/agentic_teacher/prompts/scene_analysis.md`
- Temperature: 0.2
- Max tokens: 900

**Output** (str): **Structured Semantic State (YAML)** with root `semantic_state`:
```yaml
semantic_state:
  target:
    name: "<string>"
    initial_state: "<string>"
    position: "<string>"
    attributes: ["<attr1>", "<attr2>"]
  environment:
    surface_or_container: "<string>"
    obstacles: ["<obj1>", "<obj2>"]
    constraints: ["<constraint1>", "<constraint2>"]
  risks:
    possible_failures: ["<risk1>", "<risk2>"]
    recovery_hints: ["<hint1>", "<hint2>"]
  affordances:
    primary_primitives: ["GRASP", "PLACE_ON_TOP"]
    preconditions: ["<precond1>", "<precond2>"]
    robustness_need: "low" | "medium" | "high"
```

**Audit Log Entry**:
```json
{
  "agent": "SceneAnalysis",
  "status": "ok",
  "used_llm": true,
  "chars": 3465
}
```

**Behavior**:
- Can be disabled (returns empty string if disabled)
- Output is passed to Architect Agent as structured planning context

---

### 3. Architect Agent

**Purpose**: Draft initial BT structure from instruction and visual context

**Inputs**:
- `instruction` (str): Natural language task description
- `contact_sheet_path` (str): Path to 3x3 contact sheet
- `scene_analysis` (str): Output from Scene Analysis Agent (optional, may be empty)

**Processing**:
- Uses LLM with vision (multimodal)
- Prompt: `prompts/architect.md`
- Temperature: 0.7 (default)
- Max tokens: 2000 (default)

**Output** (str): Valid BT.CPP XML
```xml
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="task_name">
      <!-- Behavior tree structure with Actions, Fallbacks, etc. -->
      <Action ID="NAVIGATE_TO" obj="target"/>
      <Action ID="GRASP" obj="target"/>
      ...
    </Sequence>
  </BehaviorTree>
</root>
```

**Audit Log Entry**:
```json
{
  "agent": "Architect",
  "status": "ok",
  "used_llm": true
}
```

**Behavior**:
- Has fallback regex-based patterns for common tasks (place_inside, place_on_top, grasp, etc.)
- Parses instruction to extract intent, object, destination
- Validates XML syntax before returning

---

### 4. Robustness Agent

**Purpose**: Add retry logic and recovery strategies to BT

**Inputs**:
- `bt_xml` (str): XML from previous agent (Architect or prior refinement)

**Processing**:
- Uses LLM (text-only)
- Prompt: `prompts/robustness.md`
- Temperature: 0.7 (default)
- Max tokens: 2500 (default)

**Output** (str): Enhanced BT XML with:
- `RetryUntilSuccessful` wrappers
- `Fallback` nodes with recovery sequences
- Increased robustness for manipulation actions

**Example Transformation**:
```xml
<!-- Before -->
<Action ID="GRASP" obj="blue_can"/>

<!-- After -->
<RetryUntilSuccessful num_attempts="3">
  <Fallback>
    <Action ID="GRASP" obj="blue_can"/>
    <Sequence name="recovery_grasp">
      <Action ID="NAVIGATE_TO" obj="blue_can"/>
      <Action ID="GRASP" obj="blue_can"/>
    </Sequence>
  </Fallback>
</RetryUntilSuccessful>
```

**Audit Log Entry**:
```json
{
  "agent": "Robustness",
  "status": "ok",
  "issues_found": 0,
  "wrapped_actions": 0,
  "used_llm": true
}
```

**Behavior**:
- Can be disabled (returns input XML unchanged if disabled)
- Typically skips wrapping NAVIGATE_TO and RELEASE primitives

---

### 5. SubTree Enablement Agent

**Purpose**: Extract repeated patterns into reusable SubTrees

**Inputs**:
- `bt_xml` (str): XML from Robustness Agent

**Processing**:
- Uses LLM (text-only)
- Prompt: `prompts/subtree_enablement.md`
- Temperature: 0.7 (default)
- Max tokens: 3000 (default)

**Output** (str): Refactored BT XML with SubTree definitions

**Example Transformation**:
```xml
<!-- Before: Repeated GRASP pattern -->
<Sequence>
  <RetryUntilSuccessful num_attempts="3">
    <Action ID="GRASP" obj="blue_can"/>
  </RetryUntilSuccessful>
</Sequence>

<!-- After: Extracted to SubTree -->
<BehaviorTree ID="MainTree">
  <Sequence>
    <SubTree ID="T_Manipulate_Grasp" target="blue_can"/>
  </Sequence>
</BehaviorTree>

<BehaviorTree ID="T_Manipulate_Grasp">
  <RetryUntilSuccessful num_attempts="3">
    <Action ID="GRASP" obj="{target}"/>
  </RetryUntilSuccessful>
</BehaviorTree>
```

**Audit Log Entry**:
```json
{
  "agent": "SubtreeEnablement",
  "status": "ok",
  "issues_found": 0,
  "used_llm": true
}
```

**Behavior**:
- Creates modular, reusable SubTrees
- Uses parameter remapping (e.g., `{target}`, `{obj}`)
- Can be disabled

---

### 6. Conformance Agent

**Purpose**: Enforce PAL v1 primitive compliance

**Inputs**:
- `bt_xml` (str): XML from SubTree Enablement Agent

**Processing**:
- Uses LLM (text-only) with repair prompt
- Prompt: `prompts/conformance.md`
- Temperature: 0.7 (default)
- Checks against PAL v1 specification

**Output** (str): PAL-compliant BT XML

**Common Fixes**:
- Remove invalid primitives (e.g., non-PAL actions)
- Fix incorrect parameters
- Ensure control flow nodes are valid (Sequence, Fallback, RetryUntilSuccessful, etc.)

**Audit Log Entry**:
```json
{
  "agent": "Conformance",
  "status": "ok"|"repaired",
  "issues_found": 1,
  "issues_fixed": 1,
  "remaining_issues": [],
  "used_llm": true
}
```

**Behavior**:
- If issues found, uses LLM to repair
- If repair fails, raises error
- Status is "repaired" if fixes were applied

---

### 7. Final Validator

**Purpose**: Hard syntactic and semantic validation

**Inputs**:
- `bt_xml` (str): XML from Conformance Agent

**Processing**:
- Pure validation (no LLM)
- XML syntax check via `ET.fromstring()`
- PAL v1 compliance check via `validate_bt_xml()`

**Output**: None (raises exception if invalid)

**Audit Log Entry**:
```json
{
  "agent": "FinalValidator",
  "status": "ok"|"error",
  "issues": []
}
```

**Behavior**:
- This is a HARD gate: if validation fails, pipeline aborts
- Ensures final BT is both syntactically valid XML and semantically valid PAL v1

---

### 8. Scorer Agent

**Purpose**: Evaluate BT quality and assign verdict

**Inputs**:
- `bt_xml` (str): Final validated BT XML
- `audit_log` (List[Dict]): Log entries from all previous agents

**Processing**:
- Uses LLM (text-only)
- Prompt: `prompts/scorer.md`
- Temperature: 0.7 (default)

**Output** (JSON):
```json
{
  "verdict": "ACCEPT"|"SKIP"|"REJECT",
  "total": 38,
  "scores": {
    "structural": 9,
    "robustness": 10,
    "compliance": 10,
    "patchability": 9
  },
  "comments": "The behavior tree demonstrates..."
}
```

**Audit Log Entry**:
```json
{
  "agent": "Scorer",
  "status": "ok",
  "verdict": "ACCEPT",
  "score": 38,
  "scores": {...},
  "comments": "...",
  "used_llm": true
}
```

**Behavior**:
- Scores on multiple dimensions (structural, robustness, compliance, patchability)
- Total score typically out of 40
- Verdict determines if BT should be included in dataset

---

## Final Output

The `AgenticTeacherLoop.generate_bt()` method returns:

```python
{
  "bt_xml": "<root>...</root>",          # Final BT XML string
  "audit_log": [...],                     # List of all agent logs
  "score": 38,                            # Score from Scorer Agent
  "verdict": "ACCEPT",                    # ACCEPT|SKIP|REJECT
  "steps": [...]                          # Optional: intermediate outputs
}
```

### Steps Array (if `record_steps=True`):
```python
[
  {
    "agent": "feasibility",
    "content": "{...}",  # JSON string
    "ext": "json"
  },
  {
    "agent": "scene_analysis",
    "content": "semantic_state: ...",
    "ext": "txt"
  },
  {
    "agent": "architect",
    "bt_xml": "<root>...</root>"
  },
  {
    "agent": "robustness",
    "bt_xml": "<root>...</root>"
  },
  # ... etc
]
```

---

## PAL v1 Primitives

All generated BTs must use ONLY these primitives:

**Manipulation**:
- `GRASP` - Pick up an object
- `RELEASE` - Release held object
- `PLACE_ON_TOP` - Place object on surface
- `PLACE_INSIDE` - Place object inside container
- `PLACE_NEAR_HEATING_ELEMENT` - Place near heat source

**Navigation**:
- `NAVIGATE_TO` - Move to location/object

**Container Operations**:
- `OPEN` - Open container/door
- `CLOSE` - Close container/door

**Appliance Operations**:
- `TOGGLE_ON` - Turn on appliance
- `TOGGLE_OFF` - Turn off appliance

**Cleaning**:
- `WIPE` - Wipe/clean surface
- `SOAK_UNDER` - Rinse under faucet
- `SOAK_INSIDE` - Soak in container

**Cutting**:
- `CUT` - Cut/slice object

**Ghost / Extended (symbolic)**:
- `PUSH` - Push object
- `POUR` - Pour contents (symbolic)
- `FOLD` - Fold deformable (symbolic)
- `UNFOLD` - Unfold deformable (symbolic)
- `SCREW` - Screw/unscrew (symbolic)
- `HANG` - Hang object (symbolic)

---

## Anti-Leakage Rule

**Critical constraint**: To prevent train-test contamination:

- **Frame 0**: ONLY reliable observation of initial world state
- **Frames 1-8**: Use ONLY for reasoning about failure risks, NOT to infer task progress

This ensures the model doesn't learn to "cheat" by looking at future frames to understand what actions were taken.

---

## Error Handling

### SkipEpisode Exception
- Raised by Feasibility Agent if task is infeasible
- Captured by dataset generation loop
- Episode is skipped but pipeline continues with next episode

### Validation Errors
- Any agent can raise `ValueError` if output is invalid
- Pipeline aborts for that episode
- Error is logged in audit log

### LLM Failures
- Each agent uses `llm_client.complete_with_fallback()`
- Automatic retry with fallback models if primary fails
- Configurable retry logic in `AzureLLMClient`

---

## Configuration

### Agent Toggling
All agents except Architect can be disabled:

```python
agents = {
    "feasibility": FeasibilityAgent(enabled=False),  # Skip feasibility
    "scene_analysis": SceneAnalysisAgent(enabled=True),
    "architect": ArchitectAgent(llm_client=client),  # Always required
    "robustness": RobustnessAgent(enabled=True, num_attempts=3),
    "recovery_planner": RecoveryPlannerAgent(enabled=True),
    "subtree_enablement": SubtreeEnablementAgent(enabled=True),
    "conformance": ConformanceAgent(enabled=True),
    "scorer": ScorerAgent(llm_client=client),
}
```

### Custom Pipeline
```python
loop = AgenticTeacherLoop(
    agents=agents,
    pipeline=[
        "robustness",
        "recovery_planner",
        "subtree_enablement",
        "conformance",
    ]
)
```

The pipeline only includes agents that transform BT XML. Feasibility, SceneAnalysis, and Architect are handled separately as special cases.

---

## Example Execution Trace

**Input**:
- Instruction: `"put down blue can"`
- Contact sheet: 9 frames showing robot holding blue can above table

**Execution**:

1. **Feasibility**: ✓ Feasible (GRASP, RELEASE)
2. **Scene Analysis**: "Blue can already grasped, table clear, placement spot between objects..."
3. **Architect**: Generates linear sequence: NAVIGATE_TO table → PLACE_ON_TOP → RELEASE
4. **Robustness**: Wraps PLACE_ON_TOP with retry + fallback recovery
5. **Recovery Planner**: Normalizes redundant patterns; ensures meaningful fallbacks
6. **SubTree Enablement**: Extracts T_Manipulate_Place SubTree
7. **Conformance**: No issues found
8. **Final Validator**: ✓ Valid XML and PAL v1
9. **Scorer**: Score 38/40, Verdict ACCEPT

**Output**:
```xml
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="put_down_blue_can">
      <SubTree ID="T_Navigate" target="table"/>
      <SubTree ID="T_Manipulate_Place_OnTop" target="table"/>
      <Action ID="RELEASE"/>
    </Sequence>
  </BehaviorTree>

  <BehaviorTree ID="T_Navigate">
    <RetryUntilSuccessful num_attempts="3">
      <Action ID="NAVIGATE_TO" obj="{target}"/>
    </RetryUntilSuccessful>
  </BehaviorTree>

  <BehaviorTree ID="T_Manipulate_Place_OnTop">
    <RetryUntilSuccessful num_attempts="3">
      <Action ID="PLACE_ON_TOP" obj="{target}"/>
    </RetryUntilSuccessful>
  </BehaviorTree>
</root>
```

---

## Known Issues & Limitations

### 1. Feasibility-SceneAnalysis Disconnect
- Feasibility lists required primitives without seeing actual initial state details
- Scene Analysis may reveal that some primitives are unnecessary (e.g., object already grasped)
- This can lead to over-conservative primitive lists

### 2. Frame 1-8 Underutilization
- Prompts tell agents to use frames 1-8 for risk assessment
- No explicit output field for identified risks
- Unclear if LLM actually uses these frames effectively

### 3. SubTree Parameter Mismatches
- SubTree Enablement may generate parameter mismatches
- Conformance agent must repair these via LLM
- Ideally SubTree Enablement should track parameters correctly from the start

### 4. Prompt Ambiguities
- "required_primitives" ambiguous: from scratch vs. from current state?
- No explicit guidance on output verbosity vs. conciseness
- Some prompts lack concrete examples

### 5. BehaviorTree.CPP Runtime Constraints (Important)
- `root@main_tree_to_execute` must match the main `<BehaviorTree ID="...">`.
- Each `<BehaviorTree>` must have exactly one root child node (wrap multiple steps in `<Sequence>`).
- Avoid duplicate `RELEASE` in single-object tasks (keep it once; do not place it both in main and inside place-subtrees).

---

## Future Improvements

1. **Structured Initial State**: Feasibility should output structured state info (gripper status, object locations)
2. **Risk Field**: Add `identified_risks` to Feasibility/SceneAnalysis output
3. **Primitive Ordering**: Clarify that `required_primitives` should be in execution order
4. **Better Examples**: Add few-shot examples to prompts for consistency
5. **Node ID Assignment**: Add dedicated agent to assign unique IDs to all nodes (improves patchability)
6. **Metrics**: Track primitive list accuracy, conformance repair frequency, etc.
7. **Schema Validation**: Consider dedicated schema validation agent before conformance

---

## Quick Reference: Agent I/O Summary

| Agent | Input | Output | Format | LLM? |
|-------|-------|--------|--------|------|
| Feasibility | instruction, contact_sheet | feasibility JSON | JSON | ✓ (vision) |
| Scene Analysis | instruction, contact_sheet | scene description | Markdown | ✓ (vision) |
| Architect | instruction, contact_sheet, scene_analysis | initial BT | XML | ✓ (vision) |
| Robustness | BT XML | enhanced BT with retries | XML | ✓ (text) |
| SubTree Enablement | BT XML | refactored BT with SubTrees | XML | ✓ (text) |
| Conformance | BT XML | PAL-compliant BT | XML | ✓ (text) |
| Final Validator | BT XML | validation errors (or none) | - | ✗ |
| Scorer | BT XML, audit_log | verdict, score, comments | JSON | ✓ (text) |

---

## Related Files

- `teacher_loop.py`: Main orchestration logic
- `agents/*.py`: Individual agent implementations
- `prompts/*.md`: LLM prompts for each agent
- `llm_client.py`: Azure OpenAI client with fallback
- `bt_checks/`: Validation utilities
- `bt_repair/`: Repair utilities for conformance

---

## Version History

- **v1.0** (Current): Initial stable pipeline with 6 configurable agents
  - Feasibility, SceneAnalysis, Architect, Robustness, SubtreeEnablement, Conformance, Scorer
  - Modular design with enable/disable flags
  - PAL v1 compliance enforcement
  - Automatic retry and recovery insertion
