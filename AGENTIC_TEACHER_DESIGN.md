# Agentic Teacher Design - High-Quality Proposer Dataset Generation

**Purpose:** Generate a proposer training dataset where every BT is:
1. **Executable** - Uses only BEHAVIOR-1K primitives (PAL v1)
2. **Robust** - Includes guards, recovery, timeouts
3. **Patchable** - Structured to be easily modified by validator
4. **Audited** - Comes with logs of checks passed/failed

**Key Insight:** A simple teacher LLM produces linear, brittle BTs. An **agentic teacher loop** with multiple specialized agents produces structured, robust, patchable BTs suitable for training both proposer AND validator.

---

## 1. Agentic Teacher Loop Architecture

### 1.1 Overview

```
Input: (instruction, observation, PAL_v1, BT_conventions)
  ↓
┌─────────────────── AGENTIC TEACHER LOOP ───────────────────┐
│                                                              │
│  A. Architect Agent                                          │
│     → Draft structured BT skeleton (phases + recovery)      │
│                                                              │
│  B. Conformance Agent                                        │
│     → Enforce PAL whitelist, ports, types, parameters       │
│                                                              │
│  C. Blackboard/Schema Agent                                  │
│     → Check key flow, naming, preconditions                 │
│                                                              │
│  D. Robustness Agent                                         │
│     → Inject guards, recovery, retry budgets, timeouts      │
│                                                              │
│  E. Subtree Enablement Agent                                 │
│     → Factor into replaceable subtrees (Perception,         │
│       Navigate, Manipulate, Verify, Recover)                │
│                                                              │
│  F. ID/Patchability Agent                                    │
│     → Assign stable node IDs, subtree IDs for O(1) patches  │
│                                                              │
│  G. Scorer/Judge Agent                                       │
│     → Reject brittle/unpatchable trees, request repair      │
│                                                              │
│  If rejected: repair iteration (back to step needing fix)   │
│  If accepted: proceed to output                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
  ↓
Output: (bt.xml, audit_log.json, subtree_map.json)
```

### 1.2 Why This Approach?

**Simple Teacher (bad):**
- LLM generates XML in one shot
- No checks, no repair
- Result: linear, brittle BTs
- Validator has no clear patch points

**Agentic Teacher (good):**
- Multi-agent system with specialized roles
- Iterative refinement with explicit checks
- Result: structured, robust, patchable BTs
- Audit logs reveal failure modes → validator training data

---

## 2. Agent Specifications

### Agent A: Architect Agent

**Role:** Draft high-level BT structure

**Input:**
- Task instruction
- Observation (key frames)
- PAL v1 primitive list
- BT conventions

**Output:** Skeleton BT with phases

**Strategy:**
1. Decompose task into phases (e.g., "search → navigate → grasp → transport → place")
2. Create top-level Sequence with phase subtrees
3. Identify critical failure points → add Fallback wrappers
4. Add recovery regions for each phase

**Example Output:**
```xml
<BehaviorTree ID="MainTree">
  <Sequence name="root">
    <!-- Phase 1: Locate target -->
    <Fallback name="phase_locate">
      <SubTree ID="T_Perception" target="{target}"/>
      <SubTree ID="T_Recovery_Perception" target="{target}"/>
    </Fallback>

    <!-- Phase 2: Navigate -->
    <SubTree ID="T_Navigate" target="{target}"/>

    <!-- Phase 3: Manipulate -->
    <Fallback name="phase_grasp">
      <SubTree ID="T_Manipulate_Grasp" target="{target}"/>
      <SubTree ID="T_Recovery_Grasp" target="{target}"/>
    </Fallback>

    <!-- Phase 4: Transport -->
    <SubTree ID="T_Navigate" target="{destination}"/>

    <!-- Phase 5: Place -->
    <SubTree ID="T_Manipulate_Place" target="{destination}"/>
  </Sequence>
</BehaviorTree>

<!-- Subtree definitions -->
<BehaviorTree ID="T_Perception">
  <Action ID="NAVIGATE_TO" name="nav_percep_01" obj="{target}"/>
</BehaviorTree>

<BehaviorTree ID="T_Manipulate_Grasp">
  <Action ID="GRASP" name="grasp_01" obj="{target}"/>
</BehaviorTree>

<!-- ... more subtrees ... -->
```

**Checks (thinking):**
- Does decomposition match task semantics?
- Are phases in logical order?
- Is recovery included for failure-prone steps?

---

### Agent B: Conformance Agent

**Role:** Enforce PAL v1 compliance

**Input:** Skeleton BT from Architect

**Output:** BT with validated primitives and parameters

