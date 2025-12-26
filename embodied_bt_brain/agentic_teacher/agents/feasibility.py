import json
from typing import Any, Dict, Optional, Tuple

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        return json.loads(snippet)
    raise ValueError("could not parse JSON from response")


class FeasibilityAgent:
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

    def check(self, instruction: str, contact_sheet_path: str) -> Tuple[str, Dict[str, Any]]:
        if not self.enabled:
            return "{}", {"agent": "Feasibility", "feasible": True, "status": "disabled"}

        if self.llm_client is None:
            raise ValueError("FeasibilityAgent requires an LLM client.")

        prompt = render_prompt("feasibility", instruction=instruction)
        response = self.llm_client.complete_with_fallback(
            prompt,
            image_path=contact_sheet_path,
            model=self.model,
            temperature=0.0,
            max_tokens=600,
        )

        data = _extract_json_object(response)
        feasible = bool(data.get("feasible", False))
        log = {
            "agent": "Feasibility",
            "status": "ok",
            "feasible": feasible,
            "reason": data.get("reason"),
            "required_primitives": data.get("required_primitives"),
            "missing_capabilities": data.get("missing_capabilities"),
            "used_llm": True,
        }
        return json.dumps(data, ensure_ascii=False, indent=2), log
