from __future__ import annotations

import json
import secrets
from datetime import timedelta

from livekit import api

from settings import Settings

CALL_TOKEN_LIFETIME = timedelta(minutes=15)


def create_call_credentials(settings: Settings, patient_id: str) -> dict:
    call_id = secrets.token_hex(6)
    room_name = f"patient-call-{call_id}"
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(f"caller-{call_id}")
        .with_name("Caller")
        .with_ttl(CALL_TOKEN_LIFETIME)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .with_room_config(
            api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(agent_name=settings.agent_name, metadata=json.dumps({"patientId": patient_id}))]
            )
        )
        .to_jwt()
    )
    return {"serverUrl": settings.livekit_url, "participantToken": token}