**Checks:**
1. **Library compliance:** Every `<Action>` uses a PAL v1 primitive
   - Valid: `<Action ID="GRASP" obj="cup"/>`
   - Invalid: `<Action ID="DetectObject" target="cup"/>` (not in PAL v1)

2. **Parameter compliance:** All parameters match PAL specification
   - Check required params present
   - Check param types (object_name, int, float, etc.)
   - Check param values in allowed ranges/vocabulary

3. **No invented actions:** Reject any action not in PAL v1

**Repair Strategy:**
- If invalid primitive found → suggest closest PAL v1 equivalent
- If missing parameter → add default or request from user
- If impossible to map → flag for manual review

**Example:**
```
Input:  <Action ID="DetectObject" target="cup"/>
Check:  "DetectObject" not in PAL v1
Repair: Map to <Action ID="NAVIGATE_TO" obj="cup"/> (implies perception)
        OR flag: "This action has no direct equivalent in PAL v1"
```

**Audit Log Entry:**
```json
{
  "agent": "Conformance",
  "check": "library_compliance",
  "node": "detect_01",
  "issue": "Invalid primitive 'DetectObject'",
  "repair": "Mapped to NAVIGATE_TO",
  "status": "fixed"
}
```

---

### Agent C: Blackboard/Schema Agent

**Role:** Validate blackboard key usage and data flow

**Input:** Conformance-validated BT

**Output:** BT with consistent blackboard schema

**Checks:**
1. **Key naming consistency:**
   - Use standard keys: `target_obj`, `grasp_pose`, `destination`, `container`
   - No ad-hoc or "mystery" keys

2. **Write-before-read:**
   - If node reads `grasp_pose`, ensure earlier node writes it
   - Flag missing writes

3. **Key types:**
   - Ensure keys have consistent types (string, pose, state, etc.)

4. **Precondition checks:**
   - Actions requiring state (e.g., held object) have checks
   - Example: Before `PLACE_ON_TOP`, check object is held

**Repair Strategy:**
- Add missing blackboard writes
- Insert precondition checks
- Standardize key names

**Example:**
```xml
<!-- Before repair -->
<Action ID="PLACE_ON_TOP" obj="{destination}"/>  <!-- Assumes object held -->

<!-- After repair -->
<Sequence>
  <Condition ID="CheckBlackboard" key="held_object" expected="true"/>
  <Action ID="PLACE_ON_TOP" obj="{destination}"/>
</Sequence>
```

**Note:** PAL v1 doesn't have explicit Condition nodes yet. We might:
- Add `CheckBlackboard` as a utility condition
- Or rely on BEHAVIOR-1K's implicit state tracking
- **Decision needed:** Should we extend PAL v1 with utility conditions?

---

### Agent D: Robustness Agent

**Role:** Inject guards, recovery, retry logic

**Input:** Schema-validated BT

**Output:** Robust BT with error handling

**Checks:**
1. **Visibility guards:**
   - Before manipulating object, ensure it's visible/accessible
   - Add checks or recovery if missing

2. **Retry budgets:**
   - Wrap failure-prone actions in `RetryUntilSuccessful`
   - Set reasonable `num_attempts` (3-5)

3. **Timeouts:**
   - Add timeout parameters to actions
   - Ensure termination even if action hangs

4. **Recovery branches:**
   - For critical failures, add Fallback with recovery
   - Example: If GRASP fails → re-navigate → retry

**Repair Strategy:**
```xml
<!-- Before: brittle -->
<Action ID="GRASP" obj="cup"/>

<!-- After: robust -->
<RetryUntilSuccessful num_attempts="3">
  <Fallback>
    <Action ID="GRASP" obj="cup"/>
    <Sequence name="recovery_grasp">
      <Action ID="NAVIGATE_TO" obj="cup"/>  <!-- Re-approach -->
      <Action ID="GRASP" obj="cup"/>
    </Sequence>
  </Fallback>
</RetryUntilSuccessful>
```

**Audit Log:**
```json
{
  "agent": "Robustness",
  "check": "retry_budget",
  "node": "grasp_01",
  "issue": "No retry wrapper",
  "repair": "Added RetryUntilSuccessful(3)",
  "status": "fixed"
}
```

---

### Agent E: Subtree Enablement Agent

**Role:** Factor BT into replaceable subtrees

**Input:** Robust BT (may be monolithic)

**Output:** BT with modular subtrees

**Strategy:**
1. Identify logical **subtask boundaries**:
   - T_Perception(target) - Find and observe object
   - T_Navigate(target) - Move to object/location
   - T_Manipulate(action, target) - Perform manipulation
   - T_Verify(goal_state) - Check postcondition
   - T_Recovery(failure_class) - Handle specific failure

