You are an expert in robotics and Behavior Trees (BT).
Your task: given (A) a brief TASK INSTRUCTION and (B) ONE contact‑sheet image containing K=9 frames (row‑major, labeled [0]..[8]), output ONLY TWO code blocks, in this exact order:
(1) a BehaviorTree.CPP v3 XML,
(2) a JSON metadata object (which MUST also include the field "local_annotations" with exactly 9 entries, one per tile).

INPUTS (authoritative)
- TASK INSTRUCTION: "Pick up a white plate, and then place it on the red plate."
- DATASET_ID: "utokyo_xarm_pick_and_place_0.1.0"
- EPISODE_ID: "episode_065"
- One contact‑sheet image 'episode.jpeg' arranged as 3×3 frames, labeled [0]..[8] (left→right, top→bottom).

PRIORITY & GROUNDING
- Ground the design in BOTH the instruction and the visual evidence from frames [0]..[8].
- If they conflict, prefer the frames; log the mismatch in metadata.assumptions.

STRICT FORMAT RULES
- Output NOTHING except the two code blocks.
- Use EXACTLY ONE <BehaviorTree ID="MainTree"> as root, with exactly one composite child.
- Do NOT include <root>, comments, extra sections, or tags not explicitly allowed.
- Each decorator has exactly ONE child.
- Use ONLY node IDs, ports, and values from the node library. No extra attributes or values.
- Numeric ports with allowed sets MUST snap to those sets. No decimals unless listed.
- If you make a mistake, FIX it silently and print the corrected final output.

ALLOWED TAGS (BehaviorTree.CPP v3)
- <BehaviorTree>, <Sequence>, <Fallback>, <Parallel success_threshold=".." failure_threshold="..">
- <Inverter>, <RetryUntilSuccessful num_attempts="..">, <Repeat num_cycles="..">, <Timeout timeout_ms="..">
- <Action ID="...">, <Condition ID="...">

NODE LIBRARY (USE ONLY THESE IDs/ports/values)
{
  "version": "btlib_v1.1",
  "composites": {
    "Sequence":  { "attrs": {} },
    "Fallback":  { "attrs": {} },
    "Parallel":  { "attrs": { "success_threshold": "int", "failure_threshold": "int" } }s
  },
  "decorators": {
    "Inverter":               { "attrs": {} },
    "RetryUntilSuccessful":   { "attrs": { "num_attempts": "int" } },
    "Repeat":                 { "attrs": { "num_cycles": "int" } },
    "Timeout":                { "attrs": { "timeout_ms": "int" } }
  },

  "actions": {
    "MoveTo":            { "ports": { "target": "string", "timeout_ms": "int" } },
    "MoveAbove":         { "ports": { "target": "string", "offset_z": "float", "timeout_ms": "int" } },
    "MoveDelta":         { "ports": { "axis": "string", "dist": "float", "timeout_ms": "int" } },

    "DetectObject":      { "ports": { "target": "string", "timeout_ms": "int" } },
    "ScanForTarget":     { "ports": { "target": "string", "pattern": "string", "max_attempts": "int", "timeout_ms": "int" } },

    "ComputeGraspPose":  { "ports": { "target": "string", "strategy": "string", "result_key": "string" } },
    "ApproachAndAlign":  { "ports": { "target": "string", "tolerance": "float", "timeout_ms": "int" } },
    "SetTCPYaw":         { "ports": { "yaw_deg": "int" } },

    "OpenGripper":       { "ports": { "width": "float", "timeout_ms": "int" } },
    "CloseGripper":      { "ports": { "force": "float", "timeout_ms": "int" } },
    "Pick":              { "ports": { "grasp_key": "string", "timeout_ms": "int" } },

    "PlaceAt":           { "ports": { "pose_key": "string", "yaw_deg": "int", "press_force": "float", "timeout_ms": "int" } },
    "LowerUntilContact": { "ports": { "speed": "string", "max_depth": "float", "force_threshold": "float", "timeout_ms": "int" } },

    "OpenContainer":     { "ports": { "target": "string", "container_type": "string", "timeout_ms": "int" } },
    "CloseContainer":    { "ports": { "target": "string", "container_type": "string", "timeout_ms": "int" } },

    "Push":              { "ports": { "target": "string", "distance": "float", "direction_deg": "int", "timeout_ms": "int" } },
    "WipeArea":          { "ports": { "area_id": "string", "pattern": "string", "passes": "int", "timeout_ms": "int" } },

    "Retreat":           { "ports": { "distance": "float", "timeout_ms": "int" } },
    "Wait":              { "ports": { "timeout_ms": "int" } },
    "SetBlackboard":     { "ports": { "key": "string", "value": "string" } }
  },

  "conditions": {
    "IsAt":              { "ports": { "target": "string" } },
    "IsObjectVisible":   { "ports": { "target": "string" } },
    "IsGraspStable":     { "ports": {} },
    "ObjectInGripper":   { "ports": { "target": "string" } },
    "ContactDetected":   { "ports": { "force_threshold": "float" } },
    "ContainerOpen":     { "ports": { "target": "string" } },
    "PoseAvailable":     { "ports": { "key": "string" } },
    "AtOrientation":     { "ports": { "yaw_deg": "int" } }
  },

  "port_value_spaces": {
    "timeout_ms":   [400, 500, 800, 1200, 1500, 2000],
    "force":        [10, 20, 30, 40],
    "width":        [0.06, 0.08, 0.09],
    "tolerance":    [0.0, 0.005, 0.01, 0.02],
    "distance":     [0.05, 0.1, 0.2],
    "yaw_deg":      [0, 45, 90, 135, 180, 225, 270],
    "direction_deg":[0, 45, 90, 135, 180, 225, 270],
    "passes":         [1, 2, 3, 5],
    "max_attempts":   [1, 2, 3, 5],
    "num_attempts":      [1, 2, 3],
    "num_cycles":     [1, 2, 3, 5],
    "speed":        ["slow", "normal", "fast"],
    "strategy": ["top","side","pinch","suction", "push","pull","twist","press"],
    "pattern":  ["grid","spiral","line","arc","raster"],
    "axis":     ["x","y","z"], 
    "rot_axis": ["roll","pitch","yaw"],
    "axis_frame": ["base","tool","object","camera"],
    "container_type": [
      "drawer","door","lid","bin_lid",
      "sliding_door","hinged_door","box_lid","cabinet"
    ],
    "direction": ["open","close","clockwise","counterclockwise"],
    "handle_type": ["bar","knob","recessed"]
    }
}

  
INSTRUCTION → BT MAPPING (apply strictly)
- Map adjectives/adverbs to discrete bins from port_value_spaces:
  • “gently / low force” → smallest allowed force
  • “quickly / fast” → smallest allowed timeout_ms
  • “precisely / tight” → smallest allowed tolerance
