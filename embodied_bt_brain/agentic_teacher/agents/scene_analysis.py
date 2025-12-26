from typing import Any, Dict, Optional, Tuple

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


class SceneAnalysisAgent:
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

    def analyze(self, instruction: str, contact_sheet_path: str) -> Tuple[str, Dict[str, Any]]:
        if not self.enabled:
            return "", {"agent": "SceneAnalysis", "status": "disabled", "used_llm": False}

        if self.llm_client is None:
            raise ValueError("SceneAnalysisAgent requires an LLM client.")

        prompt = render_prompt("scene_analysis", instruction=instruction)
        response = self.llm_client.complete_with_fallback(
            prompt,
            image_path=contact_sheet_path,
            model=self.model,
            temperature=0.2,
            max_tokens=900,
        )
        text = (response or "").strip()
        if not text:
            raise ValueError("SceneAnalysisAgent returned empty text.")

        log = {
            "agent": "SceneAnalysis",
            "status": "ok",
            "used_llm": True,
            "chars": len(text),
        }
        return text, log