2. Extract each subtask into a `<BehaviorTree ID="T_...">` block

3. Replace inline code with `<SubTree ID="..." />`

4. Ensure subtrees are **small** (5-15 nodes) and **single-responsibility**

**Before (monolithic):**
```xml
<BehaviorTree ID="MainTree">
  <Sequence>
    <Action ID="NAVIGATE_TO" obj="cup"/>
    <Action ID="GRASP" obj="cup"/>
    <Action ID="NAVIGATE_TO" obj="table"/>
    <Action ID="PLACE_ON_TOP" obj="table"/>
    <Action ID="RELEASE"/>
  </Sequence>
</BehaviorTree>
```

**After (modular):**
```xml
<BehaviorTree ID="MainTree">
  <Sequence name="root">
    <SubTree ID="T_Navigate" target="cup"/>
    <SubTree ID="T_Manipulate_Grasp" target="cup"/>
    <SubTree ID="T_Navigate" target="table"/>
    <SubTree ID="T_Manipulate_Place" target="table"/>
  </Sequence>
</BehaviorTree>

<BehaviorTree ID="T_Navigate">
  <Action ID="NAVIGATE_TO" name="nav_01" obj="{target}"/>
</BehaviorTree>

<BehaviorTree ID="T_Manipulate_Grasp">
  <Action ID="GRASP" name="grasp_01" obj="{target}"/>
</BehaviorTree>

<BehaviorTree ID="T_Manipulate_Place">
  <Sequence>
    <Action ID="PLACE_ON_TOP" name="place_01" obj="{target}"/>
    <Action ID="RELEASE" name="release_01"/>
  </Sequence>
</BehaviorTree>
```

**Subtree Map Output:**
```json
{
  "subtrees": [
    {
      "id": "T_Navigate",
      "role": "navigation",
      "params": ["target"],
      "node_count": 1,
      "patchable": true
    },
    {
      "id": "T_Manipulate_Grasp",
      "role": "manipulation",
      "params": ["target"],
      "node_count": 1,
      "patchable": true
    },
    {
      "id": "T_Manipulate_Place",
      "role": "manipulation",
      "params": ["target"],
      "node_count": 2,
      "patchable": true
    }
  ]
}
```

**Why Subtrees?**
- Validator can replace entire subtree (e.g., swap T_Recovery_Grasp)
- Clear patch boundaries
- Reusable components

---

### Agent F: ID/Patchability Agent

**Role:** Assign stable IDs for O(1) patching

**Input:** Subtree-modularized BT

**Output:** BT with stable node instance IDs

**Strategy:**
1. Every node gets unique `name="nXXX"` ID
2. ID format: `<role>_<index>` (e.g., `nav_01`, `grasp_02`)
3. IDs are stable across regeneration (deterministic based on position)
4. Subtrees get IDs: `T_<Role>_<Variant>` (e.g., `T_Navigate_ToObject`, `T_Recovery_Grasp`)

**ID Assignment Rules:**
- **Actions**: `<primitive>_<seq>` → `grasp_01`, `place_01`
- **Composites**: `<type>_<seq>` → `seq_00`, `fallback_01`
- **Subtrees**: `T_<Role>_<Context>` → `T_Navigate`, `T_Manipulate_Grasp`

**Example:**
```xml
<BehaviorTree ID="MainTree">
  <Sequence name="seq_00">
    <SubTree ID="T_Navigate" name="subtree_01" target="cup"/>
    <SubTree ID="T_Manipulate_Grasp" name="subtree_02" target="cup"/>
  </Sequence>
</BehaviorTree>

<BehaviorTree ID="T_Navigate">
  <Action ID="NAVIGATE_TO" name="nav_01" obj="{target}"/>
</BehaviorTree>

<BehaviorTree ID="T_Manipulate_Grasp">
  <RetryUntilSuccessful name="retry_01" num_attempts="3">
    <Action ID="GRASP" name="grasp_01" obj="{target}"/>
  </RetryUntilSuccessful>
</BehaviorTree>
```

**Patchability Map:**
```json
{
  "main_tree_nodes": {
    "seq_00": {"type": "Sequence", "path": "/MainTree/seq_00", "children": ["subtree_01", "subtree_02"]},
    "subtree_01": {"type": "SubTree", "path": "/MainTree/seq_00/subtree_01", "subtree_id": "T_Navigate"},
    "subtree_02": {"type": "SubTree", "path": "/MainTree/seq_00/subtree_02", "subtree_id": "T_Manipulate_Grasp"}
  },
  "subtree_nodes": {
    "T_Navigate": {
      "nav_01": {"type": "Action", "primitive": "NAVIGATE_TO", "path": "/T_Navigate/nav_01"}
    },
    "T_Manipulate_Grasp": {
      "retry_01": {"type": "RetryUntilSuccessful", "path": "/T_Manipulate_Grasp/retry_01", "children": ["grasp_01"]},
      "grasp_01": {"type": "Action", "primitive": "GRASP", "path": "/T_Manipulate_Grasp/retry_01/grasp_01"}
    }
  }
}
```

