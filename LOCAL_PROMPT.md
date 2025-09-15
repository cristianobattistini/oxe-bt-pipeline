You are an expert in robotics and Behavior Trees (BT).

GOAL
Given (A) a BehaviorTree.CPP v3 XML (below), (B) 8 temporally ordered keyframes (attached), and (C) the node library, produce ONLY one JSON code block named "local_annotations" with exactly 8 entries (one per frame). Each entry must contain:
- "frame": exact filename,
- "phase": one of ["perceive","approach","verify","grasp","transfer","place","retreat"],
- "active_leaf": {"id": <leaf ID that EXISTS in the BT>, "attrs": {<ports and values>}},
- "active_path_ids": array of structural IDs from root to that leaf (if unknown, return []).

FRAME ORDER (authoritative; do not reorder)
[0] frames/frame_000.jpg  (t=0)
[1] frames/frame_001.jpg  (t=1)
[2] frames/frame_002.jpg  (t=2)
[3] frames/frame_003.jpg  (t=3)
[4] frames/frame_004.jpg  (t=4)
[5] frames/frame_005.jpg  (t=5)
[6] frames/frame_006.jpg  (t=6)
[7] frames/frame_007.jpg  (t=7)
Use exactly these filenames in the JSON. If your filenames differ, replace the list above with the actual names before generating.

NODE LIBRARY (USE ONLY THESE IDs/ports/values)
[PASTE your node_library.json here; you may omit any "version" field]

BEHAVIOR TREE XML
[PASTE the bt.xml here]

HARD CONSTRAINTS
- Phases must be monotonically non-decreasing from t=0→t=7 (repeats allowed; no regressions).
- "active_leaf.id" MUST be a leaf present in the given BT (Action or Condition).
- "attrs" MUST use ONLY whitelisted port names for that leaf.
- For any port that has a discrete value set in "port_value_spaces", choose ONLY values from that set.
- If a suitable value is unknown from the frame, choose the most conservative bin (e.g., smallest timeout_ms, lowest force).
- If multiple BT leaves share the same ID and you cannot disambiguate, set "active_path_ids": [] (it will be filled later).

MANDATORY OUTPUT (print ONLY this JSON code block; no prose)
```json
{"local_annotations": [
  {
    "frame": "frames/frame_000.jpg",
    "phase": "...",
    "active_leaf": { "id": "...", "attrs": { /* allowed ports only */ } },
    "active_path_ids": []
  },
  /* 7 more entries for frame_001..frame_007 */
]}
```

SELF-CHECK BEFORE PRINTING (do this silently)
- Exactly 8 entries, filenames match the authoritative order above.
- Phases are in-domain and non-decreasing.
- Every "active_leaf.id" exists in the BT; every attr name/value is legal per the node library and its port_value_spaces.
- If any violation is detected, fix internally and then print ONLY the JSON block.
