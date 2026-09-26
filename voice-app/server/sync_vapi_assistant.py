from __future__ import annotations

import sys

import requests

from settings import Settings, load_settings
from vapi_webhook import DEMOGRAPHICS_TOOL_NAME

VAPI_API_URL = "https://api.vapi.ai"
VAPI_REQUEST_TIMEOUT_SECONDS = 15

SYSTEM_PROMPT = """You are a front-desk assistant for a medical clinic.
The patient for this call has ID {{patientId}}.
Before answering any question about the patient, call get_patient_demographics with that ID.
Only answer questions about the patient's demographics: name, date of birth, sex, contact details, address, marital status, race, ethnicity, language, and primary care provider.
Answer only what was asked, in one or two short spoken sentences. Read dates as spoken words.
If a field is missing, say it isn't on file. Never guess.
If the tool returns an error message, say that message to the caller."""


def build_assistant_definition(settings: Settings) -> dict:
    return {
        "name": "Patient demographics assistant",
        "firstMessage": "Hi, I can answer questions about this patient's demographics. What would you like to know?",
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
            "tools": [build_demographics_tool(settings)],
        },
    }


def build_demographics_tool(settings: Settings) -> dict:
    return {
        "type": "function",
        "function": {
            "name": DEMOGRAPHICS_TOOL_NAME,
            "description": "Get the demographics of the patient on this call.",
            "parameters": {
                "type": "object",
                "properties": {"patient_id": {"type": "string", "description": "The patient's numeric ID."}},
                "required": ["patient_id"],
            },
        },
        "server": {
            "url": f"{settings.public_base_url}/api/vapi/webhook",
            "headers": {"X-Vapi-Secret": settings.vapi_webhook_secret},
        },
    }


def find_missing_settings(settings: Settings) -> list:
    required = {
        "VAPI_PRIVATE_KEY": settings.vapi_private_key,
        "VAPI_WEBHOOK_SECRET": settings.vapi_webhook_secret,
        "PUBLIC_BASE_URL": settings.public_base_url,
    }
    return [name for name, value in required.items() if not value]


def create_or_update_assistant(settings: Settings) -> str:
    headers = {"Authorization": f"Bearer {settings.vapi_private_key}"}
    definition = build_assistant_definition(settings)
    if settings.vapi_assistant_id:
        response = requests.patch(f"{VAPI_API_URL}/assistant/{settings.vapi_assistant_id}", headers=headers, json=definition, timeout=VAPI_REQUEST_TIMEOUT_SECONDS)
    else:
        response = requests.post(f"{VAPI_API_URL}/assistant", headers=headers, json=definition, timeout=VAPI_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()["id"]


def main() -> int:
    settings = load_settings()
    missing = find_missing_settings(settings)
    if missing:
        print(f"Set these in voice-app/.env first: {', '.join(missing)}")
        return 1
    try:
        assistant_id = create_or_update_assistant(settings)
    except requests.RequestException as error:
        print(f"Couldn't sync the Vapi assistant: {error}")
        return 1
    print(f"Vapi assistant ready: {assistant_id}")
    if not settings.vapi_assistant_id:
        print("Add it to voice-app/.env as VAPI_ASSISTANT_ID, then restart the server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
