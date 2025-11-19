# README — `node_library.json`

## Purpose
`node_library.json` is the **vocabulary** of your Behavior Tree (BT) language. It declares which nodes are allowed, which attributes/ports they accept, and—optionally—discrete value sets for some ports. You use it to:
- constrain model outputs during generation (fewer syntax errors and hallucinations),
- validate generated BTs automatically,
- standardize episodes (same IDs/ports/values), making debugging and metrics easier.

## File structure
Top‑level keys:

- `version`: string label for the library (e.g., `btlib_v1.1`).
- `composites`: map `Name -> { attrs: { name: type } }`.
- `decorators`: map `Name -> { attrs: { name: type } }` (decorators must have exactly **one** child).
- `actions` / `conditions`: map `LeafID -> { ports: { name: type } }`.
- `port_value_spaces` (optional): map `port -> [allowed_values]` to stabilize model choices.

Allowed types: `int`, `float`, `bool`, `string`.  
Blackboard references use `{key}` and are always accepted by the validator (the runtime will resolve them).

### Minimal example (excerpt)
```json
{
  "version": "btlib_v1.1",
  "composites": {
    "Sequence": { "attrs": {} },
    "Parallel": { "attrs": { "success_threshold": "int", "failure_threshold": "int" } }
  },
  "decorators": {
    "Timeout": { "attrs": { "timeout_ms": "int" } }
  },
  "actions": {
    "DetectObject": { "ports": { "target": "string", "timeout_ms": "int" } },
    "CloseGripper": { "ports": { "force": "float", "timeout_ms": "int" } },
    "SetTCPYaw":    { "ports": { "yaw_deg": "int" } }
  },
  "conditions": {
    "IsObjectVisible": { "ports": { "target": "string" } }
  },
  "port_value_spaces": {
    "timeout_ms": [400, 500, 800, 1200, 1500, 2000],
    "force":      [10, 20, 30, 40],
    "yaw_deg":    [0, 90, 180, 270]
  }
}
```
**Why this shape?** Composites/decorators declare their attributes (with types) so the validator can check both structure and values consistently. Leaves use `ports`. Whenever a port appears in `port_value_spaces`, the validator enforces membership unless the value is a blackboard reference (`{...}`).

## Conventions
- Leaf IDs: PascalCase or Snake_Case (`MoveTo`, `Open_Gripper`).
- Port names: short and consistent (`target`, `timeout_ms`, `force`).  
- If you publish a `port_value_spaces` entry for a port, model outputs should pick **only** from that set or use a blackboard reference `{key}`.

## Generation (prompting)
Embed **only the relevant slice** of the library into your prompt and add a hard constraint:

```
Use only the tags/ports/values defined in the following library.
If a port appears in "port_value_spaces", select a value from that set
or provide a blackboard reference in the form {key}.
Do not use tags or attributes that are not in the library.
```

This cuts down syntax drift and normalizes outputs across episodes.

## Post‑generation validation
Run a validator on the produced BT XML using the library. The typical rules are:
- Decorators must have exactly **one** child.
- `Parallel` thresholds are integers and must not exceed the number of children.
- No unknown tags/attributes/ports; all values must respect declared types.
- If `port_value_spaces` is defined for a port, the value must belong to that set (unless it is `{key}`).