**Validator Patch Operations:**
```json
{
  "patch_type": "replace_subtree",
  "target": "subtree_02",
  "replacement": "<BehaviorTree ID='T_Manipulate_Grasp_v2'>...</BehaviorTree>"
}
```

OR

```json
{
  "patch_type": "modify_attribute",
  "target_node_id": "grasp_01",
  "attribute": "obj",
  "new_value": "cup_handle"
}
```

---

### Agent G: Scorer/Judge Agent

**Role:** Evaluate BT quality, reject brittle trees

**Input:** Fully processed BT + audit log

**Output:** ACCEPT or REJECT + feedback

**Scoring Criteria:**

1. **Structural Quality (0-10):**
   - Depth: 3-6 (not too shallow, not too deep)
   - Branching factor: >1.5 (not linear)
   - Subtree count: 3-8 (modular but not excessive)

2. **Robustness (0-10):**
   - Recovery branches present: +2
   - Retry wrappers on critical actions: +2
   - Timeout parameters present: +2
   - Precondition checks present: +2
   - Guard conditions present: +2

3. **Patchability (0-10):**
   - All nodes have IDs: +3
   - Subtrees well-defined: +3
   - Subtrees < 15 nodes each: +2
   - Clear patch points identified: +2

4. **Compliance (0-10):**
   - 100% PAL v1 primitives: +5
   - All parameters valid: +3
   - Blackboard schema consistent: +2

**Accept Threshold:** Total score ≥ 30/40

**Rejection Reasons:**
- Linear (no branching) → Request Architect to add Fallbacks
- Too brittle (no recovery) → Request Robustness to add guards
- Monolithic (no subtrees) → Request Subtree Enablement to refactor
- Invalid primitives → Request Conformance to fix

**Audit Log Entry:**
```json
{
  "agent": "Scorer",
  "scores": {
    "structural": 8,
    "robustness": 9,
    "patchability": 10,
    "compliance": 10
  },
  "total": 37,
  "threshold": 30,
  "verdict": "ACCEPT",
  "comments": "Well-structured BT with good recovery and clear patch points."
}
```

---

## 3. Explicit Checks ("Thinking About Checks")

Each agent performs explicit checks and logs results. Here's the complete checklist:

### 3.1 Library Compliance
- [ ] Every `<Action>` ID is in PAL v1 (14 primitives)
- [ ] No fictional primitives (DetectObject, MoveAbove, etc.)
- [ ] All primitives spelled correctly

### 3.2 Parameter Sanity
- [ ] All required parameters present
- [ ] Parameter types match PAL spec (object_name, int, etc.)
- [ ] Object names exist in scene vocabulary
- [ ] Numeric ranges reasonable (timeouts: 500-5000ms, attempts: 1-5, etc.)
- [ ] No `null` or `undefined` values

### 3.3 Control Flow Sanity
- [ ] Sequence semantics correct (fail-on-first-failure)
- [ ] Fallback semantics correct (succeed-on-first-success)
- [ ] No infinite retry loops (RetryUntilSuccessful has max attempts)
- [ ] Parallel has success/failure thresholds if used
- [ ] Termination conditions present (no endless loops)

### 3.4 Observability Gates
- [ ] Before acting on object, ensure it's observed (implicit in NAVIGATE_TO)
- [ ] Before GRASP, object should be visible/reachable
- [ ] Before PLACE_ON_TOP, object should be held

**Note:** BEHAVIOR-1K primitives handle much of this internally. We may not need explicit gates.

### 3.5 Pre/Postconditions
- [ ] GRASP requires: object visible, hand free
- [ ] PLACE_* requires: object held
- [ ] OPEN/CLOSE requires: object reachable
- [ ] RELEASE requires: object held

**Implementation:** Add conditions or rely on BEHAVIOR-1K's built-in checks?

### 3.6 Blackboard Discipline
- [ ] Consistent key names (target_obj, destination, held_object)
- [ ] Keys written before read
- [ ] No mystery keys
- [ ] Key types consistent

**Current Status:** BEHAVIOR-1K may handle this internally. Verify if explicit blackboard needed.

### 3.7 Patch Locality
- [ ] Failures of primitive X recoverable by replacing local subtree
- [ ] Subtrees small enough to patch (5-15 nodes)
- [ ] Subtree IDs stable and documented
- [ ] Node instance IDs unique and stable

