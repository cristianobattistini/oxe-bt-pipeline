from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt

class SchemaAgent:
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
            return bt_xml, [{"agent": "Schema", "status": "disabled", "issues_found": 0}]

        if self.llm_client is None:
            raise ValueError("SchemaAgent requires an LLM client.")

        prompt = render_prompt("schema", bt_xml=bt_xml)
        response = self.llm_client.complete(prompt, model=self.model)
        updated_xml = extract_xml(response)
        if not updated_xml:
            raise ValueError("SchemaAgent returned no XML.")
        try:
            ET.fromstring(updated_xml)
        except ET.ParseError as exc:
            raise ValueError(f"SchemaAgent returned invalid XML: {exc}") from exc

        audit_log = [
            {
                "agent": "Schema",
                "status": "ok",
                "issues_found": 0,
                "used_llm": True,
            }
        ]
        return updated_xml, audit_log
