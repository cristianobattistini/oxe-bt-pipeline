from dataclasses import dataclass
from typing import Dict, Any
from base64 import b64encode
from .config import MODEL, PRICES
from .caching import cache_tag_for_block
import os

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

@dataclass
class LiveResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw: Any

class LiveLLM:
    def __init__(self):
        if OpenAI is None:
            raise RuntimeError("openai sdk non disponibile")
        self.client = OpenAI()

    def complete(self, prompt_text: str, image_bytes: bytes | None, cached_block: str | None) -> LiveResult:
        content = []
        if prompt_text:
            content.append({"type": "text", "text": prompt_text})
        if image_bytes is not None:
            b64 = b64encode(image_bytes).decode("ascii")
            data_uri = f"data:image/jpeg;base64,{b64}"
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": data_uri
                    # facoltativo: "detail": "auto" | "high" | "low"
                }
            })

        system_txt = "You are GPT-5 Thinking. Follow the instructions precisely."
        # Inseriamo un hint per il caching: il provider può ignorarlo, ma se supportato riduce costo
        if cached_block and MODEL.use_provider_cache:
            tag = cache_tag_for_block(cached_block)
            system_txt += f"\n[CACHED_BLOCK_TAG:{tag}]"

        resp = self.client.chat.completions.create(
            model=MODEL.name,
            messages=[
                {"role": "system", "content": system_txt},
                {"role": "user", "content": content},
            ],
        )
        
        ch = resp.choices[0]
        text = ch.message.content or ""
        in_t = getattr(resp.usage, "prompt_tokens", 0)
        out_t = getattr(resp.usage, "completion_tokens", 0)
        # Stima costo lato client; il provider è la fonte di verità
        cost = (in_t/1e6)*PRICES.per_m_input + (out_t/1e6)*PRICES.per_m_output
        return LiveResult(text=text, input_tokens=in_t, output_tokens=out_t, cost_usd=round(cost,6), raw=resp)

