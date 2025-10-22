You are an expert in robotics and Behavior Trees (BT).
Your task: given (A) a brief TASK INSTRUCTION and (B) ONE contact‑sheet image containing K=8 tiles (row‑major, labeled [0]..[7]), output ONLY TWO code blocks, in this exact order:
(1) a BehaviorTree.CPP v3 XML,
(2) a JSON metadata object (which MUST also include the field "local_annotations" with exactly 8 entries, one per tile).

INPUTS (authoritative)
- TASK INSTRUCTION (verbatim, 1–2 lines).
- One contact‑sheet image 'episode.png' arranged as 2×4 tiles, labeled [0]..[7] (left→right, top→bottom).

PRIORITY & GROUNDING
- Ground the design in BOTH the instruction and the visual evidence from tiles [0]..[7].
- If they conflict, prefer the tiles; log the mismatch in metadata.assumptions.

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
      "Parallel":  { "attrs": { "success_threshold": "int", "failure_threshold": "int" } }
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
  
      /* opzionale se hai mobile base:
      "MoveBaseTo":        { "ports": { "target": "string", "timeout_ms": "int" } }
      */
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
      "tolerance":    [0.005, 0.01, 0.02],
      "distance":     [0.05, 0.1, 0.2],
      "yaw_deg":      [0, 90, 180, 270],
      "direction_deg":[0, 90, 180, 270],
      "speed":        ["slow", "normal", "fast"],
      "strategy":     ["top", "side", "pinch", "suction"],
      "pattern":      ["grid", "spiral", "line"],
      "axis":         ["x", "y", "z"],
      "container_type":["drawer", "door", "lid", "bin_lid"]
    }
  }
  
  
INSTRUCTION → BT MAPPING (apply strictly)
- Map adjectives/adverbs to discrete bins from port_value_spaces:
  • “gently / low force” → smallest allowed force
  • “quickly / fast” → smallest allowed timeout_ms
  • “precisely / tight” → smallest allowed tolerance
- “retry K times” → <RetryUntilSuccessful num_attempts="K"> (K from instruction).
- “time limit T” → <Timeout timeout_ms="T"> with T snapped to the nearest allowed bin.
- Objects/poses named in the instruction become symbolic targets consistent with the tiles (e.g., "card","pregrasp_pose","bin_A").
- If the instruction implies parameters missing from the library, set those to null and justify in metadata.evaluation_notes.

CONTACT SHEET MODE (K=8 tiles)
- Interpret tiles strictly in ascending index 0→8, row‑major (left→right, top→bottom).
- Do not reorder, merge, or skip tiles.
- When referencing frames in metadata, use: "frame_source": "contact_sheet", "frame_order": ["tile_0","tile_1","tile_2","tile_3","tile_4","tile_5","tile_6","tile_7"].

LOCAL ANNOTATIONS RULES (embedded inside metadata JSON)
- Provide "local_annotations": exactly 8 entries (tile_0..tile_7), each with:
  • "frame": one of "tile_0".."tile_7";
  • "phase": one of ["perceive","approach","verify","grasp","transfer","place","retreat"]; phases must be non‑decreasing from tile_0→tile_7 (repeats allowed; no regressions);
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
  "task_instruction": "{TASK_INSTRUCTION_VERBATIM}",
  "instruction_to_ports": {
    "force": <number or null>,
    "timeout_ms": <number or null>,
    "tolerance": <number or null>,
    "retry_attempts": <number or null>
  },
  "frame_source": "contact_sheet",
  "frame_order": ["tile_0","tile_1","tile_2","tile_3","tile_4","tile_5","tile_6","tile_7"],
  "objects": ["..."],
  "objects_from_instruction": ["..."],
  "blackboard_keys": ["..."],
  "node_specs": [
    {"id":"...","type":"Action|Condition","ports":{...},"description":"..."}
  ],
  "tree_stats": {"nodes_total": 0, "actions": 0, "conditions": 0, "depth": 0},
  "failure_modes": ["..."],
  "recovery_strategy": ["..."],
  "assumptions": ["note conflicts or uncertainties, including instruction↔tiles"],
  "evaluation_notes": {
    "expected_success_criteria": ["..."],
    "test_scenarios": ["happy path","object_missing","grasp_fail","perception_noise"]
  },
  "timing": {"model_reported_tokens": null, "client_elapsed_ms": null},

  "local_annotations": [
    {
      "frame": "tile_0",
      "phase": "...",
      "active_leaf": {"id":"...","attrs":{}},
      "active_path_ids": []
    }
    /* + 7 entries for tile_1..tile_7 */
  ]
}
```

SELF‑CHECK BEFORE PRINTING (do this silently)
- Exactly one <BehaviorTree ID="MainTree"> with a single composite child.
- Decorators each have one child; Parallel includes both thresholds.
- All leaves use ONLY whitelisted ports; numeric ports use ONLY allowed values from port_value_spaces.
- Instruction copied verbatim; chosen bins reflected in "instruction_to_ports".
- "frame_source" and "frame_order" set as specified.
- "local_annotations": 8 entries, filenames valid, phases non‑decreasing, leaves exist in the BT, attrs/legal values.
- If any violation is detected, fix internally and then print ONLY the two blocks.