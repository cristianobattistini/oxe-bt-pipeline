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
      <DetectObject target="bread" timeout_ms="1200"/>
      <Sequence>
        <ScanForTarget target="bread" pattern="raster" max_attempts="3" timeout_ms="1500"/>
        <DetectObject target="bread" timeout_ms="1200"/>
      </Sequence>
    </Fallback>
    <DetectObject target="plate" timeout_ms="1200"/>
    <SetBlackboard key="plate_center" value="from_detection"/>
    <OpenGripper width="0.09" timeout_ms="500"/>
    <MoveAbove target="bread" offset_z="0.03" timeout_ms="1200"/>
    <ApproachAndAlign target="bread" tolerance="0.01" timeout_ms="1200"/>
    <ComputeGraspPose target="bread" strategy="pinch" result_key="bread_grasp"/>
    <LowerUntilContact speed="slow" max_depth="0.02" force_threshold="10" timeout_ms="800"/>
    <Pick grasp_key="bread_grasp" timeout_ms="1200"/>
    <ObjectInGripper target="bread"/>
    <Retreat distance="0.1" timeout_ms="800"/>
    <MoveAbove target="plate" offset_z="0.05" timeout_ms="1200"/>
    <PlaceAt pose_key="plate_center" yaw_deg="0" press_force="10" timeout_ms="1200"/>
    <OpenGripper width="0.08" timeout_ms="500"/>
    <Retreat distance="0.2" timeout_ms="1200"/>
    <Wait timeout_ms="500"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A PR2 end-effector operates on a tabletop with a green mat. A white plate and a piece of bread/pastry are visible. The goal is to pick the bread and ultimately situate it on the plate, consistent with the visual sequence. The robot first perceives the bread, aligns for a pinch grasp, establishes contact, closes the gripper, verifies the grasp, lifts away from the table, moves above the plate, and performs a gentle placement before retreating to a safe pose.",
  "preconditions": [
    "Bread and plate are within reachable workspace",
    "Camera provides sufficient visibility of targets",
    "Gripper functional and initially unobstructed",
    "Table surface is approximately planar"
  ],
  "stepwise_plan": [
    "Perceive bread; fallback to scanning if first detection fails",
    "Detect plate and cache a placement pose key",
    "Open gripper and approach above bread",
    "Align precisely and compute pinch grasp",
    "Lower until contact then execute pick",
    "Verify object in gripper and lift/retreat",
    "Move above plate and place bread at plate_center",
    "Open gripper and retreat to safe distance"
  ],
  "success_criteria": [
    "Bread stably grasped during transfer",
    "Bread ends up centered on the plate",
    "Gripper released and robot safely retreated"
  ],
  "failure_and_recovery": [
    "Perception miss: use ScanForTarget then retry DetectObject",
    "Grasp slip: re-align and recompute grasp pose",
    "Placement misalignment: re-approach plate and reattempt PlaceAt",
    "Contact not detected: increase max_depth or re-scan"
  ],
  "termination": "Terminate once bread is placed on plate and the arm has retreated after a short wait."
}

- FRAME (single image; indexing is authoritative):
frame_index: 4
frame_name: "frame_04.jpg"
frame_ranking_hint: 0.9

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_4",
  "phase": "grasp",
  "active_leaf": {
    "id": "Pick",
    "attrs": {
      "grasp_key": "bread_grasp",
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
