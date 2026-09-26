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
    vapi_public_key: str
    vapi_private_key: str
    vapi_assistant_id: str
    vapi_webhook_secret: str
    public_base_url: str
    port: int
    web_build_dir: Path

    @property
    def is_voice_configured(self) -> bool:
        return bool(self.vapi_public_key and self.vapi_assistant_id)


def load_settings() -> Settings:
    return Settings(
        integuru_api_key=os.getenv("INTEGURU_API_KEY", ""),
        integuru_invoke_url=os.getenv("INTEGURU_INVOKE_URL", "https://api.integuru.ai/integrations/invoke"),
        integuru_account_id=os.getenv("INTEGURU_ACCOUNT_ID", "98c16453-be1f-4c9f-b942-dcdfa8e526f3"),
        demographics_integration_id=os.getenv("DEMOGRAPHICS_INTEGRATION_ID", "65afea2f-a46b-40f9-b831-abdb21b01738"),
        vapi_public_key=os.getenv("VAPI_PUBLIC_KEY", ""),
        vapi_private_key=os.getenv("VAPI_PRIVATE_KEY", ""),
        vapi_assistant_id=os.getenv("VAPI_ASSISTANT_ID", ""),
        vapi_webhook_secret=os.getenv("VAPI_WEBHOOK_SECRET", ""),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
        port=int(os.getenv("PORT", "5000")),
        web_build_dir=APP_ROOT / "web" / "dist",
    )
