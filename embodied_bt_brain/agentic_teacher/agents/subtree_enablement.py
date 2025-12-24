from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt

_RESERVED_ATTRS = {"ID", "name"}


def _find_main_tree(root: ET.Element) -> ET.Element | None:
    for tree in root.findall(".//BehaviorTree"):
        if tree.get("ID") == "MainTree":
            return tree
    trees = root.findall(".//BehaviorTree")
    return trees[0] if trees else None


def _get_container(root: ET.Element) -> ET.Element | None:
    if root.tag == "root":
        return root
    if root.tag == "BehaviorTree":
        return None
    return root


class SubtreeEnablementAgent:
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
                {"agent": "SubtreeEnablement", "status": "disabled", "issues_found": 0}
            ]

        if self.llm_client is None:
            raise ValueError("SubtreeEnablementAgent requires an LLM client.")

        prompt = render_prompt("subtree_enablement", bt_xml=bt_xml)
        response = self.llm_client.complete(prompt, model=self.model)
        updated_xml = extract_xml(response)
        if not updated_xml:
            raise ValueError("SubtreeEnablementAgent returned no XML.")

        try:
            root = ET.fromstring(updated_xml)
        except ET.ParseError as exc:
            raise ValueError(f"SubtreeEnablementAgent returned invalid XML: {exc}") from exc

        audit_log = [
            {
                "agent": "SubtreeEnablement",
                "status": "ok",
                "issues_found": 0,
                "used_llm": True,
            }
        ]
        return updated_xml, audit_log
