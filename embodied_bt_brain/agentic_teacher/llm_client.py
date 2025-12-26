import base64
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import logging

from openai import AzureOpenAI, NotFoundError


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
    raw_endpoint = str(keys.AZURE_OPENAI_ENDPOINT)
    default_model: Optional[str] = "gpt-4o"

    # Support both:
    # - base endpoint: https://<resource>.openai.azure.com
    # - fully-qualified deployment URL (legacy / copy-paste):
    #   https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=...
    if "/openai/deployments/" in raw_endpoint:
        parsed = urlparse(raw_endpoint)
        parts = parsed.path.split("/openai/deployments/", 1)
        base_path = parts[0]
        remainder = parts[1] if len(parts) > 1 else ""
        deployment = remainder.split("/", 1)[0] if remainder else ""
        if deployment:
            default_model = deployment
        raw_endpoint = f"{parsed.scheme}://{parsed.netloc}{base_path}"

    return AzureConfig(
        api_key=keys.AZURE_OPENAI_KEY,
        azure_endpoint=raw_endpoint,
        api_version=keys.AZURE_OPENAI_API_VERSION,
        default_model=default_model,
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

    def complete_with_fallback(
        self,
        prompt: str,
        *,
        image_path: Optional[str] = None,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1600,
    ) -> str:
        """
        Same as `complete`, but if the explicit deployment/model is not found,
        retries with the client's default deployment (useful with misconfigured CLI).
        """
        try:
            return self.complete(
                prompt,
                image_path=image_path,
                system=system,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except NotFoundError:
            if model and model != self.default_model:
                logging.warning(
                    "Azure deployment '%s' not found; retrying with default '%s'",
                    model,
                    self.default_model,
                )
                return self.complete(
                    prompt,
                    image_path=image_path,
                    system=system,
                    model=self.default_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise
