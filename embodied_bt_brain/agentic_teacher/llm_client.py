import base64
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI


try:
    from embodied_bt_brain import keys  # type: ignore
except Exception:  # pragma: no cover - fallback for local runs
    import keys  # type: ignore


@dataclass
class AzureConfig:
    api_key: str
    azure_endpoint: str
    api_version: str
    default_model: Optional[str]


def load_azure_config() -> AzureConfig:
    return AzureConfig(
        api_key=keys.AZURE_OPENAI_KEY,
        azure_endpoint=keys.AZURE_OPENAI_ENDPOINT,
        api_version=keys.AZURE_OPENAI_API_VERSION,
        default_model="gpt-4o",
    )


class AzureLLMClient:
    def __init__(self, *, model: Optional[str] = None) -> None:
        cfg = load_azure_config()
        self.default_model = model or cfg.default_model
        if not self.default_model:
            raise ValueError("Azure OpenAI model/deployment name is required.")
        self.client = AzureOpenAI(
            api_key=cfg.api_key,
            azure_endpoint=cfg.azure_endpoint,
            api_version=cfg.api_version,
        )

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def complete(
        self,
        prompt: str,
        *,
        image_path: Optional[str] = None,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1600,
    ) -> str:
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})

        if image_path:
            img_b64 = self._encode_image(image_path)
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                },
            ]
        else:
            content = prompt

        messages.append({"role": "user", "content": content})

        response = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
