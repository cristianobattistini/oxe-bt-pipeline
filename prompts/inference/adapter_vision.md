TASK: From Frame 0 only, output `semantic_state` YAML for planning.

INPUT:
{instruction}

OUTPUT: YAML only (no markdown). Keep values short; use empty lists if unknown. Use PAL v1 names in `primary_primitives`.

YAML schema (must match exactly):
semantic_state:
  target:
    name: "<string>"
    initial_state: "<string>"
    position: "<string>"
    attributes: ["<attr1>", "<attr2>"]
  environment:
    surface_or_container: "<string>"
    obstacles: ["<obj1>", "<obj2>"]
    constraints: ["<constraint1>", "<constraint2>"]
  risks:
    possible_failures: ["<risk1>", "<risk2>"]
    recovery_hints: ["<hint1>", "<hint2>"]
  affordances:
    primary_primitives: ["GRASP", "PLACE_ON_TOP"]
    preconditions: ["<precond1>", "<precond2>"]
    robustness_need: "low" | "medium" | "high"
