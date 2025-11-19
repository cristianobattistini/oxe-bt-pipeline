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
    <MoveTo target="cabinet_area" timeout_ms="1500"/>
    <Fallback>
      <IsObjectVisible target="drawer_handle"/>
      <ScanForTarget target="drawer_handle" pattern="raster" max_attempts="3" timeout_ms="1500"/>
    </Fallback>
    <DetectObject target="drawer_handle" timeout_ms="1200"/>
    <ComputeGraspPose target="drawer_handle" strategy="pull" result_key="grasp_handle"/>
    <OpenGripper width="0.09" timeout_ms="500"/>
    <MoveAbove target="drawer_handle" offset_z="0.05" timeout_ms="1500"/>
    <SetTCPYaw yaw_deg="90"/>
    <ApproachAndAlign target="drawer_handle" tolerance="0.01" timeout_ms="1500"/>
    <CloseGripper force="20" timeout_ms="800"/>
    <OpenContainer target="drawer" container_type="drawer" timeout_ms="1500"/>
    <Retreat distance="0.1" timeout_ms="1200"/>
    <ContainerOpen target="drawer"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "The scene shows a mobile manipulator near a wooden cabinet with metal handles and a countertop holding a tissue box and a red cup. The robot arm approaches the cabinet front, aligns with a horizontal drawer handle, grasps it, and performs a pulling motion to open the drawer. The plan emphasizes reliable perception of the handle, correct end‑effector yaw for a bar handle, and gentle force when closing the gripper. After opening, the arm retreats to avoid collisions and checks that the drawer is indeed open.",
  "preconditions": [
    "Robot has free access to the cabinet front",
    "Drawer handle visible or discoverable via scan",
    "End-effector operational and gripper functional",
    "No obstacles blocking the pull trajectory"
  ],
  "stepwise_plan": [
    "Navigate/position near cabinet and search for the drawer handle",
    "Detect the handle and compute a pull-oriented grasp",
    "Pre-open gripper, approach above the handle, and set yaw alignment",
    "Close gripper on the handle and execute drawer opening",
    "Retreat and verify the drawer state is open"
  ],
  "success_criteria": [
    "Gripper secures the drawer handle without slipping",
    "Drawer translates outward a visible distance",
    "Robot retreats to a safe standoff",
    "Open state is confirmed by a container-open check"
  ],
  "failure_and_recovery": [
    "If handle not detected, perform raster scan and retry detection",
    "If grasp slips, reopen, realign, and regrasp with improved approach",
    "If drawer jams, re-approach with slightly different pose and repeat open action"
  ],
  "termination": "Terminate once ContainerOpen succeeds after retreat or on unrecoverable failure."
}

- FRAME (single image; indexing is authoritative):
frame_index: 4
frame_name: "frame_04.jpg"
frame_ranking_hint: 0.88

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_4",
  "phase": "grasp",
  "active_leaf": {
    "id": "CloseGripper",
    "attrs": {
      "force": 20,
      "timeout_ms": 800
    }
  },
  "active_path_ids": [
    "Sequence",
    "CloseGripper"
  ]
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
  "frame_index": 4,
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
