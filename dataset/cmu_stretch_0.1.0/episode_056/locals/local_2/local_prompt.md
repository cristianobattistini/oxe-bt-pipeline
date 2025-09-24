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
      <ScanForTarget target="green_garbage_bin" pattern="raster" max_attempts="3" timeout_ms="1200"/>
    </RetryUntilSuccessful>
    <DetectObject target="green_garbage_bin" timeout_ms="1200"/>
    <MoveAbove target="green_bin_lid" offset_z="0.05" timeout_ms="1500"/>
    <SetTCPYaw yaw_deg="90"/>
    <ApproachAndAlign target="green_bin_lid_edge" tolerance="0.005" timeout_ms="1200"/>
    <OpenGripper width="0.09" timeout_ms="400"/>
    <ComputeGraspPose target="green_bin_lid_handle" strategy="pull" result_key="lid_grasp"/>
    <Pick grasp_key="lid_grasp" timeout_ms="1200"/>
    <OpenContainer target="green_garbage_bin" container_type="bin_lid" timeout_ms="1500"/>
    <Retreat distance="0.1" timeout_ms="800"/>
    <ContainerOpen target="green_garbage_bin"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "In a lab scene with a green garbage bin beneath a table, a mobile manipulator must lift open the bin’s hinged green lid. The robot first localizes the bin, approaches above the lid, aligns to the lid edge/handle, and prepares the gripper. It computes a pulling grasp on the lid handle, grasps, and lifts to open using an OpenContainer primitive tailored for bin lids. After opening, it retreats a short distance to avoid collisions and checks that the container is open. Motion and timeouts are conservative due to tight space near the table.",
  "preconditions": [
    "Green garbage bin and lid are present and visible",
    "Hinged lid has graspable edge or handle",
    "Robot arm and gripper are operational",
    "Workspace free of unexpected obstructions"
  ],
  "stepwise_plan": [
    "Scan and detect the green garbage bin.",
    "Move above the lid and set tool yaw to align with hinge/edge.",
    "Approach and align precisely to the lid edge/handle.",
    "Pre-open the gripper and compute a pulling grasp on the lid handle.",
    "Pick using the computed grasp.",
    "Execute OpenContainer for bin lid to lift the lid.",
    "Retreat slightly and verify the bin is open."
  ],
  "success_criteria": [
    "Lid rotates upward to an open state",
    "No collisions with table or environment",
    "Robot maintains a stable grasp during lift",
    "Final ContainerOpen condition succeeds"
  ],
  "failure_and_recovery": [
    "If perception fails, rescan up to three times.",
    "If alignment is off, re-approach with tighter tolerance.",
    "If grasp slips, reopen gripper, recompute grasp, and retry pick.",
    "If lid jams, retreat and attempt a new approach angle."
  ],
  "termination": "Tree terminates after ContainerOpen succeeds or after action timeouts/failures propagate to the root."
}

- FRAME (single image; indexing is authoritative):
frame_index: 7
frame_name: "frame_07.jpg"
frame_ranking_hint: 0.78

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_7",
  "phase": "transfer",
  "active_leaf": {
    "id": "OpenContainer",
    "attrs": {
      "target": "green_garbage_bin",
      "container_type": "bin_lid",
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
  "frame_index": 7,
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
