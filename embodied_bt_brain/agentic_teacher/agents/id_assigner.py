from typing import Any, Dict, List, Tuple
from xml.etree import ElementTree as ET


def _base_name(node: ET.Element) -> str:
    if node.tag == "Action":
        primitive_id = node.get("ID") or "action"
        return primitive_id.lower()
    if node.tag == "SubTree":
        return "subtree"
    return node.tag.lower()


def assign_stable_names(bt_xml: str) -> Tuple[str, int]:
    root = ET.fromstring(bt_xml)
    counters: Dict[str, int] = {}
    assigned = 0

    for node in root.iter():
        if node.tag in {"root", "BehaviorTree"}:
            continue
        if node.get("name"):
            continue
        base = _base_name(node)
        idx = counters.get(base, 0)
        counters[base] = idx + 1
        node.set("name", f"{base}_{idx:02d}")
        assigned += 1

    try:
        ET.indent(root, space="  ")
    except AttributeError:
        pass
    return ET.tostring(root, encoding="unicode"), assigned


class IdAssignerAgent:
    """
    Deterministically assigns missing `name="..."` fields to nodes for patchability.
    This is post-processing (not semantic generation).
    """

    def process(self, bt_xml: str) -> Tuple[str, List[Dict[str, Any]]]:
        updated_xml, assigned = assign_stable_names(bt_xml)
        return updated_xml, [
            {
                "agent": "IdAssigner",
                "status": "ok",
                "assigned_names": assigned,
                "used_llm": False,
            }
        ]

