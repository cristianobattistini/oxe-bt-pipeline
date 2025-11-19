SYSTEM (role: senior BT engineer)
You generate BehaviorTree.CPP v3 XML subtrees that are locally consistent with a given GLOBAL BT.
Follow STRICT RULES. Print exactly two code blocks: (1) XML subtree, (2) JSON metadata.

INPUTS
- NODE_LIBRARY (authoritative; use only these node IDs, ports, and port_value_spaces):
{
  "version": "btlib_v2.2",

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
    "MoveToXY":          { "ports": { "x": "float", "y": "float", "yaw_deg": "int", "timeout_ms": "int" } },
    "NavigateToNamed":   { "ports": { "location_id": "string", "yaw_deg": "int", "timeout_ms": "int" } },

    "MoveAbove":         { "ports": { "target": "string", "offset_z": "float", "timeout_ms": "int" } },
    "MoveDelta":         { "ports": { "axis": "string", "dist": "float", "timeout_ms": "int" } },

    "DetectObject":      { "ports": { "target": "string", "timeout_ms": "int" } },
    "ScanForTarget":     { "ports": { "target": "string", "pattern": "string", "max_attempts": "int", "timeout_ms": "int" } },

    "ComputeGraspPose":  { "ports": { "target": "string", "strategy": "string", "result_key": "string" } },
    "GraspAtPose":       { "ports": { "pose_key": "string", "strategy": "string", "timeout_ms": "int" } },

    "ApproachAndAlign":  { "ports": { "target": "string", "tolerance": "float", "timeout_ms": "int" } },
    "SetTCPYaw":         { "ports": { "yaw_deg": "int" } },

    "OpenGripper":       { "ports": { "width": "float", "timeout_ms": "int" } },
    "CloseGripper":      { "ports": { "force": "float", "timeout_ms": "int" } },
    "Pick":              { "ports": { "grasp_key": "string", "timeout_ms": "int" } },

    "HoldObject":        { "ports": { "target": "string", "duration_ms": "int" } },

    "PlaceAt":           { "ports": { "pose_key": "string", "yaw_deg": "int", "press_force": "float", "timeout_ms": "int" } },
    "PlaceAtTol":        { "ports": { "pose_key": "string", "yaw_deg": "int", "press_force": "float", "tolerance": "float", "timeout_ms": "int" } },
    "PlaceOnSurface":    { "ports": { "target": "string", "area_id": "string", "yaw_deg": "int", "press_force": "float", "timeout_ms": "int" } },

    "PlaceDown":         { "ports": { "target": "string", "timeout_ms": "int" } },
    "LowerUntilContact": { "ports": { "speed": "string", "max_depth": "float", "force_threshold": "float", "timeout_ms": "int" } },

    "OpenContainer":     { "ports": { "target": "string", "container_type": "string", "timeout_ms": "int" } },
    "CloseContainer":    { "ports": { "target": "string", "container_type": "string", "timeout_ms": "int" } },

    "PressButton":       { "ports": { "target": "string", "button_type": "string", "press_depth": "float", "press_force": "float", "timeout_ms": "int" } },

    "InsertInto":        { "ports": { "target": "string", "slot_id": "string", "axis": "string", "distance": "float", "tolerance": "float", "force_limit": "float", "timeout_ms": "int" } },

    "Push":              { "ports": { "target": "string", "distance": "float", "direction_deg": "int", "timeout_ms": "int" } },
    "PushWithTool":      { "ports": { "target": "string", "distance": "float", "direction_deg": "int", "tool_id": "string", "timeout_ms": "int" } },
    "Pull":              { "ports": { "target": "string", "distance": "float", "direction_deg": "int", "timeout_ms": "int" } },

    "SlideAlongSurface": { "ports": { "target": "string", "area_id": "string", "distance": "float", "direction_deg": "int", "pattern": "string", "timeout_ms": "int" } },

    "RotateHeld":        { "ports": { "target": "string", "rot_axis": "string", "angle_deg": "int", "timeout_ms": "int" } },

    "RaiseHeld":         { "ports": { "target": "string", "distance": "float", "timeout_ms": "int" } },

    "WipeArea":          { "ports": { "area_id": "string", "pattern": "string", "passes": "int", "timeout_ms": "int" } },

    "FollowTrajectory":  { "ports": { "traj_key": "string", "timeout_ms": "int" } },

    "Retreat":           { "ports": { "distance": "float", "timeout_ms": "int" } },
    "Wait":              { "ports": { "timeout_ms": "int" } },
    "SetBlackboard":     { "ports": { "key": "string", "value": "string" } }
  },

  "conditions": {
    "IsAt":              { "ports": { "target": "string" } },
    "IsAtXY":            { "ports": { "x": "float", "y": "float", "tolerance": "float" } },

    "IsObjectVisible":   { "ports": { "target": "string" } },
    "IsGraspStable":     { "ports": {} },
    "ObjectInGripper":   { "ports": { "target": "string" } },

    "ContactDetected":   { "ports": { "force_threshold": "float" } },
    "ContainerOpen":     { "ports": { "target": "string" } },
    "PoseAvailable":     { "ports": { "key": "string" } },
    "AtOrientation":     { "ports": { "yaw_deg": "int" } },

    "ButtonPressed":     { "ports": { "target": "string" } },
    "Inserted":          { "ports": { "target": "string", "slot_id": "string" } }
  },

  "port_value_spaces": {
    "timeout_ms":    [400, 500, 800, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000, 7000, 10000],
    "duration_ms":   [250, 500, 1000, 2000, 3000, 5000, 8000, 10000],

    "force":         [5, 10, 15, 20, 30, 40, 60, 80, 100],
    "press_force":   [5, 10, 15, 20, 30, 40, 60],
    "force_threshold":[2, 5, 10, 15, 20, 30, 40, 60],
    "force_limit":   [5, 10, 20, 30, 40, 60, 80],
    "width":         [0.02, 0.03, 0.04, 0.06, 0.08, 0.09, 0.10, 0.12],
    "tolerance":     [0.0, 0.002, 0.005, 0.01, 0.015, 0.02, 0.03, 0.05],

    "distance":      [0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50],
    "max_depth":     [0.01, 0.02, 0.05, 0.08, 0.10, 0.15],
    "press_depth":   [0.002, 0.005, 0.010, 0.015, 0.020, 0.030],
    "angle_deg":     [5, 10, 15, 30, 45, 60, 75, 90, 120, 135, 150, 165, 180],
    "yaw_deg":       [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 195, 210, 225, 240, 255, 270, 285, 300, 315, 330, 345],
    "direction_deg": [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 195, 210, 225, 240, 255, 270, 285, 300, 315, 330, 345],

    "passes":        [1, 2, 3, 4, 5, 6, 8, 10],
    "max_attempts":  [1, 2, 3, 5, 8, 10],
    "num_attempts":  [1, 2, 3, 5],
    "num_cycles":    [1, 2, 3, 5, 8, 10],

    "speed":         ["very_slow", "slow", "normal", "fast", "very_fast"],
    "strategy":      ["top", "side", "pinch", "suction", "scoop", "tilt", "push", "pull", "twist", "press", "slide", "poke"],
    "pattern":       ["grid", "spiral", "line", "arc", "raster", "circle", "zigzag", "random"],
    "axis":          ["x", "y", "z"],
    "rot_axis":      ["roll", "pitch", "yaw"],
    "axis_frame":    ["base", "tool", "object", "camera", "map", "odom", "world"],

    "container_type": [
      "drawer", "door", "lid", "bin", "bin_lid", "sliding_door", "hinged_door",
      "box", "box_lid", "cabinet", "pot", "pan", "jar", "fridge_door", "microwave_door"
    ],
    "direction":     ["open", "close", "clockwise", "counterclockwise"],
    "handle_type":   ["bar", "knob", "recessed", "lever", "ring", "button", "handleless"],
    "button_type":   ["push_button", "toggle", "rocker", "keypad", "touch"],

    "object_category": [
      "block", "bottle", "cup", "mug", "can", "jar", "lid", "plate", "bowl",
      "pot", "pan", "knife", "vegetable", "fruit", "box", "clamp", "fixture",
      "tool", "drawer_handle", "cabinet_door", "bin", "door", "container"
    ],
    "tool_id":       ["spatula", "stick", "rod", "squeegee", "tongs", "scraper", "hook", "spoon"],
    "area_id":       ["table", "counter", "shelf", "plate", "sink", "stove", "board", "dish_rack", "basket", "tray"],
    "location_id":   ["goal", "waypoint_1", "waypoint_2", "station_A", "station_B", "start", "home", "dock"],
    "fixture_id":    ["grid_clamp", "jig_A", "jig_B", "slot_1", "slot_2"],
    "slot_id":       ["slot_1", "slot_2", "hole_A", "hole_B", "receptacle_A"],
    "pose_key":      ["goal_pose", "place_on_plate", "place_on_shelf", "place_in_bin", "place_on_table"],
    "grasp_key":     ["std_top", "std_side", "pinch_2f", "suction_center", "pinch_wide"],
    "traj_key":      ["traj_approach", "traj_insert", "traj_retreat", "traj_wipe"]
  }
}

