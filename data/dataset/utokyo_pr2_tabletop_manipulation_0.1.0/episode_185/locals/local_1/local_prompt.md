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
    <OpenGripper width="0.08" timeout_ms="800"/>
    <Fallback>
      <DetectObject target="grape" timeout_ms="800"/>
      <ScanForTarget target="grape" pattern="spiral" max_attempts="3" timeout_ms="1200"/>
    </Fallback>
    <IsObjectVisible target="grape"/>
    <MoveAbove target="grape" offset_z="0.03" timeout_ms="1200"/>
    <SetTCPYaw yaw_deg="0"/>
    <AtOrientation yaw_deg="0"/>
    <ApproachAndAlign target="grape" tolerance="0.005" timeout_ms="1200"/>
    <ComputeGraspPose target="grape" strategy="pinch" result_key="grasp_grape"/>
    <RetryUntilSuccessful num_attempts="3">
      <Pick grasp_key="grasp_grape" timeout_ms="1200"/>
    </RetryUntilSuccessful>
    <CloseGripper force="10" timeout_ms="800"/>
    <IsGraspStable/>
    <ObjectInGripper target="grape"/>
    <Retreat distance="0.1" timeout_ms="1200"/>
    <Wait timeout_ms="500"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A PR2 arm with a parallel gripper performs a single-grape pick from a plate on a tabletop. The robot first perceives the target grape, approaches from above, aligns its wrist, and computes a pinch-style grasp suitable for an individual grape on the plate. After grasp planning, it executes the pick with retries, closes the gripper with low force, verifies grasp stability, lifts, and retreats slightly to clear the plate. The visual sequence shows approach near the plate rim, contact, and a lifted grape visible in later frames.",
  "preconditions": [
    "Robot initialized and reachable workspace around the plate",
    "Gripper empty and able to open to 0.08 m",
    "Camera provides view of the plate and grapes",
    "Table is stable; no human interference",
    "Target grape present on the plate"
  ],
  "stepwise_plan": [
    "Open gripper to prepare for grasp",
    "Detect grape; if not visible, perform spiral scan",
    "Move above the detected grape at a safe offset",
    "Set yaw and verify orientation",
    "Approach and align with tight tolerance",
    "Compute pinch grasp for the grape",
    "Execute pick with up to 3 retries",
    "Close gripper with low force and verify grasp stability",
    "Confirm object in gripper, then retreat upward to clear the plate",
    "Wait briefly to stabilize"
  ],
  "success_criteria": [
    "Exactly one grape grasped and lifted clear of the plate",
    "Object remains secured after retreat with stable grasp",
    "No collisions with plate, table, or environment",
    "All actions complete within specified timeouts"
  ],
  "failure_and_recovery": [
    "Perception failure: perform spiral scan and re-detect",
    "Misalignment: re-approach and realign before grasp",
    "Failed grasp or dropped object: retry pick up to 3 times",
    "Timeouts: abort current leaf and fallback to re-perceive"
  ],
  "termination": "Terminate after object is confirmed in gripper and retreat plus brief wait complete, or upon unrecoverable failure."
}

- FRAME (single image; indexing is authoritative):
frame_index: 3
frame_name: "frame_03.jpg"
frame_ranking_hint: 0.92

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_3",
  "phase": "verify",
  "active_leaf": {
    "id": "AtOrientation",
    "attrs": {
      "yaw_deg": 0
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
  "frame_index": 3,
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
