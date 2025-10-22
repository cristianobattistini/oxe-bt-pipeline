Instruction:
You are an assistant that converts a short task description into a BehaviorTree.CPP tree.
- Infer the node order and numeric parameters by grounding in the provided media (video or image).
- The tree must be valid for the BehaviorTree.CPP library (v3+).
- Use only the actions and attributes listed under “Actions”.
- Do not invent objects or states that are not visually supported by the media. Use only what is visible or clearly implied in the media.

Output Requirements:
Output only a single XML: one <BehaviorTree>…</BehaviorTree>.  
Use only the exact node IDs and attributes from the action list.

Input:
Task:
A stationary manipulator must pick up the slender green glass bottle from a cluttered tabletop and hold it steadily for a few seconds. The scene shows multiple colorful containers, with the arm approaching from above and the bottle located right-of-center. The behavior emphasizes reliable perception, precise alignment, a side grasp around the bottle’s neck or body, and a brief hold after lifting to verify stability.

Actions:
<ACTIONS_LIST>

Now output the XML behavior tree only.




python vlm_ft/train/inference.py \
  --adapter_dir "$ADAP_DIR" \
  --video "/home/battistini/exp/private_datasets/oxe_vlm_jsonl/val/videos/asu_table_top_converted_externally_to_rlds_0.1.0/episode_099/contact_video.mp4" \
  --prompt "$(cat <<'PROMPT'
Instruction:
You convert a short task description into a BehaviorTree.CPP tree by grounding your decisions in the PROVIDED MEDIA (video frames).
**PRIORITY OF EVIDENCE: MEDIA > TEXT.**  
If the task text conflicts with the media, IGNORE THE TEXT and follow the media to produce a minimal BehaviorTree for the observed task.

Output Requirements:
- Output only a single valid BehaviorTree.CPP XML and nothing else.
- Use only the nodes/ports in “Actions”.
- Targets must be visually supported by the media; do not invent objects or states.

Task: hold green glass bottle

Actions:
[DetectObject(target, timeout_ms),
 IsObjectVisible(target),
 ScanForTarget(target, pattern, max_attempts, timeout_ms),
 OpenGripper(width, timeout_ms),
 MoveAbove(target, offset_z, timeout_ms),
 ApproachAndAlign(target, tolerance, timeout_ms),
 ComputeGraspPose(target, strategy, result_key),
 PoseAvailable(key),
 GraspAtPose(pose_key, strategy, timeout_ms),
 CloseGripper(force, timeout_ms),
 RaiseHeld(target, distance, timeout_ms),
 HoldObject(target, duration_ms)]

Grounding rules:
- Prefer the media evidence over the text; if the video shows e.g. putting bread down, produce that tree.
- Numeric parameters must be realistic based on the video.

Now output the XML behavior tree only.
PROMPT
)"



python vlm_ft/train/inference.py \
  --adapter_dir "$ADAP_DIR" \
  --video "/home/battistini/exp/private_datasets/oxe_vlm_jsonl/val/videos/asu_table_top_converted_externally_to_rlds_0.1.0/episode_099/contact_video.mp4" \
  --prompt "$(cat <<'PROMPT'
Instruction:
describe what the robot is doing
PROMPT
)"


Instruction:
You are an assistant that converts a short task description into a BehaviorTree.CPP tree.
- Infer the node order and numeric parameters by grounding in the provided media (video or image).
- The tree must be valid for the BehaviorTree.CPP library (v3+).
- Use only the actions and attributes listed under “Actions”.
- Do not invent objects or states that are not visually supported by the media. Use only what is visible or clearly implied in the media.

Output Requirements:
Output only a single XML: one <BehaviorTree>…</BehaviorTree>.  
Use only the exact node IDs and attributes from the action list.

Input:
Task: hold green glass bottle

Actions:[DetectObject(target, timeout_ms),IsObjectVisible(target),ScanForTarget(target, pattern, max_attempts, timeout_ms),OpenGripper(width, timeout_ms),MoveAbove(target, offset_z, timeout_ms),ApproachAndAlign(target, tolerance, timeout_ms),ComputeGraspPose(target, strategy, result_key),PoseAvailable(key),GraspAtPose(pose_key, strategy, timeout_ms),CloseGripper(force, timeout_ms),RaiseHeld(target, distance, timeout_ms),HoldObject(target, duration_ms)]



Now output the XML behavior tree only.





------------------------------------------------------------------------------------------------

--prompt "$(cat <<'PROMPT'
Instruction:
You convert a short task description into a BehaviorTree.CPP tree by grounding your decisions in the PROVIDED MEDIA (video frames).
**PRIORITY OF EVIDENCE: MEDIA > TEXT.**  
If the task text conflicts with the media, IGNORE THE TEXT and follow the media to produce a minimal BehaviorTree for the observed task.

Output Requirements:
- Output only a single valid BehaviorTree.CPP XML and nothing else.
- Use only the nodes/ports in “Actions”.
- Targets must be visually supported by the media; do not invent objects or states.

Task (may be noisy): hold green glass bottle

Actions:
[DetectObject(target, timeout_ms),
 IsObjectVisible(target),
 ScanForTarget(target, pattern, max_attempts, timeout_ms),
 OpenGripper(width, timeout_ms),
 MoveAbove(target, offset_z, timeout_ms),
 ApproachAndAlign(target, tolerance, timeout_ms),
 ComputeGraspPose(target, strategy, result_key),
 PoseAvailable(key),
 GraspAtPose(pose_key, strategy, timeout_ms),
 CloseGripper(force, timeout_ms),
 RaiseHeld(target, distance, timeout_ms),
 HoldObject(target, duration_ms)]

Grounding rules:
- Prefer the media evidence over the text; if the video shows e.g. putting bread down, produce that tree.
- Numeric parameters must be realistic for tabletop manipulation.

Now output the XML behavior tree only.
PROMPT
)"