- GLOBAL_BT (authoritative structure, do not modify here):
<BehaviorTree ID="MainTree">
  <Sequence>
    <DetectObject target="glass_bottle" timeout_ms="1500"/>
    <Fallback>
      <ObjectInGripper target="glass_bottle"/>
      <Sequence>
        <OpenGripper width="0.09" timeout_ms="1000"/>
        <ComputeGraspPose target="glass_bottle" strategy="side" result_key="grasp_pose"/>
        <GraspAtPose pose_key="grasp_pose" strategy="side" timeout_ms="2000"/>
        <IsGraspStable/>
      </Sequence>
    </Fallback>
    <PlaceDown target="glass_bottle" timeout_ms="1500"/>
    <OpenGripper width="0.10" timeout_ms="800"/>
    <Retreat distance="0.10" timeout_ms="1000"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A 6-DOF robotic arm manipulates tabletop items including a green glass bottle, a blue can, a red block, a gray cup, and orange cups. The goal is to place down the glass bottle at the table surface. The tree first detects the bottle, checks if it is already held, and if not, performs a side-grasp. After confirming a stable grasp, the robot executes a place-down, opens the gripper to release the bottle, and retreats to clear the workspace.",
  "preconditions": [
    "Work surface clear enough to place the bottle",
    "Bottle visible to the camera",
    "Gripper operational and calibrated",
    "No obstacles along approach and retreat paths"
  ],
  "stepwise_plan": [
    "Perceive and localize the glass bottle.",
    "If already held, skip grasp; otherwise open gripper, compute side grasp, execute grasp, and verify stability.",
    "Place the bottle down on the table.",
    "Open gripper to release.",
    "Retreat to a safe distance."
  ],
  "success_criteria": [
    "Bottle ends stably on the table without toppling",
    "Gripper fully releases the bottle",
    "Arm ends in a safe, non-contact pose"
  ],
  "failure_and_recovery": [
    "Detection failure: re-attempt detection from a slightly different pose.",
    "Grasp failure or slip: re-compute grasp and retry.",
    "Placement contact not detected: re-attempt place with slower approach."
  ],
  "termination": "Terminate when the bottle is on the table, released, and the arm has retreated."
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
    "id": "ObjectInGripper",
    "attrs": {
      "target": "glass_bottle"
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
