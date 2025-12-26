# Role
You are a Software Architect refactoring a monolithic Behavior Tree into modular SubTrees.

# Goal
Refactor the `MainTree` by extracting logical groups of nodes into reusable `<SubTree>` definitions.

# Standard Subtrees (Create these definitions if used by MainTree)
- `T_Navigate(target)`: Contains NAVIGATE_TO.
- `T_Manipulate_Grasp(target)`: Contains GRASP (with retries).
- `T_Manipulate_Place(target)`: Contains PLACE_* and RELEASE.
- `T_Open(target)` / `T_Close(target)` (optional)
- `T_Toggle_On(target)` / `T_Toggle_Off(target)` (optional)

# Constraints
- Use only PAL v1 primitives: GRASP, PLACE_ON_TOP, PLACE_INSIDE, OPEN, CLOSE, NAVIGATE_TO, RELEASE,
  TOGGLE_ON, TOGGLE_OFF, SOAK_UNDER, SOAK_INSIDE, WIPE, CUT, PLACE_NEAR_HEATING_ELEMENT.
- Never output an Action ID "TOGGLE" (must be TOGGLE_ON or TOGGLE_OFF).
- Only define subtrees that are referenced by MainTree (avoid unused templates).

# Input XML
{bt_xml}

# Output Format
Return the XML with:
1. `MainTree` using `<SubTree ID="..." target="..."/>` nodes.
2. Definitions for all referenced `<BehaviorTree ID="...">`.