### Minimal validator (Python)
```python
import xml.etree.ElementTree as ET

def _is_bb_ref(v: str) -> bool:
    v = str(v).strip()
    return v.startswith("{") and v.endswith("}")

def _parse_typed(v: str, t: str) -> bool:
    if _is_bb_ref(v):        # blackboard refs are always accepted
        return True
    try:
        if t == "int":
            int(v); return True
        if t == "float":
            float(v); return True
        if t == "bool":
            return str(v).lower() in ("true","false","0","1")
        if t == "string":
            return True
    except Exception:
        return False
    return False

def _node_kind(name, lib):
    if name in lib["composites"]: return ("composite", name)
    if name in lib["decorators"]: return ("decorator", name)
    if name in lib["actions"]:    return ("action",    name)
    if name in lib["conditions"]: return ("condition", name)
    return (None, None)  # unknown, or <Action ID="...">

def _canonical_name(elem):
    if elem.tag in ("Action","Condition") and "ID" in elem.attrib:
        return elem.attrib["ID"].strip()
    return elem.tag

def validate_bt(xml_text: str, lib: dict):
    errs = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return [f"Invalid XML: {e}"]

    bt = None
    if root.tag == "BehaviorTree":
        bt = root
    else:
        for c in root.iter():
            if c.tag == "BehaviorTree":
                bt = c; break
    if bt is None:
        return ["Missing <BehaviorTree>"]

    def walk(elem):
        name = _canonical_name(elem)
        kind, canon = _node_kind(name, lib)
        children = list(elem)

        if kind == "composite":
            allowed = lib["composites"][canon]["attrs"]
            for k,v in elem.attrib.items():
                if k in ("ID","BTCPP_format","main_tree_to_execute"):
                    continue
                if k not in allowed:
                    errs.append(f"[{name}] forbidden attribute: {k}")
                elif not _parse_typed(v, allowed[k]):
                    errs.append(f"[{name}] attribute {k} has wrong type: '{v}' not {allowed[k]}")
            if name == "Parallel":
                n = len(children)
                try:
                    st = int(elem.attrib.get("success_threshold","-1"))
                    ft = int(elem.attrib.get("failure_threshold","-1"))
                    if not (0 <= st <= n): errs.append(f"[Parallel] success_threshold {st} out of range 0..{n}")
                    if not (0 <= ft <= n): errs.append(f"[Parallel] failure_threshold {ft} out of range 0..{n}")
                except ValueError:
                    errs.append("[Parallel] thresholds must be integers")
        elif kind == "decorator":
            if len(children) != 1:
                errs.append(f"[{name}] must have exactly 1 child, got {len(children)}")
            allowed = lib["decorators"][canon]["attrs"]
            for k,v in elem.attrib.items():
                if k not in allowed:
                    errs.append(f"[{name}] forbidden attribute: {k}")
                elif not _parse_typed(v, allowed[k]):
                    errs.append(f"[{name}] attribute {k} has wrong type: '{v}' not {allowed[k]}")
        elif kind in ("action","condition"):
            spec = lib["actions"][canon]["ports"] if kind=="action" else lib["conditions"][canon]["ports"]
            for k,v in elem.attrib.items():
                if k == "ID":
                    continue
                if k not in spec:
                    errs.append(f"[{name}] forbidden port: {k}")
                    continue
                t = spec[k]
                if not _parse_typed(v, t):
                    errs.append(f"[{name}] port {k} has wrong type: '{v}' not {t}")
                space = lib.get("port_value_spaces", {}).get(k)
                if space and not _is_bb_ref(v):
                    if t == "int":
                        ok = int(v) in space
                    elif t == "float":
                        ok = float(v) in space
                    else:
                        ok = v in space
                    if not ok:
                        errs.append(f"[{name}] port {k} value '{v}' not in {space}")
        else:
            service_ok = elem.tag in ("root","BehaviorTree","TreeNodesModel")
            if not service_ok:
                errs.append(f"Unknown/unsupported tag: <{elem.tag}>")

        for ch in children:
            walk(ch)

    for child in list(bt):
        walk(child)
    return errs
```
**How it works.** The validator parses the XML, canonicalizes leaf names (accepts both `<MoveTo .../>` and `<Action ID="MoveTo" .../>`), and checks each node against the library: node kind, allowed attributes/ports, types, structural rules for decorators and `Parallel`, and membership in discrete spaces. Blackboard references `{...}` bypass value checks and are left to the runtime.

## Local view integration
When rendering `active_leaf`:
1. Ensure its `id` exists in `actions ∪ conditions`.
2. Check every `k:v` against declared `ports` and, if present, `port_value_spaces`.
3. Flag violations explicitly (“forbidden port”, “value not in space”).

## Practical examples

### Oriented placement (T‑block)
```xml
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <DetectObject target="t_block" timeout_ms="800"/>
      <ApproachAndAlign target="t_block" tolerance="0.01" timeout_ms="1200"/>
      <CloseGripper force="20" timeout_ms="800"/>
      <MoveAbove target="place_T_outline" offset_z="0.10" timeout_ms="1200"/>
      <SetTCPYaw yaw_deg="90"/>
      <LowerUntilContact speed="slow" max_depth="0.05" force_threshold="5.0" timeout_ms="1200"/>
      <OpenGripper width="0.08" timeout_ms="500"/>
      <Retreat distance="0.10" timeout_ms="800"/>
    </Sequence>
  </BehaviorTree>
</root>
```

### Pushing/wiping (cloth)
```xml
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <DetectObject target="cloth" timeout_ms="800"/>
      <Push target="cloth" distance="0.20" direction_deg="0" timeout_ms="1200"/>
      <WipeArea area_id="center" pattern="grid" passes="2" timeout_ms="1500"/>
      <Retreat distance="0.10" timeout_ms="800"/>
    </Sequence>
  </BehaviorTree>
</root>
```

### Container interaction (bin/drawer)
```xml
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <OpenContainer target="bin" container_type="bin_lid" timeout_ms="1200"/>
      <PlaceAt pose_key="{drop_pose}" yaw_deg="0" press_force="0.0" timeout_ms="1200"/>
      <CloseContainer target="bin" container_type="bin_lid" timeout_ms="1200"/>
    </Sequence>
  </BehaviorTree>
</root>
```

## Versioning
Start small and evolve incrementally (`btlib_v1.2`, `v1.3`, …). Keep backward compatibility: do not rename existing ports; add new ports with safe defaults. If new recurring patterns emerge, add a small number of higher‑level leaves without changing the overall grammar.

---

**Summary.** `node_library.json` formalizes your BT language. Put a compact slice into prompts to constrain generation, run the validator to guarantee conformity, and keep the library versioned as your tasks grow. This makes model outputs syntactically correct, comparable across episodes, and easy to debug.
