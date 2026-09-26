from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
import requests

from app import create_app
from integuru_client import InteguruClient, LookupOutcome, PatientLookup, classify_integuru_response
from settings import load_settings
from vapi_webhook import DEMOGRAPHICS_TOOL_NAME
from verified_patients import VerifiedPatientCache

SECRET = "test-secret"
SAMPLE_RECORD = {
    "patient_id": "298724",
    "personal_info": {"fname": "Test", "lname": "Wedge", "dob": "07/07/2000", "sex": "male", "ssn": "123-45-6789"},
    "contact": {"phone": "555-123-1111", "email": ""},
    "providers": {"doctorName": "1st, Attempt"},
    "insurance": {"insurances": [{"name": "secret plan"}]},
}


def build_settings(**overrides):
    base = replace(
        load_settings(),
        integuru_api_key="key",
        vapi_public_key="pub",
        vapi_assistant_id="asst",
        vapi_webhook_secret=SECRET,
    )
    return replace(base, **overrides)


def build_client(outcome, record=None, settings=None):
    integuru = MagicMock(spec=InteguruClient)
    integuru.read_patient.return_value = PatientLookup(outcome, record)
    app = create_app(settings or build_settings(), integuru)
    return app.test_client(), integuru


def build_tool_call_payload(patient_id_in_call="298724", patient_id_in_arguments="298724", tool_name=DEMOGRAPHICS_TOOL_NAME):
    return {
        "message": {
            "type": "tool-calls",
            "call": {"assistantOverrides": {"variableValues": {"patientId": patient_id_in_call}}},
            "toolCallList": [
                {"id": "call-1", "type": "function", "function": {"name": tool_name, "arguments": {"patient_id": patient_id_in_arguments}}}
            ],
        }
    }


@pytest.mark.parametrize("body", [None, {}, {"patientId": ""}, {"patientId": "12ab"}, {"patientId": "12345678901"}, "not json"])
def test_verify_rejects_invalid_patient_ids(body):
    client, integuru = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    response = client.post("/api/patients/verify", json=body)
    assert response.status_code == 400
    integuru.read_patient.assert_not_called()


@pytest.mark.parametrize(
    "outcome, expected_status",
    [(LookupOutcome.NOT_FOUND, 404), (LookupOutcome.UNAVAILABLE, 503), (LookupOutcome.AUTH_FAILED, 503)],
)
def test_verify_maps_failures_to_friendly_messages(outcome, expected_status):
    client, _ = build_client(outcome)
    response = client.post("/api/patients/verify", json={"patientId": "298724"})
    assert response.status_code == expected_status
    assert response.get_json()["message"]


def test_verify_returns_display_name_without_record():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    response = client.post("/api/patients/verify", json={"patientId": " 298724 "})
    body = response.get_json()
    assert response.status_code == 200
    assert body == {"status": "found", "patientId": "298724", "displayName": "Test Wedge"}


def test_webhook_rejects_wrong_secret():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    response = client.post("/api/vapi/webhook", json=build_tool_call_payload(), headers={"X-Vapi-Secret": "wrong"})
    assert response.status_code == 401


def test_webhook_rejects_everything_when_secret_unset():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD, build_settings(vapi_webhook_secret=""))
    response = client.post("/api/vapi/webhook", json=build_tool_call_payload(), headers={"X-Vapi-Secret": ""})
    assert response.status_code == 401


def test_webhook_answers_verified_patient_without_ssn_or_insurance():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    client.post("/api/patients/verify", json={"patientId": "298724"})
    response = client.post("/api/vapi/webhook", json=build_tool_call_payload(), headers={"X-Vapi-Secret": SECRET})
    result = response.get_json()["results"][0]
    shared = json.loads(result["result"])
    assert result["toolCallId"] == "call-1"
    assert shared["date_of_birth"] == "07/07/2000"
    assert shared["primary_care_provider"] == "1st, Attempt"
    assert "ssn" not in json.dumps(shared) and "123-45-6789" not in json.dumps(shared)
    assert "insurance" not in json.dumps(shared)
    assert "email" not in shared


