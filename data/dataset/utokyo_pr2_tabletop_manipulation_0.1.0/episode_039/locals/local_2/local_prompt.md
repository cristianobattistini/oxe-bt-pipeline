SYSTEM (role: senior BT engineer)
You generate BehaviorTree.CPP v3 XML subtrees that are locally consistent with a given GLOBAL BT.
Follow STRICT RULES. Print exactly two code blocks: (1) XML subtree, (2) JSON metadata.

INPUTS
- NODE_LIBRARY (authoritative; use only these node IDs, ports, and port_value_spaces):
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
    "num_attempts":   [1, 2, 3],
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

- GLOBAL_BT (authoritative structure, do not modify here):
<BehaviorTree ID="MainTree">
  <Sequence>
    <Fallback>
      <Condition ID="IsObjectVisible" target="grape"/>
      <RetryUntilSuccessful num_attempts="3">
        <Action ID="ScanForTarget" target="grape" pattern="raster" max_attempts="3" timeout_ms="1200"/>
      </RetryUntilSuccessful>
    </Fallback>
    <Action ID="DetectObject" target="grape" timeout_ms="800"/>
    <Action ID="OpenGripper" width="0.06" timeout_ms="500"/>
    <Action ID="MoveAbove" target="grape" offset_z="0.05" timeout_ms="1500"/>
    <Action ID="ComputeGraspPose" target="grape" strategy="pinch" result_key="grasp_grape"/>
    <Action ID="ApproachAndAlign" target="grape" tolerance="0.005" timeout_ms="1500"/>
    <Action ID="LowerUntilContact" speed="slow" max_depth="0.03" force_threshold="5.0" timeout_ms="1200"/>
    <Action ID="CloseGripper" force="10" timeout_ms="800"/>
    <Condition ID="IsGraspStable"/>
    <Fallback>
      <Condition ID="IsObjectVisible" target="plate"/>
      <Action ID="DetectObject" target="plate" timeout_ms="800"/>
    </Fallback>
    <Action ID="MoveAbove" target="plate" offset_z="0.10" timeout_ms="1500"/>
    <Action ID="PlaceAt" pose_key="plate_center" yaw_deg="0" press_force="10.0" timeout_ms="1200"/>
    <Action ID="OpenGripper" width="0.08" timeout_ms="500"/>
    <Action ID="Retreat" distance="0.1" timeout_ms="1200"/>
    <Action ID="Wait" timeout_ms="500"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A PR2-style gripper operates on a tabletop with a grape cluster and a round plate. The robot must localize the grape, approach from above with an open gripper, compute a pinch grasp, and close with minimal force to avoid crushing. After confirming a stable grasp, it navigates above the plate and places the grape onto it, releases, and retreats. Visual alignment and gentle contact are emphasized due to the soft, irregular object. Timeouts and simple retries are used for robust perception.",
  "preconditions": [
    "Workspace is clear and reachable",
    "Camera provides view of table",
    "Plate present on table",
    "Grape is present",
    "Gripper functional and calibrated"
  ],
  "stepwise_plan": [
    "Check or scan for grape visibility",
    "Detect grape precisely",
    "Open gripper",
    "Move above grape at small offset",
    "Compute pinch grasp and align",
    "Lower until contact and close gently",
    "Verify stable grasp",
    "Confirm plate visibility",
    "Move above plate and place",
    "Open gripper to release",
    "Retreat and wait briefly"
  ],
  "success_criteria": [
    "Grape ends resting on the plate",
    "No visible crushing or dropping",
    "Gripper empty at end",
    "Robot safely retreated from workspace"
  ],
  "failure_and_recovery": [
    "If grape not visible: raster scan with retries",
    "If contact not detected: lower again within limits",
    "If grasp unstable: reopen and reattempt compute+grasp",
    "If plate occluded: detect again before place"
  ],
  "termination": "After release on plate and retreat completes without active faults."
}

- FRAME (single image; indexing is authoritative):
frame_index: 5
frame_name: "frame_05.jpg"
frame_ranking_hint: 0.8

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_5",
  "phase": "transfer",
  "active_leaf": {
    "id": "MoveAbove",
    "attrs": {
      "target": "plate",
      "offset_z": 0.1,
      "timeout_ms": 1500
    }
  },
  "active_path_ids": []
}

- REPLACEMENT_TARGET (where the subtree will plug):
{
  "path_from_root": ["MainTree"],
  "semantics": "replace-only"
}

STRICT RULES
1) Output (1) must be BehaviorTree.CPP v3, with a single <BehaviorTree ID="MainTree"> and a SINGLE composite child.
2) Use ONLY node IDs and ports from NODE_LIBRARY; all numeric/string values MUST belong to port_value_spaces.
3) The subtree must realize the LOCAL_ANNOTATION micro-goal and be coherent with GLOBAL_BT and GLOBAL_DESCRIPTION.
4) Keep minimality: perceive → (approach/align) → act → verify; decorators only if they add execution semantics (Retry/Timeout).
5) Do not invent blackboard keys not implied by NODE_LIBRARY or GLOBAL_BT.
6) No comments, no extra tags, no prose inside XML.

REQUIRED OUTPUT

(1) XML subtree
<BehaviorTree ID="MainTree">
    <Sequence>
        <!-- minimal, binned, library-only -->
    </Sequence>
</BehaviorTree>

(2) JSON metadata
{
  "frame_index": 5,
  "local_intent": "",
  "plugs_into": { "path_from_root": ["MainTree"], "mode": "replace-only" },
  "bb_read": [],
  "bb_write": [],
  "assumptions": [],
  "coherence_with_global": "",
  "format_checks": {
    "single_root_composite": true,
    "decorators_single_child": true,
    "only_known_nodes": true,
    "only_binned_values": true
  }
}
