from __future__ import annotations

import hmac
import json
import logging
from typing import Any, Optional

from demographics import build_display_name
from verified_patients import VerifiedPatientCache

logger = logging.getLogger(__name__)

DEMOGRAPHICS_TOOL_NAME = "get_patient_demographics"
RECORD_UNAVAILABLE_REPLY = "I couldn't get that record right now. Please end the call and try again."
UNVERIFIED_PATIENT_REPLY = "I can only share details for the patient that was verified when this call started."
UNKNOWN_TOOL_REPLY = "That tool isn't available."
MAX_PATIENT_ID_LENGTH = 10


def is_request_from_vapi(received_secret: Optional[str], expected_secret: str) -> bool:
    if not expected_secret or not received_secret:
        return False
    return hmac.compare_digest(received_secret.encode(), expected_secret.encode())


def build_tool_call_results(payload: Any, verified_patients: VerifiedPatientCache) -> Optional[dict]:
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict) or message.get("type") != "tool-calls":
        return None

    call_patient_id = read_patient_id_from_call(message.get("call"))
    tool_calls = message.get("toolCallList") if isinstance(message.get("toolCallList"), list) else []
    results = [answer_tool_call(tool_call, call_patient_id, verified_patients) for tool_call in tool_calls if isinstance(tool_call, dict)]
    return {"results": results}


def answer_tool_call(tool_call: dict, call_patient_id: Optional[str], verified_patients: VerifiedPatientCache) -> dict:
    tool_call_id = str(tool_call.get("id", ""))
    function = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}

    if function.get("name") != DEMOGRAPHICS_TOOL_NAME:
        return {"toolCallId": tool_call_id, "result": UNKNOWN_TOOL_REPLY}

    requested_patient_id = read_patient_id_from_arguments(function.get("arguments"))
    if call_patient_id and requested_patient_id and requested_patient_id != call_patient_id:
        logger.warning("Tool asked for patient %s during a call for %s", requested_patient_id, call_patient_id)
        return {"toolCallId": tool_call_id, "result": UNVERIFIED_PATIENT_REPLY}

    patient_id = call_patient_id or requested_patient_id
    demographics = verified_patients.recall(patient_id) if patient_id else None
    if demographics is None:
        return {"toolCallId": tool_call_id, "result": UNVERIFIED_PATIENT_REPLY if patient_id else RECORD_UNAVAILABLE_REPLY}

    return {"toolCallId": tool_call_id, "result": json.dumps({"patient_name": build_display_name(demographics), **demographics})}


def read_patient_id_from_call(call: Any) -> Optional[str]:
    if not isinstance(call, dict):
        return None
    overrides = call.get("assistantOverrides") if isinstance(call.get("assistantOverrides"), dict) else {}
    variable_values = overrides.get("variableValues") if isinstance(overrides.get("variableValues"), dict) else {}
    return clean_patient_id(variable_values.get("patientId"))


def read_patient_id_from_arguments(arguments: Any) -> Optional[str]:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return None
    if not isinstance(arguments, dict):
        return None
    return clean_patient_id(arguments.get("patient_id"))


def clean_patient_id(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text if is_valid_patient_id(text) else None


def is_valid_patient_id(text: str) -> bool:
    return text.isdigit() and 1 <= len(text) <= MAX_PATIENT_ID_LENGTH
