from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(APP_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    integuru_api_key: str
    integuru_invoke_url: str
    integuru_account_id: str
    demographics_integration_id: str
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    agent_name: str
    stt_model: str
    llm_model: str
    tts_model: str
    port: int
    web_build_dir: Path

    @property
    def is_voice_configured(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)


def load_settings() -> Settings:
    return Settings(
        integuru_api_key=os.getenv("INTEGURU_API_KEY", ""),
        integuru_invoke_url=os.getenv("INTEGURU_INVOKE_URL", "https://api.integuru.ai/integrations/invoke"),
        integuru_account_id=os.getenv("INTEGURU_ACCOUNT_ID", "98c16453-be1f-4c9f-b942-dcdfa8e526f3"),
        demographics_integration_id=os.getenv("DEMOGRAPHICS_INTEGRATION_ID", "65afea2f-a46b-40f9-b831-abdb21b01738"),
        livekit_url=os.getenv("LIVEKIT_URL", ""),
        livekit_api_key=os.getenv("LIVEKIT_API_KEY", ""),
        livekit_api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        agent_name=os.getenv("LIVEKIT_AGENT_NAME", "patient-demographics"),
        stt_model=os.getenv("LIVEKIT_STT_MODEL", "deepgram/nova-3"),
        llm_model=os.getenv("LIVEKIT_LLM_MODEL", "google/gemini-2.5-flash-lite"),
        tts_model=os.getenv("LIVEKIT_TTS_MODEL", "cartesia/sonic-3"),
        port=int(os.getenv("PORT", "5000")),
        web_build_dir=APP_ROOT / "web" / "dist",
    )
