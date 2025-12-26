# Role
You are a Software Architect refactoring a monolithic Behavior Tree into modular SubTrees.

# Goal
Refactor the `MainTree` by extracting logical groups of nodes into reusable `<SubTree>` definitions.

# Standard Subtrees (Create these definitions if used by MainTree)
- `T_Navigate(target)`: Contains NAVIGATE_TO.
- `T_Manipulate_Grasp(target)`: Contains GRASP (optionally with RetryUntilSuccessful).
- `T_Manipulate_Place_OnTop(target)`: Contains PLACE_ON_TOP and RELEASE.
- `T_Manipulate_Place_Inside(target)`: Contains PLACE_INSIDE and RELEASE.
- `T_Open(target)` / `T_Close(target)` (optional)
- `T_Toggle_On(target)` / `T_Toggle_Off(target)` (optional)
- `T_Wipe(target)` / `T_Cut(target)` / `T_Soak_Under(target)` / `T_Soak_Inside(target)` (optional)

# Constraints
- Use only PAL v1 primitives: GRASP, PLACE_ON_TOP, PLACE_INSIDE, OPEN, CLOSE, NAVIGATE_TO, RELEASE,
  TOGGLE_ON, TOGGLE_OFF, SOAK_UNDER, SOAK_INSIDE, WIPE, CUT, PLACE_NEAR_HEATING_ELEMENT.
- Never output an Action ID "TOGGLE" (must be TOGGLE_ON or TOGGLE_OFF).
- Only define subtrees that are referenced by MainTree (avoid unused templates).
- Do NOT use `<input .../>` tags inside `<SubTree>` calls. Pass parameters as attributes like `target="blue_can"`.
- Preserve the intended plan: do not reorder macro-phases or change goals (e.g., do not change PLACE_INSIDE to PLACE_ON_TOP).
- Keep XML valid and executable by BehaviorTree.CPP v3.

# Input XML
{bt_xml}

# Output Format
Return the XML with:
1. `MainTree` using `<SubTree ID="..." target="..."/>` nodes.
2. Definitions for all referenced `<BehaviorTree ID="...">`.

# SubTree Parameter Convention
- In `MainTree`, pass parameters via attributes (e.g., `target="blue_can"`).
- Inside subtree definitions, read parameters via blackboard substitution: `obj="{target}"`.
- Do not introduce additional parameters unless already present in the input.