### 3.8 Style Constraints
- [ ] Modular structure (subtrees, not monolith)
- [ ] Named regions for logical phases
- [ ] Not overly linear (branching factor >1.5)
- [ ] Not overly deep (depth 3-6)

---

## 4. Subtree Conventions

### 4.1 Subtree Types (Standard Library)

**T_Perception(target):**
```xml
<BehaviorTree ID="T_Perception">
  <Action ID="NAVIGATE_TO" name="nav_percep_01" obj="{target}"/>
</BehaviorTree>
```
**Purpose:** Locate and observe target (NAVIGATE_TO implies perception in BEHAVIOR-1K)

**T_Navigate(target):**
```xml
<BehaviorTree ID="T_Navigate">
  <Action ID="NAVIGATE_TO" name="nav_01" obj="{target}"/>
</BehaviorTree>
```
**Purpose:** Move to target location/object

**T_Manipulate_Grasp(target):**
```xml
<BehaviorTree ID="T_Manipulate_Grasp">
  <RetryUntilSuccessful name="retry_01" num_attempts="3">
    <Action ID="GRASP" name="grasp_01" obj="{target}"/>
  </RetryUntilSuccessful>
</BehaviorTree>
```
**Purpose:** Grasp object with retry

**T_Manipulate_Place(target, action):**
```xml
<BehaviorTree ID="T_Manipulate_Place">
  <Sequence>
    <Action ID="PLACE_ON_TOP" name="place_01" obj="{target}"/>
    <Action ID="RELEASE" name="release_01"/>
  </Sequence>
</BehaviorTree>
```
**Purpose:** Place held object (PLACE_ON_TOP, PLACE_INSIDE, etc.) and release

**T_Manipulate_Open(target):**
```xml
<BehaviorTree ID="T_Manipulate_Open">
  <Action ID="OPEN" name="open_01" obj="{target}"/>
</BehaviorTree>
```
**Purpose:** Open container/door

**T_Manipulate_Toggle(target, state):**
```xml
<BehaviorTree ID="T_Manipulate_Toggle">
  <Action ID="TOGGLE_ON" name="toggle_01" obj="{target}"/>
</BehaviorTree>
```
**Purpose:** Toggle object on/off

**T_Recovery_Grasp(target):**
```xml
<BehaviorTree ID="T_Recovery_Grasp">
  <Sequence>
    <Action ID="NAVIGATE_TO" name="nav_recovery_01" obj="{target}"/>
    <Action ID="GRASP" name="grasp_recovery_01" obj="{target}"/>
  </Sequence>
</BehaviorTree>
```
**Purpose:** Recovery strategy for failed grasp (re-navigate + retry)

**T_Recovery_Navigate(target):**
```xml
<BehaviorTree ID="T_Recovery_Navigate">
  <Fallback>
    <Action ID="NAVIGATE_TO" name="nav_retry_01" obj="{target}"/>
    <!-- Could add alternative navigation strategy -->
  </Fallback>
</BehaviorTree>
```
**Purpose:** Recovery for failed navigation

### 4.2 Subtree Naming Convention

**Format:** `T_<Role>_<Action>_<Context>`

**Examples:**
- `T_Perception` - General perception
- `T_Navigate` - General navigation
- `T_Manipulate_Grasp` - Manipulation: grasping
- `T_Manipulate_Place_OnTop` - Manipulation: placing on surface
- `T_Manipulate_Place_Inside` - Manipulation: placing inside container
- `T_Recovery_Grasp` - Recovery from grasp failure
- `T_Verify_Placed` - Verify placement succeeded

### 4.3 Parameter Passing to Subtrees

**Mechanism:** Use attribute substitution with `{param}` syntax

**Example:**
```xml
<BehaviorTree ID="MainTree">
  <SubTree ID="T_Navigate" target="cup"/>
</BehaviorTree>

<BehaviorTree ID="T_Navigate">
  <Action ID="NAVIGATE_TO" name="nav_01" obj="{target}"/>
</BehaviorTree>
```

**At runtime:** `{target}` → `"cup"`

