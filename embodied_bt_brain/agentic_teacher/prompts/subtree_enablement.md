# Role
You are a Software Architect refactoring a monolithic Behavior Tree into modular SubTrees.

# Goal
Refactor the `MainTree` by extracting logical groups of nodes into reusable `<SubTree>` definitions.

# Standard Subtrees (Create these definitions)
- `T_Navigate(target)`: Contains NAVIGATE_TO.
- `T_Manipulate_Grasp(target)`: Contains GRASP (with retries).
- `T_Manipulate_Place(target)`: Contains PLACE_* and RELEASE.
- `T_Open(target)` / `T_Close(target)`
- `T_Toggle(target)`

# Input XML
{bt_xml}

# Output Format
Return the XML with:
1. `MainTree` using `<SubTree ID="..." target="..."/>` nodes.
2. Definitions for all referenced `<BehaviorTree ID="...">`.