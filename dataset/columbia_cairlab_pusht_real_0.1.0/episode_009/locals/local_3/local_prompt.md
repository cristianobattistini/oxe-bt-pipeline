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
    <RetryUntilSuccessful num_attempts="3">
      <Action ID="DetectObject" target="t_block" timeout_ms="1200"/>
    </RetryUntilSuccessful>
    <RetryUntilSuccessful num_attempts="3">
      <Action ID="DetectObject" target="goal_region" timeout_ms="1200"/>
    </RetryUntilSuccessful>
    <Action ID="MoveAbove" target="t_block" offset_z="0.03" timeout_ms="1500"/>
    <Action ID="ApproachAndAlign" target="t_block" tolerance="0.005" timeout_ms="1500"/>
    <Action ID="SetTCPYaw" yaw_deg="0"/>
    <Repeat num_cycles="3">
      <Action ID="Push" target="t_block" distance="0.1" direction_deg="0" timeout_ms="1200"/>
    </Repeat>
    <Condition ID="IsAt" target="goal_region"/>
    <Action ID="Retreat" distance="0.1" timeout_ms="800"/>
    <Action ID="Wait" timeout_ms="400"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A table-top robot with a cylindrical end-effector must push a T-shaped block across a planar workspace into a marked target region. The sequence emphasizes reliable perception, careful approach to establish tangential contact, and repeated short pushes along a straight line. Visual frames show a red T-block and a drawn blue mark on the table used as the target cue. The controller operates at 10 Hz; timeouts are binned. No grasping is required—only planar pushing with yaw set to align the tool’s face to the intended motion.",
  "preconditions": [
    "Workspace is clear around the T-block",
    "Camera provides views of block and goal mark",
    "End-effector is free and above the table",
    "Block is movable on the surface"
  ],
  "stepwise_plan": [
    "Detect the T-block",
    "Detect/locate the goal region",
    "Move above the block and align for pushing",
    "Set yaw to align with push direction",
    "Execute repeated short pushes toward the goal",
    "Verify the block reached the goal vicinity",
    "Retreat to a safe height/pose"
  ],
  "success_criteria": [
    "T-block is inside or clearly touching the goal region boundary",
    "No collision with fixtures",
    "Robot ends in a safe, non-contact pose"
  ],
  "failure_and_recovery": [
    "If detection fails, retry perception up to three times",
    "If pushing stalls, repeat short pushes; re-approach if misaligned",
    "If verification fails, re-perceive and continue pushing"
  ],
  "termination": "Terminate after verification succeeds and the robot retreats from contact."
}

- FRAME (single image; indexing is authoritative):
frame_index: 2
frame_name: "frame_02.jpg"
frame_ranking_hint: 0.56

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_2",
  "phase": "approach",
  "active_leaf": {
    "id": "MoveAbove",
    "attrs": {
      "target": "t_block",
      "offset_z": 0.03,
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
  "frame_index": 2,
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