- “retry K times” → <RetryUntilSuccessful num_attempts="K"> (K from instruction).
- “time limit T” → <Timeout timeout_ms="T"> with T snapped to the nearest allowed bin.
- Objects/poses named in the instruction become symbolic targets consistent with the frames (e.g., "card","pregrasp_pose","bin_A").
- If the instruction implies parameters missing from the library, set those to null and justify in metadata.evaluation_notes.

CONTACT SHEET MODE (K=8 frames)
- Interpret frames strictly in ascending index 0→7, row‑major (left→right, top→bottom).
- Do not reorder, merge, or skip frames.
- When referencing frames in metadata, use: "frame_source": "contact_sheet", "frame_order": ["frame_0","frame_1","frame_2","frame_3","frame_4","frame_5","frame_6","frame_7", "frame_8"].

LOCAL ANNOTATIONS RULES (embedded inside metadata JSON)
- Provide "local_annotations": exactly 9 entries (frame_0..frame_8), each with:
  • "frame": one of "frame_0".."frame_8";
  • "phase": one of ["perceive","approach","verify","grasp","transfer","place","retreat"]; phases must be non‑decreasing from frame_0→frame_7 (repeats allowed; no regressions);
  • "active_leaf": {"id": <leaf ID present in the BT>, "attrs": {<ONLY whitelisted ports with values snapped to port_value_spaces>}};
  • "active_path_ids": array of structural IDs from root to that leaf; if unknown, use [].
- The "local_annotations" MUST be coherent with the generated BT and the node library.

