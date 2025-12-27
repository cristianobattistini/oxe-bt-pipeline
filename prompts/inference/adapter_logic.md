ROLE: BT Planner (BehaviorTree.CPP v3)
TASK: Generate the final BT XML from Frame 0 + Semantic State.

INPUTS:
- Instruction: {instruction}
- Image: Frame 0 only
- Semantic State (YAML):
{semantic_state}
- Valid Actions (PAL subset for this sample): {actions}

OUTPUT: XML only (no markdown).

XML RULES:
- Allowed tags: root, BehaviorTree, Sequence, Fallback, RetryUntilSuccessful, Timeout, SubTree, Action.
- Forbidden tags: Condition, SetBlackboard, Parallel, and any other tags. No `<input .../>`.
- Leaves: `<Action ID="NAME" obj="..."/>` (RELEASE has NO obj).
- SubTrees:
  - Calls: `<SubTree ID="T_..." target="object"/>`
  - Defs consume: `obj="{target}"`

PLANNING RULES:
- Order constraints: NAVIGATE_TO before GRASP/OPEN/WIPE/CUT; GRASP before PLACE_* or RELEASE; OPEN before PLACE_INSIDE when needed.
- Robustness: wrap critical actions (GRASP/OPEN/PLACE_*) in RetryUntilSuccessful (2-3 attempts).
- Use Fallback only if branch B changes actions/order (real recovery), never “same action again”.
