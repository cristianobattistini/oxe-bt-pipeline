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
      <DetectObject target="cloth" timeout_ms="1200"/>
      <ScanForTarget target="cloth" pattern="raster" max_attempts="3" timeout_ms="1500"/>
    </Fallback>
    <MoveAbove target="cloth" offset_z="0.06" timeout_ms="800"/>
    <SetTCPYaw yaw_deg="90"/>
    <ApproachAndAlign target="cloth_edge_right" tolerance="0.01" timeout_ms="1200"/>
    <LowerUntilContact speed="slow" max_depth="0.02" force_threshold="10" timeout_ms="1200"/>
    <Push target="cloth_edge_right" distance="0.1" direction_deg="180" timeout_ms="1200"/>
    <LowerUntilContact speed="slow" max_depth="0.01" force_threshold="10" timeout_ms="800"/>
    <Retreat distance="0.1" timeout_ms="800"/>
    <Wait timeout_ms="400"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A PR2 arm operates over a wooden table with a pink square cloth centered in view. The goal is to fold the cloth once by using the gripper’s side to push the right edge leftward, creating a neat crease. The robot first perceives the cloth, approaches above it, aligns to the right edge, sets a lateral yaw, makes gentle contact with the surface, executes a leftward push to flip half the cloth, briefly re-presses to set the crease, and finally retracts. No grasping is required; folding is achieved by contact and pushing.",
  "preconditions": [
    "Cloth placed flat on table within reachable workspace",
    "Robot arm homed and gripper unobstructed",
    "Camera view unobstructed; lighting adequate",
    "Table surface has sufficient friction to hold cloth after fold"
  ],
  "stepwise_plan": [
    "Detect cloth; if not visible, scan the area.",
    "Move above the cloth to a safe approach height.",
    "Set tool yaw for lateral edge push and align to the right edge.",
    "Lower until contact with table to establish stable contact.",
    "Push the right edge leftward to create the fold.",
    "Briefly press again to set the crease.",
    "Retreat to a safe height and pause."
  ],
  "success_criteria": [
    "Cloth appears folded once with a visible crease",
    "Final cloth footprint roughly half original width",
    "No excessive cloth drift beyond central area",
    "Arm safely retracted at end"
  ],
  "failure_and_recovery": [
    "Perception failure: fall back to scanning and retry detection",
    "Misalignment: re-approach and realign edge before pushing",
    "Insufficient contact: perform another lower-until-contact step",
    "Cloth shift during push: repeat push with adjusted start pose"
  ],
  "termination": "Terminate after the retreat and brief wait once a single fold is formed and the arm is clear."
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
    "id": "ApproachAndAlign",
    "attrs": {
      "target": "cloth_edge_right",
      "tolerance": 0.01,
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
