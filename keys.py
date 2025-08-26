from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Literal, Optional
from pathlib import Path

# Carica .env dalla root progetto (se presente)
try:
    from dotenv import load_dotenv, find_dotenv  # pip install python-dotenv
    root = Path(__file__).resolve().parents[0]  # cartella del file keys.py
    # prova .env in root repo (un livello sopra) e, se non c'è, qualunque .env trovato
    cand1 = root.parent / ".env"
    if cand1.exists():
        load_dotenv(dotenv_path=cand1, override=False)
    else:
        load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

Provider = Literal["openai", "azure"]

def _get_env(*names: str) -> Optional[str]:
    """Ritorna il primo env var definito tra quelli passati (per compat con nomi legacy)."""
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return None

@dataclass(frozen=True)
class OpenAIConfig:
    provider: Provider
    azure_api_key: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_api_version: Optional[str] = None
    azure_chat_deployment: Optional[str] = None

    @staticmethod
    def from_env() -> "OpenAIConfig":
        provider = (os.getenv("OPENAI_PROVIDER") or "azure").lower()

        cfg = OpenAIConfig(
            provider=provider,  # type: ignore
            azure_api_key=_get_env("AZURE_OPENAI_API_KEY", "AZURE_API_KEY", "azure_openai_key", "azure_key"),
            azure_endpoint=_get_env("AZURE_OPENAI_ENDPOINT", "AZURE_ENDPOINT", "azure_openai_endpoint", "azure_endpoint"),
            azure_api_version=_get_env("AZURE_OPENAI_API_VERSION", "azure_openai_api_version"),
            azure_chat_deployment=_get_env("AZURE_OPENAI_CHAT_DEPLOYMENT", "azure_openai_deployment"),
        )
        cfg._validate()
        return cfg

    def _validate(self) -> None:
        if self.provider != "azure":
            raise RuntimeError("Imposta OPENAI_PROVIDER=azure (chiave OpenAI public non presente).")
        missing = [k for k,v in {
            "AZURE_OPENAI_API_KEY": self.azure_api_key,
            "AZURE_OPENAI_ENDPOINT": self.azure_endpoint,
            "AZURE_OPENAI_API_VERSION": self.azure_api_version,
            "AZURE_OPENAI_CHAT_DEPLOYMENT": self.azure_chat_deployment,
        }.items() if not v]
        if missing:
            raise RuntimeError(f"Variabili mancanti per Azure OpenAI: {', '.join(missing)}")

def get_openai_client():
    from openai import AzureOpenAI
    cfg = OpenAIConfig.from_env()
    endpoint = cfg.azure_endpoint if cfg.azure_endpoint.endswith("/") else (cfg.azure_endpoint + "/")
    return AzureOpenAI(
        api_key=cfg.azure_api_key,
        api_version=cfg.azure_api_version,
        azure_endpoint=endpoint,
    )

def default_model() -> str:
    return OpenAIConfig.from_env().azure_chat_deployment  # deployment name
