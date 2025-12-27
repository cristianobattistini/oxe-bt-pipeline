ROLE: BT Repair (BehaviorTree.CPP v3)
TASK: Fix the Naive XML into the final robust + modular XML (SubTree allowed). Image is Frame 0 only.

INPUTS:
- Instruction: {instruction}
- Naive XML:
{naive_xml}

OUTPUT: XML only (no markdown).

XML RULES:
- Allowed tags: root, BehaviorTree, Sequence, Fallback, RetryUntilSuccessful, Timeout, SubTree, Action.
- Forbidden: any other tags. No `<input .../>`.
- Preserve existing XML comments; do NOT add new ones.
- Leaves: `<Action ID="..." obj="..."/>` (RELEASE has NO params; others have exactly `obj`).
- `root@main_tree_to_execute` matches the first `<BehaviorTree ID="...">`.
- Each `<BehaviorTree>` has exactly one root child (wrap in `<Sequence>` if needed).
- Allowed Action IDs (PAL v1): GRASP, PLACE_ON_TOP, PLACE_INSIDE, OPEN, CLOSE, NAVIGATE_TO, RELEASE, TOGGLE_ON, TOGGLE_OFF, SOAK_UNDER, SOAK_INSIDE, WIPE, CUT, PLACE_NEAR_HEATING_ELEMENT, PUSH, POUR, FOLD, UNFOLD, SCREW, HANG.

REPAIR STEPS:
1) Fix XML well-formedness and missing/extra `obj`.
2) Add robustness: wrap GRASP/OPEN/PLACE_* in RetryUntilSuccessful (2-3).
3) Use Fallback only if branch B changes actions/order (real recovery). If both branches attempt the same action, collapse to a single RetryUntilSuccessful with more attempts.
4) Modularize: use `<SubTree ... target="..."/>` calls in MainTree and define referenced subtrees using `obj="{target}"`.