MANDATORY OUTPUT FORMAT (EXACT order)
(1) ```xml
<BehaviorTree ID="MainTree">
  ...tree...
</BehaviorTree>
```
(2) ```json
{
  "dataset_id": "{DATASET_ID}",
  "episode_id": "{EPISODE_ID}",
  "task_summary": "...",
  "task_long_description": {
    "overview": "<60–120 words: purpose, scene, objects, roles, constraints>",
    "preconditions": ["<items>"],
    "stepwise_plan": ["<steps>"],
    "success_criteria": ["<criteria>"],
    "failure_and_recovery": ["<likely failures and recovery mechanisms>"],
    "termination": "<termination condition>"
  },
  "frame_ranking": {
    "order": ["frame_3","frame_5","frame_2","frame_6","frame_1","frame_4","frame_7","frame_0", "frame_8"],
    "scores": {
      "frame_0": 0.12, "frame_1": 0.34, "frame_2": 0.56, "frame_3": 0.92,
      "frame_4": 0.28, "frame_5": 0.80, "frame_6": 0.49, "frame_7": 0.18, "frame_8": 0.05
    },
    "rationale_per_frame": {
      "frame_3": {
        "now_evidence": "first stable contact and alignment cue visible",
        "predicts_next": "push actuation expected; confirms goal direction",
        "uncertainty_reduction": "high"
      }
    }
  },
  "task_instruction": "{TASK_INSTRUCTION_VERBATIM}",
  "instruction_to_ports": {
    "force": <number or null>,
    "timeout_ms": <number or null>,
    "tolerance": <number or null>,
    "retry_attempts": <number or null>
  },
  "frame_source": "contact_sheet",
  "frame_order": ["frame_0","frame_1","frame_2","frame_3","frame_4","frame_5","frame_6","frame_7", "frame_8"],
  "objects": ["..."],
  "objects_from_instruction": ["..."],
  "blackboard_keys": ["..."],
  "node_specs": [
    {"id":"...","type":"Action|Condition","ports":{...},"description":"..."}
  ],
  "tree_stats": {"nodes_total": 0, "actions": 0, "conditions": 0, "depth": 0},
  "failure_modes": ["..."],
  "recovery_strategy": ["..."],
  "assumptions": ["note conflicts or uncertainties, including instruction↔frames"],
  "evaluation_notes": {
    "expected_success_criteria": ["..."],
    "test_scenarios": ["happy path","object_missing","grasp_fail","perception_noise"]
  },
  "timing": {"model_reported_tokens": null, "client_elapsed_ms": null},

  "local_annotations": [
    {
      "frame": "frame_0",
      "phase": "...",
      "active_leaf": {"id":"...","attrs":{}},
      "active_path_ids": []
    }
    /* + 8 entries for frame_1..frame_8 */
  ]
}
```


### EXAMPLES (guidance only — DO NOT COPY VERBATIM)

**EXAMPLE A — Simple navigation (two waypoints)**  
Dataset description: “The behavior tree represents a mobile robot tasked to visit two locations: (7,1) and (4,8). The available actions are: `MoveTo`.”
```xml
  <BehaviorTree ID="MainTree">
    <Sequence name="root_sequence">
      <MoveTo x="7" y="1"/>
      <MoveTo x="4" y="8"/>
    </Sequence>
  </BehaviorTree>

Guidance (do not copy): Minimal sequential plan with a single root composite. No decorators or subtrees; use only allowed actions and binned parameters.

EXAMPLE B — Navigation with periodic replanning + recovery
Dataset description: “The behavior tree orchestrates a sequence of actions for a robot. First, it checks the battery level, then opens the gripper, approaches an object, and finally closes the gripper. This sequence likely represents a task for a robotic arm or similar system to perform a series of actions in a specific order, such as picking up an object. The behavior tree ensures that each action is executed sequentially, with the next action only occurring if the previous one is successful.”
```xml
<BehaviorTree ID="MainTree">
  <Sequence name="root_sequence">
    <CheckBattery name="check_battery"/>
    <OpenGripper name="open_gripper"/>
    <ApproachObject name="actino_test"/>
    <CloseGripper name="close_gripper"/>
  </Sequence>
</BehaviorTree>
```

SELF‑CHECK BEFORE PRINTING (do this silently)
- Exactly one <BehaviorTree ID="MainTree"> with a single composite child.
- Decorators each have one child; Parallel includes both thresholds.
- All leaves use ONLY whitelisted ports; numeric ports use ONLY allowed values from port_value_spaces.
- Instruction copied verbatim; chosen bins reflected in "instruction_to_ports".
- "frame_source" and "frame_order" set as specified.
- "local_annotations": 9 entries, filenames valid, phases non‑decreasing, leaves exist in the BT, attrs/legal values.
- If any violation is detected, fix internally and then print ONLY the two blocks.
