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
    <Action ID="ScanForTarget" target="fridge_handle" pattern="arc" max_attempts="3" timeout_ms="1500"/>
    <Condition ID="IsObjectVisible" target="fridge_handle"/>
    <Action ID="MoveTo" target="fridge_front" timeout_ms="1500"/>
    <Action ID="ApproachAndAlign" target="fridge_handle" tolerance="0.01" timeout_ms="1500"/>
    <Action ID="OpenGripper" width="0.09" timeout_ms="800"/>
    <Action ID="ComputeGraspPose" target="fridge_handle" strategy="pull" result_key="fridge_handle_grasp"/>
    <Action ID="Pick" grasp_key="fridge_handle_grasp" timeout_ms="1500"/>
    <Action ID="OpenContainer" target="fridge_door" container_type="hinged_door" timeout_ms="1500"/>
    <Action ID="OpenGripper" width="0.09" timeout_ms="800"/>
    <Action ID="Retreat" distance="0.2" timeout_ms="1200"/>
    <Condition ID="ContainerOpen" target="fridge_door"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A PR2 robot opens a refrigerator. The scene shows a white fridge beside a drawer unit. The robot must locate the fridge handle, approach with alignment, grasp it, and pull the hinged door open until the interior is visible. After opening, it releases the handle and backs off to a safe distance. Constraints include precise approach near furniture, reliable perception of the handle, and controlled pulling to swing the door without collision.",
  "preconditions": [
    "Robot base positioned near fridge front",
    "Fridge handle present and reachable",
    "Gripper functional and empty",
    "Workspace free of obstacles along door swing"
  ],
  "stepwise_plan": [
    "Scan for the handle on the fridge door",
    "Verify handle visibility",
    "Move to pregrasp in front of fridge",
    "Approach and align to the handle",
    "Open gripper to desired width",
    "Compute grasp pose for pulling",
    "Execute pick to latch to the handle",
    "Open the container (hinged door) by pulling",
    "Release handle and retreat",
    "Verify door is open"
  ],
  "success_criteria": [
    "Door angle sufficiently open so interior shelves are visible",
    "ContainerOpen(fridge_door) condition true",
    "Robot safely clear from door swing"
  ],
  "failure_and_recovery": [
    "If handle not detected, rescan and slightly reposition",
    "If alignment fails, repeat approach with tighter tolerance",
    "If grasp slips, reopen gripper and recompute grasp pose",
    "If door resists, retry OpenContainer within allowed timeouts"
  ],
  "termination": "Terminate when ContainerOpen on the fridge door returns success after retreat."
}

- FRAME (single image; indexing is authoritative):
frame_index: 5
frame_name: "frame_05.jpg"
frame_ranking_hint: 0.93

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_5",
  "phase": "grasp",
  "active_leaf": {
    "id": "Pick",
    "attrs": {
      "grasp_key": "fridge_handle_grasp",
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
