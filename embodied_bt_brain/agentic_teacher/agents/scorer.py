import json
from typing import Any, Dict, List, Optional, Tuple

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


class ScorerAgent:
    def __init__(
        self,
        *,
        llm_client: Optional[AzureLLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.llm_client = llm_client
        self.model = model

    def evaluate(self, bt_xml: str, audit_log: List[Dict[str, Any]]) -> Tuple[str, Any, Dict[str, Any]]:
        if self.llm_client is None:
            raise ValueError("ScorerAgent requires an LLM client.")

        prompt = render_prompt("scorer", bt_xml=bt_xml)
        response = self.llm_client.complete_with_fallback(prompt, model=self.model)
        try:
            data = _extract_json(response)
        except json.JSONDecodeError as exc:
            raise ValueError(f"ScorerAgent returned invalid JSON: {exc}") from exc

        verdict = data.get("verdict")
        score = data.get("total", data.get("score"))
        log = {
            "agent": "Scorer",
            "status": "ok",
            "verdict": verdict,
            "score": score,
            "scores": data.get("scores"),
            "comments": data.get("comments"),
            "used_llm": True,
        }
        return verdict, score, log
