from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


def _copy_action(action: ET.Element) -> ET.Element:
    copied = ET.Element("Action", dict(action.attrib))
    return copied


def _wrap_action(parent: ET.Element, action: ET.Element, attempts: int) -> None:
    obj = action.get("obj")
    primitive_id = action.get("ID")
    if primitive_id in {"NAVIGATE_TO", "RELEASE"}:
        return

    retry = ET.Element("RetryUntilSuccessful", {"num_attempts": str(attempts)})
    fallback = ET.SubElement(retry, "Fallback")
    fallback.append(action)

    if obj:
        recovery = ET.SubElement(fallback, "Sequence")
        ET.SubElement(recovery, "Action", {"ID": "NAVIGATE_TO", "obj": obj})
        recovery.append(_copy_action(action))

    children = list(parent)
    try:
        idx = children.index(action)
    except ValueError:
        return

    parent.remove(action)
    parent.insert(idx, retry)


class RobustnessAgent:
    def __init__(
        self,
        *,
        enabled: bool = True,
        num_attempts: int = 3,
        llm_client: Optional[AzureLLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.enabled = enabled
        self.num_attempts = num_attempts
        self.llm_client = llm_client
        self.model = model

    def process(self, bt_xml: str) -> Tuple[str, List[Dict[str, Any]]]:
        if not self.enabled:
            return bt_xml, [{"agent": "Robustness", "status": "disabled", "issues_found": 0}]

        if self.llm_client is None:
            raise ValueError("RobustnessAgent requires an LLM client.")

        prompt = render_prompt("robustness", bt_xml=bt_xml)
        response = self.llm_client.complete(prompt, model=self.model)
        updated_xml = extract_xml(response)
        if not updated_xml:
            raise ValueError("RobustnessAgent returned no XML.")
        try:
            ET.fromstring(updated_xml)
        except ET.ParseError as exc:
            raise ValueError(f"RobustnessAgent returned invalid XML: {exc}") from exc
        wrapped = 0
        audit_log = [
            {
                "agent": "Robustness",
                "status": "ok",
                "issues_found": 0,
                "wrapped_actions": wrapped,
                "used_llm": True,
            }
        ]
        return updated_xml, audit_log
