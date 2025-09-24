from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

@dataclass
class MockResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

class MockLLM:
    def __init__(self, fixture_path: Path):
        self.fixture_path = fixture_path

    def complete(self, prompt_text: str, image_bytes: bytes | None) -> MockResult:
        # Simula il costo in modo deterministico sulla lunghezza prompt
        txt = self.fixture_path.read_text(encoding="utf-8")
        in_tok = max(1000, len(prompt_text)//4)
        out_tok = max(800, len(txt)//4)
        # Costo fittizio estremamente basso in mock
        return MockResult(text=txt, input_tokens=in_tok, output_tokens=out_tok, cost_usd=0.0)
