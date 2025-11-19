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
      <IsObjectVisible target="t_block"/>
      <ScanForTarget target="t_block" pattern="spiral" max_attempts="3" timeout_ms="800"/>
    </Fallback>
    <Fallback>
      <IsObjectVisible target="goal"/>
      <ScanForTarget target="goal" pattern="spiral" max_attempts="3" timeout_ms="800"/>
    </Fallback>
    <MoveAbove target="t_block" offset_z="0.03" timeout_ms="800"/>
    <ApproachAndAlign target="t_block" tolerance="0.005" timeout_ms="800"/>
    <LowerUntilContact speed="slow" max_depth="0.02" force_threshold="10" timeout_ms="800"/>
    <Push target="t_block" distance="0.1" direction_deg="90" timeout_ms="800"/>
    <Push target="t_block" distance="0.1" direction_deg="0" timeout_ms="800"/>
    <Retreat distance="0.1" timeout_ms="800"/>
    <IsAt target="block_at_goal"/>
  </Sequence>
</BehaviorTree>

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{
  "overview": "A fixed-base manipulator with a circular tool must push a T-shaped block so that it overlaps a marked goal region on the table, as depicted by the contact-sheet frames where the arm makes contact and sweeps the piece along planar directions [attached_image:1][web:8]. The real-world Push-T task is commonly executed with policies issuing commands at 10 Hz, which matches the stated sensing and control frequencies for this episode [attached_image:1][web:8]. The environment includes the T block, the drawn goal outline, and a clean planar workspace enabling point-contact pushes [attached_image:1][web:8]. The behavior emphasizes alignment before contact, short straight pushes, and a final retraction to clear occlusions and signal task completion [attached_image:1][web:8].",
  "preconditions": [
    "T block and goal outline are both detectable in the workspace view before approaching [attached_image:1][web:8]",
    "End-effector is collision-free above the table and ready to descend for contact [attached_image:1][web:8]",
    "Controller runs at 10 Hz so push segments and perception update consistently [attached_image:1][web:8]"
  ],
  "stepwise_plan": [
    "Perceive the T block and the goal region; if not immediately visible, perform a short spiral scan [attached_image:1][web:8]",
    "Move above the block, align to the intended push edge, and descend slowly until contact is detected [attached_image:1][web:8]",
    "Execute one or two straight pushes to translate the block toward and into the outline while maintaining alignment [attached_image:1][web:8]",
    "Verify approximate placement, then retract to a safe height/offset to end the episode cleanly [attached_image:1][web:8]"
  ],
  "success_criteria": [
    "The T block lies within the goal outline with acceptable overlap comparable to Push-T IoU-style thresholds used in literature [attached_image:1][web:8]",
    "The end-effector retreats clear of the object and goal region after placement [attached_image:1][web:8]"
  ],
  "failure_and_recovery": [
    "If the block is not detected, perform a bounded spiral scan before reattempting perception [attached_image:1][web:8]",
    "If contact is not reached within the descent limit, retreat slightly, realign, and retry approach [attached_image:1][web:8]",
    "If the push overshoots or under-shoots, execute an orthogonal corrective push followed by re-verification [attached_image:1][web:8]"
  ],
  "termination": "Terminate when the block is inside the goal region and the tool has retracted to a safe distance, or when perception/approach repeatedly fails causing the sequence to return failure [attached_image:1][web:8]"
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
      "target": "t_block",
      "tolerance": 0.005,
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