def test_webhook_refuses_unverified_patient():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    response = client.post("/api/vapi/webhook", json=build_tool_call_payload(), headers={"X-Vapi-Secret": SECRET})
    assert "verified" in response.get_json()["results"][0]["result"]


def test_webhook_refuses_patient_other_than_the_call_patient():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    client.post("/api/patients/verify", json={"patientId": "298724"})
    payload = build_tool_call_payload(patient_id_in_arguments="111111")
    response = client.post("/api/vapi/webhook", json=payload, headers={"X-Vapi-Secret": SECRET})
    assert "verified" in response.get_json()["results"][0]["result"]


@pytest.mark.parametrize("payload", [None, {}, {"message": "x"}, {"message": {"type": "status-update"}}, {"message": {"type": "tool-calls", "toolCallList": "bad"}}])
def test_webhook_survives_malformed_payloads(payload):
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    response = client.post("/api/vapi/webhook", json=payload, headers={"X-Vapi-Secret": SECRET})
    assert response.status_code == 200


def test_webhook_answers_unknown_tool_safely():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    payload = build_tool_call_payload(tool_name="delete_everything")
    response = client.post("/api/vapi/webhook", json=payload, headers={"X-Vapi-Secret": SECRET})
    assert response.get_json()["results"][0]["result"] == "That tool isn't available."


def test_config_hides_keys_when_voice_not_configured():
    client, _ = build_client(LookupOutcome.FOUND, settings=build_settings(vapi_public_key=""))
    assert client.get("/api/config").get_json() == {"voiceReady": False, "publicKey": "", "assistantId": ""}


@pytest.mark.parametrize(
    "status, payload, expected",
    [
        (401, None, LookupOutcome.AUTH_FAILED),
        (404, None, LookupOutcome.NOT_FOUND),
        (500, None, LookupOutcome.UNAVAILABLE),
        (429, None, LookupOutcome.UNAVAILABLE),
        (200, None, LookupOutcome.NOT_FOUND),
        (200, {"status_code": 404, "body": {"error": "missing"}}, LookupOutcome.NOT_FOUND),
        (200, {"status_code": 500, "body": {"personal_info": {"fname": "A"}}}, LookupOutcome.UNAVAILABLE),
        (200, {"status_code": 500, "body": {"error": "session expired"}}, LookupOutcome.UNAVAILABLE),
        (200, {"status_code": 400, "body": {"error": "bad input"}}, LookupOutcome.UNAVAILABLE),
        (200, {"output": {"personal_info": {"fname": "", "lname": "", "dob": ""}}}, LookupOutcome.NOT_FOUND),
        (200, {"output": {"status_code": 200, "body": SAMPLE_RECORD}}, LookupOutcome.FOUND),
        (200, SAMPLE_RECORD, LookupOutcome.FOUND),
    ],
)
def test_classify_integuru_response(status, payload, expected):
    assert classify_integuru_response(status, payload).outcome is expected


def test_integuru_client_retries_once_then_reports_unavailable():
    http = MagicMock()
    http.post.side_effect = requests.Timeout("slow")
    client = InteguruClient(build_settings(), http)
    assert client.read_patient("298724").outcome is LookupOutcome.UNAVAILABLE
    assert http.post.call_count == 2


def test_integuru_client_without_key_does_not_call_api():
    http = MagicMock()
    client = InteguruClient(build_settings(integuru_api_key=""), http)
    assert client.read_patient("298724").outcome is LookupOutcome.AUTH_FAILED
    http.post.assert_not_called()


def test_verified_patient_cache_expires_entries():
    now = [0.0]
    cache = VerifiedPatientCache(lifetime_seconds=10, clock=lambda: now[0])
    cache.remember("1", {"first_name": "A"})
    now[0] = 11
    assert cache.recall("1") is None
