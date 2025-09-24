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
    <OpenGripper width="0.09" timeout_ms="800"/>
    <DetectObject target="white_plate" timeout_ms="1200"/>
    <DetectObject target="red_plate" timeout_ms="1200"/>
    <ComputeGraspPose target="white_plate" strategy="side" result_key="white_plate_grasp"/>
    <MoveAbove target="white_plate" offset_z="0.05" timeout_ms="1500"/>
    <ApproachAndAlign target="white_plate" tolerance="0.005" timeout_ms="1500"/>
    <CloseGripper force="20" timeout_ms="800"/>
    <ObjectInGripper target="white_plate"/>
    <IsGraspStable/>
    <Retreat distance="0.1" timeout_ms="800"/>
    <MoveAbove target="red_plate" offset_z="0.06" timeout_ms="1500"/>
    <LowerUntilContact speed="slow" max_depth="0.05" force_threshold="10" timeout_ms="1200"/>
    <PlaceAt pose_key="red_plate_top" yaw_deg="0" press_force="10" timeout_ms="1200"/>
    <OpenGripper width="0.09" timeout_ms="800"/>
    <Retreat distance="0.1" timeout_ms="800"/>
    <Wait timeout_ms="400"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A robotic arm must pick a white plate and place it on a nearby red plate. The scene shows a table workspace with a white plate near a larger red plate. The robot should begin with perception, approach the white plate, align for a rim grasp, close the gripper, verify the grasp, lift and transfer toward the red plate, descend until contact, place, release, and retreat. Movements should be controlled and precise to avoid sliding the plates.",
  "preconditions": [
    "Workspace is clear around the plates",
    "Robot gripper is operational and initially open",
    "Camera view includes both white and red plates",
    "Kinematic reachability of both locations"
  ],
  "stepwise_plan": [
    "Open gripper and detect white and red plates.",
    "Compute side grasp on the white plate; move above and align.",
    "Close gripper and verify stable grasp.",
    "Retreat and move above the red plate.",
    "Lower until contact and place at the target pose.",
    "Open gripper to release and retreat."
  ],
  "success_criteria": [
    "White plate is securely grasped without slipping",
    "White plate ends up resting on the red plate surface",
    "No collisions with the environment",
    "Robot safely retreats to a neutral height"
  ],
  "failure_and_recovery": [
    "If detection fails: re-detect or scan the area.",
    "If grasp is unstable: reopen, re-align, and attempt a new grasp.",
    "If contact not detected on placement: adjust height and retry descent."
  ],
  "termination": "Terminate after releasing the plate on the red plate and retreating for at least 0.1 m."
}

- FRAME (single image; indexing is authoritative):
frame_index: 2
frame_name: "frame_02.jpg"
frame_ranking_hint: 0.56

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{
  "frame": "frame_2",
  "phase": "verify",
  "active_leaf": {
    "id": "ApproachAndAlign",
    "attrs": {
      "target": "white_plate",
      "tolerance": 0.005,
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
