from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt

def _base_name(node: ET.Element) -> str:
    if node.tag == "Action":
        primitive_id = node.get("ID") or "action"
        return primitive_id.lower()
    if node.tag == "SubTree":
        return "subtree"
    return node.tag.lower()


def _assign_names(tree: ET.Element) -> int:
    counters: Dict[str, int] = {}
    assigned = 0

    for node in tree.iter():
        if node.tag == "BehaviorTree":
            continue
        if node.get("name"):
            continue
        base = _base_name(node)
        idx = counters.get(base, 0)
        counters[base] = idx + 1
        node.set("name", f"{base}_{idx:02d}")
        assigned += 1

    return assigned


class IdPatchabilityAgent:
    def __init__(
        self,
        *,
        enabled: bool = True,
        llm_client: Optional[AzureLLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.enabled = enabled
        self.llm_client = llm_client
        self.model = model

    def process(self, bt_xml: str) -> Tuple[str, List[Dict[str, Any]]]:
        if not self.enabled:
            return bt_xml, [
                {"agent": "IdPatchability", "status": "disabled", "issues_found": 0}
            ]

        if self.llm_client is None:
            raise ValueError("IdPatchabilityAgent requires an LLM client.")

        prompt = render_prompt("id_patchability", bt_xml=bt_xml)
        response = self.llm_client.complete(prompt, model=self.model)
        updated_xml = extract_xml(response)
        if not updated_xml:
            raise ValueError("IdPatchabilityAgent returned no XML.")
        try:
            ET.fromstring(updated_xml)
        except ET.ParseError as exc:
            raise ValueError(f"IdPatchabilityAgent returned invalid XML: {exc}") from exc
        audit_log = [
            {
                "agent": "IdPatchability",
                "status": "ok",
                "issues_found": 0,
                "names_assigned": 0,
                "used_llm": True,
            }
        ]
        return updated_xml, audit_log
