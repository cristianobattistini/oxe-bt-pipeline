import re
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


_PATTERNS = [
    (
        "place_inside",
        re.compile(
            r"(?:put|place|insert) (?:the )?(?P<object>.+?) (?:in|into|inside) (?:the )?(?P<dest>.+)"
        ),
    ),
    (
        "place_on_top",
        re.compile(
            r"(?:put|place|hang) (?:the )?(?P<object>.+?) (?:on|onto|on top of) (?:the )?(?P<dest>.+)"
        ),
    ),
    (
        "stack",
        re.compile(r"(?:stack) (?:the )?(?P<object>.+)"),
    ),
    (
        "pour",
        re.compile(
            r"(?:pour) (?:the )?(?P<object>.+?) (?:in|into) (?:the )?(?P<dest>.+)"
        ),
    ),
    (
        "soak_under",
        re.compile(
            r"(?:soak|wash|rinse) (?:the )?(?P<object>.+?) under (?:the )?(?P<dest>.+)"
        ),
    ),
    (
        "soak_inside",
        re.compile(
            r"(?:soak|wash|rinse) (?:the )?(?P<object>.+?) (?:in|inside) (?:the )?(?P<dest>.+)"
        ),
    ),
    ("open", re.compile(r"(?:open) (?:the )?(?P<object>.+)")),
    ("close", re.compile(r"(?:close|shut) (?:the )?(?P<object>.+)")),
    ("toggle_on", re.compile(r"(?:toggle on|turn on|switch on|press) (?:the )?(?P<object>.+)")),
    ("toggle_off", re.compile(r"(?:toggle off|turn off|switch off) (?:the )?(?P<object>.+)")),
    ("wipe", re.compile(r"(?:wipe|clean) (?:the )?(?P<object>.+)")),
    ("cut", re.compile(r"(?:cut|slice) (?:the )?(?P<object>.+)")),
    ("navigate", re.compile(r"(?:avoid obstacle and reach|reach|go to|navigate to) (?:the )?(?P<object>.+)")),
    ("grasp", re.compile(r"(?:pick up|pick|grasp|lift) (?:the )?(?P<object>.+)")),
]


def _normalize_entity(text: str) -> str:
    cleaned = text.strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _extract_plan(instruction: str) -> Dict[str, str]:
    lowered = instruction.lower().strip()
    for label, pattern in _PATTERNS:
        match = pattern.search(lowered)
        if match:
            data = {"intent": label}
            if "object" in match.groupdict() and match.group("object"):
                data["object"] = _normalize_entity(match.group("object"))
            if "dest" in match.groupdict() and match.group("dest"):
                data["dest"] = _normalize_entity(match.group("dest"))
            return data
    return {"intent": "navigate", "object": "target"}


def _build_actions(plan: Dict[str, str]) -> List[Dict[str, Dict[str, str]]]:
    intent = plan.get("intent", "navigate")
    obj = plan.get("object", "target")
    dest = plan.get("dest", "destination")

    actions: List[Dict[str, Dict[str, str]]] = []
    if intent in {"place_inside", "place_on_top"}:
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "GRASP", "attrs": {"obj": obj}})
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": dest}})
        place_id = "PLACE_INSIDE" if intent == "place_inside" else "PLACE_ON_TOP"
        actions.append({"ID": place_id, "attrs": {"obj": dest}})
        actions.append({"ID": "RELEASE", "attrs": {}})
        return actions

    if intent == "stack":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "GRASP", "attrs": {"obj": obj}})
        actions.append({"ID": "PLACE_ON_TOP", "attrs": {"obj": obj}})
        actions.append({"ID": "RELEASE", "attrs": {}})
        return actions

    if intent == "pour":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "GRASP", "attrs": {"obj": obj}})
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": dest}})
        actions.append({"ID": "PLACE_INSIDE", "attrs": {"obj": dest}})
        actions.append({"ID": "RELEASE", "attrs": {}})
        return actions

    if intent == "open":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "OPEN", "attrs": {"obj": obj}})
        return actions

    if intent == "close":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "CLOSE", "attrs": {"obj": obj}})
        return actions

    if intent == "toggle_on":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "TOGGLE_ON", "attrs": {"obj": obj}})
        return actions

    if intent == "toggle_off":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "TOGGLE_OFF", "attrs": {"obj": obj}})
        return actions

    if intent == "wipe":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "WIPE", "attrs": {"obj": obj}})
        return actions

    if intent == "cut":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "CUT", "attrs": {"obj": obj}})
        return actions

    if intent == "soak_under":
        nav_target = dest or obj
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": nav_target}})
        actions.append({"ID": "SOAK_UNDER", "attrs": {"obj": obj}})
        return actions

    if intent == "soak_inside":
        nav_target = dest or obj
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": nav_target}})
        actions.append({"ID": "SOAK_INSIDE", "attrs": {"obj": obj}})
        return actions

    if intent == "grasp":
        actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
        actions.append({"ID": "GRASP", "attrs": {"obj": obj}})
        return actions

    actions.append({"ID": "NAVIGATE_TO", "attrs": {"obj": obj}})
    return actions


def _build_xml(actions: List[Dict[str, Dict[str, str]]]) -> str:
    root = ET.Element("root", {"main_tree_to_execute": "MainTree"})
    main_tree = ET.SubElement(root, "BehaviorTree", {"ID": "MainTree"})
    sequence = ET.SubElement(main_tree, "Sequence")
    for action in actions:
        attrs = {"ID": action["ID"]}
        attrs.update(action.get("attrs", {}))
        ET.SubElement(sequence, "Action", attrs)
    try:
        ET.indent(root, space="  ")
    except AttributeError:
        pass
    return ET.tostring(root, encoding="unicode")


class ArchitectAgent:
    def __init__(
        self,
        llm_client: Optional[AzureLLMClient] = None,
        *,
        model: Optional[str] = None,
    ) -> None:
        self.llm_client = llm_client
        self.model = model

    def draft(self, instruction: str, contact_sheet_path: str) -> Tuple[str, List[Dict[str, str]]]:
        if self.llm_client is None:
            raise ValueError("ArchitectAgent requires an LLM client.")

        prompt = render_prompt("architect", instruction=instruction)

        response = self.llm_client.complete(
            prompt,
            image_path=contact_sheet_path,
            model=self.model,
        )
        bt_xml = extract_xml(response)
        if not bt_xml:
            raise ValueError("ArchitectAgent returned no XML.")

        try:
            ET.fromstring(bt_xml)
        except ET.ParseError as exc:
            raise ValueError(f"ArchitectAgent returned invalid XML: {exc}") from exc

        audit_log = [
            {
                "agent": "Architect",
                "status": "ok",
                "used_llm": True,
            }
        ]
        return bt_xml, audit_log
