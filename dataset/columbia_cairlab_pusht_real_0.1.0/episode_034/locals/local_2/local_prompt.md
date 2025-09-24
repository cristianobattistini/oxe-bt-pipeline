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
      <Condition ID="IsObjectVisible" target="block_T"/>
      <Action ID="ScanForTarget" target="block_T" pattern="raster" max_attempts="3" timeout_ms="800"/>
    </Fallback>
    <Fallback>
      <Condition ID="IsObjectVisible" target="goal_outline"/>
      <Action ID="ScanForTarget" target="goal_outline" pattern="raster" max_attempts="3" timeout_ms="800"/>
    </Fallback>
    <Action ID="MoveAbove" target="block_T" offset_z="0.02" timeout_ms="800"/>
    <Action ID="ApproachAndAlign" target="block_T" tolerance="0.005" timeout_ms="1200"/>
    <Action ID="SetTCPYaw" yaw_deg="135"/>
    <Repeat num_cycles="3">
      <Sequence>
        <Action ID="Push" target="block_T" distance="0.1" direction_deg="135" timeout_ms="1200"/>
        <Action ID="ApproachAndAlign" target="block_T" tolerance="0.005" timeout_ms="1200"/>
      </Sequence>
    </Repeat>
    <Action ID="Retreat" distance="0.1" timeout_ms="800"/>
    <Action ID="Wait" timeout_ms="400"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A UR-type arm with a circular end-effector pushes a T-shaped block across a white tabletop toward a drawn goal outline. The robot first locates both the block and the goal, approaches to a safe height, and aligns its tool to the block’s face. It then performs a series of short, controlled pushes roughly toward the goal, re-aligning between pushes to keep contact stable. After displacement appears sufficient, the robot backs away and pauses. Frequencies are 10 Hz for observation and control; pushes are conservative in distance and time.",
  "preconditions": [
    "Workspace is clear and flat",
    "Block and goal outline present on table",
    "Camera feeding detections of 'block_T' and 'goal_outline'",
    "Robot reachable workspace covers object and target"
  ],
  "stepwise_plan": [
    "Detect the T block and the goal outline; scan if not visible.",
    "Move above the block and align to a pushing face.",
    "Set tool yaw to a diagonal (≈135°) toward the goal.",
    "Repeat: push a short distance, then re-align to maintain heading.",
    "Retreat from the object and briefly wait."
  ],
  "success_criteria": [
    "Block translated toward/into the goal outline",
    "No loss of contact causing undesired rotations",
    "Robot ends safely away from the block"
  ],
  "failure_and_recovery": [
    "Block or goal not detected → raster scan and retry detection",
    "Misalignment or slip during push → re-align and attempt next push",
    "Insufficient displacement → additional push cycles (bounded)"
  ],
  "termination": "After completing the planned push cycles and retreat, or if visibility cannot be recovered after scans."
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
    "id": "ApproachAndAlign",
    "attrs": {
      "target": "block_T",
      "tolerance": 0.005,
      "timeout_ms": 1200
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
