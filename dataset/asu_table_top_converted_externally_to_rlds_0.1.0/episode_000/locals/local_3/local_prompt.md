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
    <OpenGripper width="0.06" timeout_ms="1000"/>
    <Fallback>
      <DetectObject target="green_bottle" timeout_ms="1500"/>
      <ScanForTarget target="green_bottle" pattern="spiral" max_attempts="3" timeout_ms="3000"/>
    </Fallback>
    <MoveAbove target="green_bottle" offset_z="0.05" timeout_ms="3000"/>
    <ApproachAndAlign target="green_bottle" tolerance="0.01" timeout_ms="3000"/>
    <ComputeGraspPose target="green_bottle" strategy="side" result_key="goal_pose"/>
    <GraspAtPose pose_key="goal_pose" strategy="side" timeout_ms="3000"/>
    <CloseGripper force="30" timeout_ms="1000"/>
    <RaiseHeld target="green_bottle" distance="0.10" timeout_ms="1500"/>
    <ObjectInGripper target="green_bottle"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A UR-style robotic arm operates over a semi-circular tabletop populated with small bottles, cups, and cylinders under static lighting, with the objective to pick the green bottle visible near the table center-left area. [web:3] The behavior emphasizes reliable perception and alignment before executing a side grasp suited to cylindrical bottle geometry. [web:3] Dataset episodes are structured in an RLDS-like format, so perception-first and verification steps align with standardized sequential decision data conventions. [web:6] The plan finishes after lifting to a safe height and verifying that the object remains in the gripper. [web:6]",
  "preconditions": [
    "Workspace is clear of collisions above the target by at least 5 cm to allow a vertical pre-grasp approach. [web:3]",
    "Gripper is open and calibrated with known jaw width prior to perception. [web:6]",
    "Camera viewpoints provide unobstructed sight of the green bottle for detection or a short scan routine. [web:3]",
    "Controller is configured for position control suitable for approach, alignment, and lifting actions. [web:6]"
  ],
  "stepwise_plan": [
    "Open the gripper to a nominal width and detect the green bottle; if immediate detection fails, run a short spiral scan. [web:6]",
    "Move above the detected bottle with a 5 cm vertical offset and align the end effector laterally to the bottle’s axis. [web:3]",
    "Compute a side grasp pose and execute the grasp at the computed pose with a moderate closing force. [web:3]",
    "Lift the bottle by 10 cm to clear the tabletop and check that it remains securely held. [web:6]"
  ],
  "success_criteria": [
    "Bottle is grasped without displacing surrounding objects. [web:3]",
    "Object remains in gripper after a 10 cm lift above the surface. [web:6]",
    "No timeouts or unrecovered perception failures occur during the sequence. [web:6]"
  ],
  "failure_and_recovery": [
    "If DetectObject fails, the Fallback triggers ScanForTarget with a spiral pattern for up to three attempts before aborting. [web:6]",
    "If grasp slips (ObjectInGripper false), the sequence fails and can be re-executed from perception with an adjusted approach. [web:3]",
    "If alignment times out, retreat to above-target and retry alignment once after scan completes. [web:6]"
  ],
  "termination": "Terminate when the bottle is lifted 10 cm and ObjectInGripper confirms possession, or on unrecoverable detection/grasp errors. [web:6]"
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
      "target": "green_bottle",
      "offset_z": 0.05,
      "timeout_ms": 3000
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
