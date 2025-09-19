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
    <DetectObject target="cloth" timeout_ms="1200"/>
    <OpenGripper width="0.09" timeout_ms="800"/>
    <MoveAbove target="cloth_edge" offset_z="0.03" timeout_ms="1200"/>
    <ApproachAndAlign target="cloth_edge" tolerance="0.005" timeout_ms="1200"/>
    <LowerUntilContact speed="slow" max_depth="0.02" force_threshold="10" timeout_ms="1200"/>
    <CloseGripper force="10" timeout_ms="800"/>
    <MoveDelta axis="z" dist="0.1" timeout_ms="800"/>
    <Push target="cloth" distance="0.1" direction_deg="180" timeout_ms="1200"/>
    <PlaceAt pose_key="fold_center" yaw_deg="0" press_force="10" timeout_ms="1200"/>
    <OpenGripper width="0.06" timeout_ms="800"/>
    <Retreat distance="0.1" timeout_ms="800"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A single PR2-like arm manipulates a pink cloth on a wooden tabletop. The goal is to fold the cloth by grasping one edge, lifting slightly, and dragging/pushing it over itself to create a clear crease. The sequence emphasizes careful approach, gentle contact, and a short lift followed by an in-plane push to achieve the fold. After forming the fold near the cloth center, the gripper presses to set the crease, releases the cloth, and retreats to a safe height, leaving the folded cloth on the table.",
  "preconditions": [
    "Cloth is visible on the table",
    "Workspace is free of obstacles around the cloth",
    "Gripper operational and empty",
    "Table surface provides sufficient friction for folding by push/drag"
  ],
  "stepwise_plan": [
    "Perceive and localize the cloth and a foldable edge.",
    "Open the gripper and move above the target edge.",
    "Align, descend until contact, and close the gripper on the edge.",
    "Lift slightly and push/drag the edge across the cloth to fold.",
    "Press at the fold center to set the crease.",
    "Open gripper and retreat to a safe pose."
  ],
  "success_criteria": [
    "A visible, stable fold is formed",
    "Cloth remains within workspace bounds",
    "No unintended object displacement",
    "Robot ends at a safe, non-contact pose"
  ],
  "failure_and_recovery": [
    "Cloth not detected: re-perceive or adjust view",
    "Missed grasp: reopen, realign, and retry approach",
    "Slip during push: reduce speed or re-grasp closer to edge",
    "Insufficient fold: repeat push/press from corrected start"
  ],
  "termination": "Terminate when fold is formed and the arm has released the cloth and retreated safely."
}

- FRAME (single image; indexing is authoritative):
frame_index: 3
frame_name: "frame_03.jpg"
frame_ranking_hint: 0.92

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_3",
  "phase": "grasp",
  "active_leaf": {
    "id": "CloseGripper",
    "attrs": {
      "force": 10,
      "timeout_ms": 800
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
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="LocalSubtask">
      <!-- minimal, binned, library-only -->
    </Sequence>
  </BehaviorTree>
</root>

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