**Alternative (if BehaviorTree.CPP v3 doesn't support param substitution):**
Use blackboard keys:
```xml
<BehaviorTree ID="MainTree">
  <Sequence>
    <SetBlackboard key="target_obj" value="cup"/>
    <SubTree ID="T_Navigate"/>
  </Sequence>
</BehaviorTree>

<BehaviorTree ID="T_Navigate">
  <Action ID="NAVIGATE_TO" name="nav_01" obj="{target_obj}"/>
</BehaviorTree>
```

**Decision needed:** Which parameter-passing mechanism does BehaviorTree.CPP v3 support?

---

## 5. Implementation Modules

### 5.1 Directory Structure

```
embodied_bt_brain/
├── agentic_teacher/                   (NEW: agentic teacher implementation)
│   ├── __init__.py
│   ├── teacher_loop.py                (Main orchestrator)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── architect.py               (Agent A)
│   │   ├── conformance.py             (Agent B)
│   │   ├── schema.py                  (Agent C)
│   │   ├── robustness.py              (Agent D)
│   │   ├── subtree_enablement.py      (Agent E)
│   │   ├── id_patchability.py         (Agent F)
│   │   └── scorer.py                  (Agent G)
│   ├── bt_checks/                     (Static validators)
│   │   ├── __init__.py
│   │   ├── library_compliance.py      (Check against PAL v1)
│   │   ├── parameter_validation.py    (Type/range checks)
│   │   ├── control_flow.py            (Sequence/Fallback semantics)
│   │   ├── blackboard.py              (Key usage checks)
│   │   └── patchability.py            (Patch locality heuristics)
│   ├── bt_repair/                     (Repair strategies)
│   │   ├── __init__.py
│   │   ├── rule_based.py              (Rule-based fixes)
│   │   └── llm_repair.py              (LLM-driven repair)
│   └── config/
│       ├── agent_config.yaml          (Agent parameters)
│       └── scoring_thresholds.yaml    (Scorer thresholds)
│
├── primitive_library/                 (PAL definition + schema)
│   ├── __init__.py
│   ├── pal_v1.json                    (14 primitives spec)
│   ├── subtree_templates.json         (Standard subtree library)
│   └── validator.py                   (Validate BT against PAL)
│
├── dataset_proposer_agentic/          (Dataset generation orchestrator)
│   ├── __init__.py
│   ├── generate_dataset.py            (Main script)
│   ├── input_sources/
│   │   ├── behavior1k_demos.py        (Load BEHAVIOR-1K demos)
│   │   └── oxe_episodes.py            (Load OXE episodes - future)
│   ├── output_writers/
│   │   ├── dataset_writer.py          (Write JSONL dataset)
│   │   └── audit_logger.py            (Write audit logs)
│   └── utils/
│       ├── frame_selection.py         (Select key frames)
│       └── instruction_parser.py      (Parse task descriptions)
```

### 5.2 Key Modules

**`teacher_loop.py`** - Main orchestrator:
```python
class AgenticTeacherLoop:
    def __init__(self, pal_spec, bt_conventions, agents):
        self.agents = agents  # [Architect, Conformance, ..., Scorer]
        self.pal_spec = pal_spec
        self.bt_conventions = bt_conventions

    def generate_bt(self, instruction, observation):
        # Step 1: Architect drafts skeleton
        bt_skeleton = self.agents['architect'].draft(instruction, observation)

        # Step 2-6: Refinement pipeline
        bt = bt_skeleton
        audit_log = []

        for agent_name in ['conformance', 'schema', 'robustness', 'subtree_enablement', 'id_patchability']:
            bt, agent_log = self.agents[agent_name].process(bt)
            audit_log.extend(agent_log)

        # Step 7: Scorer evaluates
        verdict, score, feedback = self.agents['scorer'].evaluate(bt, audit_log)

        if verdict == "REJECT":
            # Repair iteration (up to 3 tries)
            return self.repair_and_retry(bt, feedback, audit_log, max_retries=3)

        # Generate outputs
        subtree_map = extract_subtree_map(bt)

        return {
            "bt_xml": bt,
            "audit_log": audit_log,
            "subtree_map": subtree_map,
            "score": score
        }
```

**`bt_checks/library_compliance.py`** - PAL v1 validation:
```python
class LibraryComplianceChecker:
    def __init__(self, pal_spec):
        self.allowed_primitives = set(pal_spec['primitives'].keys())

    def check(self, bt_xml):
        tree = parse_xml(bt_xml)
        issues = []

        for action in tree.findall(".//Action"):
            primitive_id = action.get('ID')
            if primitive_id not in self.allowed_primitives:
                issues.append({
                    "node": action.get('name'),
                    "issue": f"Invalid primitive '{primitive_id}'",
                    "severity": "error"
                })

        return issues
```

**`agents/conformance.py`** - Conformance agent:
```python
class ConformanceAgent:
    def __init__(self, pal_spec, llm_client):
        self.checker = LibraryComplianceChecker(pal_spec)
        self.llm_client = llm_client
        self.pal_spec = pal_spec

    def process(self, bt_xml):
        issues = self.checker.check(bt_xml)

        if not issues:
            return bt_xml, []

        # Attempt repair
        repair_prompt = self._build_repair_prompt(bt_xml, issues)
        repaired_bt = self.llm_client.generate(repair_prompt)

        # Re-check
        new_issues = self.checker.check(repaired_bt)

        audit_log = [{
            "agent": "Conformance",
            "issues_found": len(issues),
            "issues_fixed": len(issues) - len(new_issues),
            "details": issues
        }]

        return repaired_bt, audit_log
```

---

## 6. Dataset Generation Workflow

### 6.1 Input Source: BEHAVIOR-1K Demonstrations

**Step 1:** Download demonstration from HuggingFace
```python
# demo structure
demo = {
    "task_name": "turning_on_radio",
    "task_description": "Turn on the radio in the living room",
    "observations": [rgb_frame_0, rgb_frame_1, ..., rgb_frame_N],
    "actions": [
        {"primitive": "NAVIGATE_TO", "obj": "radio"},
        {"primitive": "TOGGLE_ON", "obj": "radio"}
    ],
    "success": True
}
```

**Step 2:** Convert action sequence → BT skeleton
```python
def demo_to_bt_skeleton(demo):
    actions = demo['actions']

    # Simple linear skeleton
    bt_skeleton = f"""
    <BehaviorTree ID="MainTree">
      <Sequence name="root">
        {'\n'.join([f'<Action ID="{a["primitive"]}" obj="{a["obj"]}"/>' for a in actions])}
      </Sequence>
    </BehaviorTree>
    """

    return bt_skeleton
```

**Step 3:** Feed to agentic teacher
```python
teacher = AgenticTeacherLoop(pal_spec, bt_conventions, agents)

result = teacher.generate_bt(
    instruction=demo['task_description'],
    observation=select_key_frames(demo['observations'])
)

# result = {
#     "bt_xml": "<BehaviorTree>...</BehaviorTree>",
#     "audit_log": [{...}, {...}],
#     "subtree_map": {...},
#     "score": 37
# }
```

**Step 4:** Write to dataset
```python
dataset_entry = {
    "instruction": demo['task_description'],
    "observation": key_frame_path,
    "bt_xml": result['bt_xml'],
    "metadata": {
        "source": "behavior1k_demo",
        "task_name": demo['task_name'],
        "score": result['score'],
        "audit_log": result['audit_log'],
        "subtree_map": result['subtree_map']
    }
}

write_to_jsonl(dataset_entry, "data/dataset_behavior1k/train/data.jsonl")
```

### 6.2 Dataset Output Format

**JSONL format for proposer training:**
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a BehaviorTree generator. Generate BehaviorTree.CPP v3 XML using only these primitives: [GRASP, PLACE_ON_TOP, PLACE_INSIDE, OPEN, CLOSE, NAVIGATE_TO, RELEASE, TOGGLE_ON, TOGGLE_OFF, WIPE, CUT, SOAK_UNDER, SOAK_INSIDE, PLACE_NEAR_HEATING_ELEMENT]."
    },
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "INSTRUCTION: Turn on the radio in the living room"},
        {"type": "image", "image": "images/turning_on_radio/frame_0000.jpg"}
      ]
    },
    {
      "role": "assistant",
      "content": [
        {"type": "text", "text": "<BehaviorTree ID=\"MainTree\">\n  <Sequence name=\"seq_00\">\n    <SubTree ID=\"T_Navigate\" name=\"subtree_01\" target=\"radio\"/>\n    <SubTree ID=\"T_Manipulate_Toggle\" name=\"subtree_02\" target=\"radio\" action=\"ON\"/>\n  </Sequence>\n</BehaviorTree>\n\n<BehaviorTree ID=\"T_Navigate\">\n  <Action ID=\"NAVIGATE_TO\" name=\"nav_01\" obj=\"{target}\"/>\n</BehaviorTree>\n\n<BehaviorTree ID=\"T_Manipulate_Toggle\">\n  <Action ID=\"TOGGLE_ON\" name=\"toggle_01\" obj=\"{target}\"/>\n</BehaviorTree>"}
      ]
    }
  ],
  "metadata": {
    "task_name": "turning_on_radio",
    "source": "behavior1k_demo",
    "score": 37,
    "subtree_map": {...}
  }
}
```

**Audit log (separate file for analysis):**
```json
{
  "episode_id": "turning_on_radio_001",
  "timestamp": "2025-12-24T10:30:00",
  "agents": [
    {
      "agent": "Architect",
      "output": "skeleton_bt.xml",
      "checks": ["phase_decomposition", "recovery_regions"],
      "status": "success"
    },
    {
      "agent": "Conformance",
      "issues_found": 0,
      "issues_fixed": 0,
      "status": "success"
    },
    {
      "agent": "Robustness",
      "checks_performed": ["retry_budget", "timeout_params"],
      "repairs": [
        {"node": "grasp_01", "repair": "Added RetryUntilSuccessful(3)"}
      ],
      "status": "success"
    },
    {
      "agent": "Scorer",
      "scores": {"structural": 8, "robustness": 9, "patchability": 10, "compliance": 10},
      "total": 37,
      "verdict": "ACCEPT"
    }
  ]
}
```

---

## 7. Open Questions & Decisions Needed

### 7.1 Blackboard vs Implicit State

**Question:** Do BEHAVIOR-1K primitives use explicit blackboard, or is state implicit?

**Options:**
1. **Implicit (likely):** Primitives track state internally (e.g., "is object held?")
2. **Explicit:** Need to manage blackboard keys

**Action:** Verify in BEHAVIOR-1K documentation or test script

### 7.2 Condition Nodes

**Question:** Do we need explicit Condition nodes (e.g., `IsObjectHeld`, `IsVisible`)?

**Options:**
1. **No:** BEHAVIOR-1K handles preconditions internally, primitives fail if conditions not met
2. **Yes:** Add utility conditions for explicit guards

**Current PAL v1:** No condition nodes listed

**Recommendation:** Start without, add only if needed for robustness

### 7.3 SubTree Parameter Passing

**Question:** How does BehaviorTree.CPP v3 handle SubTree parameters?

**Options:**
1. **Attribute substitution:** `<SubTree ID="T_Nav" target="cup"/>` → `{target}` replaced in subtree
2. **Blackboard only:** Must use `SetBlackboard` before `SubTree`

**Action:** Test with BehaviorTree.CPP or check documentation

### 7.4 LLM for Agents

**Question:** Which LLM to use for agents (Architect, Conformance repair, etc.)?

**Options:**
1. **GPT-4o / Claude Opus:** High quality, expensive
2. **GPT-4o-mini / Claude Sonnet:** Good balance
3. **Open models (Qwen2.5-72B, etc.):** Cheaper, self-hosted

**Recommendation:** GPT-4o-mini for development, switch to better model if quality issues

### 7.5 Repair Iteration Limit

**Question:** How many repair iterations before giving up?

**Recommendation:** Max 3 iterations per agent, max 2 full loop cycles

If still failing after 2 cycles → flag for manual review

---

## 8. Next Steps

### Week 1: Implement Core Checking & Repair
- [ ] Create `primitive_library/pal_v1.json` (14 primitives)
- [ ] Implement `bt_checks/library_compliance.py`
- [ ] Implement `bt_checks/parameter_validation.py`
- [ ] Implement `bt_checks/control_flow.py`
- [ ] Write unit tests for checkers

### Week 2: Implement Agents A-D
- [ ] Implement `agents/architect.py` (skeleton generation)
- [ ] Implement `agents/conformance.py` (PAL v1 enforcement)
- [ ] Implement `agents/schema.py` (blackboard validation - if needed)
- [ ] Implement `agents/robustness.py` (guards, retry, recovery)
- [ ] Test agents individually with hand-crafted inputs

### Week 3: Implement Agents E-G + Orchestrator
- [ ] Implement `agents/subtree_enablement.py` (modularization)
- [ ] Implement `agents/id_patchability.py` (ID assignment)
- [ ] Implement `agents/scorer.py` (quality evaluation)
- [ ] Implement `teacher_loop.py` (orchestrator)
- [ ] Test full loop with sample tasks

### Week 4: Dataset Generation Pipeline
- [ ] Download sample BEHAVIOR-1K demos
- [ ] Implement `demo_to_bt_skeleton` converter
- [ ] Implement `generate_dataset.py` orchestrator
- [ ] Generate pilot dataset (100 episodes)
- [ ] Analyze audit logs, refine agents

### Week 5: Scale & Validate
- [ ] Generate full dataset (1000+ episodes)
- [ ] Validate generated BTs (parse, execute sample in simulation)
- [ ] Compute dataset statistics
- [ ] Prepare for proposer training

---

## Conclusion

This agentic teacher design produces **high-quality, executable, patchable BTs** suitable for:
1. **Proposer training:** Learn to generate robust, structured BTs
2. **Validator training:** Clear patch points and audit logs reveal failure modes
3. **Runtime execution:** BTs actually work in BEHAVIOR-1K simulation

Key advantages over simple teacher:
- **Robustness:** Guards, recovery, retry logic built-in
- **Modularity:** Subtrees enable targeted patching
- **Compliance:** Guaranteed PAL v1 alignment
- **Quality:** Scorer rejects brittle trees
- **Traceability:** Audit logs document all checks and repairs

This is the foundation for a working MoE system.
