You are an expert in robotics and Behavior Trees (BT).  
Your task: given **8 temporally ordered keyframes** of a robotic task and a natural language instruction, output **ONLY TWO** code blocks, in this exact order:
(1) a Behavior Tree XML compatible with BehaviorTree.CPP v3,  
(2) a JSON metadata object.

INPUTS (provide values here before running):
- TASK INSTRUCTION: "lift open green garbage can lid"
- DATASET_ID: "cmu_stretch_0.1.0"
- EPISODE_ID: "episode_005"
- 8 ordered keyframes attached as images.


FRAME ORDER (authoritative; do not reorder):
[0] frame_00.jpg  (t=0)
[1] frame_01.jpg  (t=1)
[2] frame_02.jpg  (t=2)
[3] frame_03.jpg  (t=3)
[4] frame_04.jpg  (t=4)
[5] frame_05.jpg  (t=5)
[6] frame_06.jpg  (t=6)
[7] frame_07.jpg  (t=7)

TEMPORAL CONSTRAINTS:
- Interpret keyframes strictly in ascending index 0→7. Do not permute or skip.
- Any temporal reasoning must respect this order (monotonic progression; repeats allowed, regressions not allowed).
- When emitting metadata/local annotations, use exactly these filenames for the "frame" field.


STRICT FORMAT RULES:
- Output NOTHING except the two code blocks.
- Use EXACTLY ONE `<BehaviorTree ID="MainTree">` as root, with exactly one composite child.
- Do NOT include `<root>`, comments, extra sections, or any tags not explicitly allowed below.
- Every decorator must have exactly ONE child.
- Use ONLY the node IDs, ports, and values defined in the node library (below). No extra attributes or values.
- If numeric ports have allowed sets, choose ONLY from those sets. No decimals unless listed.
- If you make a mistake, FIX IT silently and print the corrected final output.

ALLOWED TAGS (BehaviorTree.CPP v3):
- `<BehaviorTree>`, `<Sequence>`, `<Fallback>`, `<Parallel success_threshold=".." failure_threshold="..">`
- `<Inverter>`, `<RetryUntilSuccessful num_attempts="..">`, `<Repeat num_cycles="..">`, `<Timeout timeout_ms="..">`
- `<Action ID="...">`, `<Condition ID="...">`

NODE LIBRARY (USE ONLY THESE IDs/ports/values):
{
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
  

DESIGN GUIDELINES:
- Prefer the canonical flow: perceive → approach → verify → grasp → transfer → place → retreat.
- Use Fallback+Retry for MoveTo/IsAt where appropriate.
- Use symbolic targets/poses (e.g., `"card"`, `"pregrasp_pose"`, `"bin_A"`).

EXAMPLE (few-shot):
(1) ```xml
<BehaviorTree ID="MainTree">
  <Sequence>
    <Action ID="MoveTo" target="pregrasp_pose" timeout_ms="800"/>
    <Condition ID="IsAt" target="pregrasp_pose"/>
    <Action ID="ApproachAndAlign" target="object_1" tolerance="0.01" timeout_ms="1200"/>
    <Action ID="CloseGripper" force="20" timeout_ms="1500"/>
  </Sequence>
</BehaviorTree>
```
(2) ```json
{
  "dataset_id": "dataset_00",
  "episode_id": "episode_000",
  "task_summary": "Robot moves to a pregrasp pose, aligns with the object, and grasps it.",
  "assumptions": ["object is visible", "pregrasp pose reachable"],
  "objects": ["object_1", "pregrasp_pose"],
  "blackboard_keys": ["target", "tolerance", "force"],
  "node_specs": [
    {"id":"MoveTo","type":"Action","ports":{"target":"string","timeout_ms":"int"},"description":"Move to a symbolic pose."},
    {"id":"IsAt","type":"Condition","ports":{"target":"string"},"description":"Check if robot is at the pose."},
    {"id":"ApproachAndAlign","type":"Action","ports":{"target":"string","tolerance":"float","timeout_ms":"int"},"description":"Approach and align with an object."},
    {"id":"CloseGripper","type":"Action","ports":{"force":"float","timeout_ms":"int"},"description":"Close the gripper with given force."}
  ],
  "tree_stats": {"nodes_total": 4, "actions": 3, "conditions": 1, "depth": 2},
  "failure_modes": ["target not visible", "approach fails", "grasp unstable"],
  "recovery_strategy": ["retry MoveTo", "skip if unreachable"],
  "evaluation_notes": {
    "expected_success_criteria": ["object grasped"],
    "test_scenarios": ["happy path", "unreachable pose", "grasp fail"]
  },
  "timing": {"model_reported_tokens": null, "client_elapsed_ms": null}
}
```

NOW YOUR TASK:
You are given **8 temporally ordered keyframes** (attached).  
OPTIONAL: a one-line goal may be provided (e.g., “place card in bin_A”).  
Generate the two blocks (XML then JSON), following all constraints above.

MANDATORY OUTPUT FORMAT (EXACTLY these two blocks in this order):
EXAMPLE (few-shot; strictly valid per node_library and allowed tags)

(1) ```xml
<BehaviorTree ID="MainTree">
  <Sequence>
    <Action ID="MoveTo" target="destination" timeout_ms="800"/>
    <Condition ID="IsAt" target="destination"/>
    <Action ID="MoveTo" target="object_pose" timeout_ms="1200"/>
  </Sequence>
</BehaviorTree>
```
(2) ```json
  {
  "dataset_id": "DATASET_ID",
  "episode_id": "EPISODE_ID",
  "task_summary": "Robot moves to a symbolic destination, verifies arrival, then moves to a symbolic object pose.",
  "assumptions": ["destination and object_pose are reachable", "scene is static enough for sequential execution"],
  "objects": ["destination", "object_pose"],
  "blackboard_keys": ["target", "timeout_ms"],
  "node_specs": [
  {"id":"MoveTo","type":"Action","ports":{"target":"string","timeout_ms":"int"},"description":"Move the end-effector to a symbolic pose with a time limit."},
  {"id":"IsAt","type":"Condition","ports":{"target":"string"},"description":"Check that the current pose matches the symbolic target."}
  ],
  "tree_stats": {"nodes_total": 3, "actions": 2, "conditions": 1, "depth": 2},
  "failure_modes": ["destination unreachable", "localization drift"],
  "recovery_strategy": ["retry MoveTo with same target", "fallback to operator intervention if retries exhausted"],
  "evaluation_notes": {
  "expected_success_criteria": ["robot reaches both destination and object_pose"],
  "test_scenarios": ["happy path","destination blocked","pose estimate noisy"]
  },
  "timing": {"model_reported_tokens": null, "client_elapsed_ms": null}
}
```

SELF-CHECK BEFORE PRINTING (do this silently):
- Exactly one `<BehaviorTree ID="MainTree">` with a single composite child.
- Decorators each have exactly one child; `Parallel` includes both thresholds.
- Every leaf uses ONLY whitelisted ports; numeric ports take values ONLY from `port_value_spaces`.
- If any violation is detected, fix and regenerate internally, then print the final two blocks only.
