from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


class RecoveryPlannerAgent:
    """
    Inserts/normalizes meaningful recovery structure:
      - Branch A: bounded retry of the same action
      - Branch B: recovery that changes conditions (re-NAVIGATE / re-GRASP / re-OPEN)

    This agent is intentionally prompt-driven to avoid brittle deterministic rewriting.
    """

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

    def process_with_context(
        self,
        bt_xml: str,
        *,
        instruction: str,
        scene_analysis: str,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        if not self.enabled:
            return bt_xml, [{"agent": "RecoveryPlanner", "status": "disabled", "used_llm": False}]

        if self.llm_client is None:
            raise ValueError("RecoveryPlannerAgent requires an LLM client.")

        prompt = render_prompt(
            "recovery_planner",
            instruction=instruction,
            scene_analysis=scene_analysis or "",
            bt_xml=bt_xml,
        )
        response = self.llm_client.complete_with_fallback(
            prompt,
            model=self.model,
            temperature=0.2,
            max_tokens=2200,
        )
        updated_xml = extract_xml(response)
        if not updated_xml:
            raise ValueError("RecoveryPlannerAgent returned no XML.")
        try:
            ET.fromstring(updated_xml)
        except ET.ParseError as exc:
            raise ValueError(f"RecoveryPlannerAgent returned invalid XML: {exc}") from exc

        audit_log = [
            {
                "agent": "RecoveryPlanner",
                "status": "ok",
                "used_llm": True,
            }
        ]
        return updated_xml, audit_log

