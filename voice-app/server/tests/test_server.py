from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
import requests

from agent import describe_demographics_for_agent, read_patient_id_from_metadata, wait_for_demographics
from app import create_app
from demographics import extract_shareable_demographics
from integuru_client import InteguruClient, LookupOutcome, PatientLookup, classify_integuru_response
from settings import load_settings

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
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="lk-key",
        livekit_api_secret="lk-secret-that-is-long-enough-for-hs256",
    )
    return replace(base, **overrides)


def build_client(outcome, record=None, settings=None):
    integuru = MagicMock(spec=InteguruClient)
    integuru.read_patient.return_value = PatientLookup(outcome, record)
    app = create_app(settings or build_settings(), integuru)
    return app.test_client(), integuru


def decode_jwt_claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


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
def test_verify_maps_failures_to_friendly_messages_without_token(outcome, expected_status):
    client, _ = build_client(outcome)
    response = client.post("/api/patients/verify", json={"patientId": "298724"})
    body = response.get_json()
    assert response.status_code == expected_status
    assert body["message"]
    assert "participantToken" not in body


def test_verify_refuses_when_livekit_not_configured():
    client, integuru = build_client(LookupOutcome.FOUND, SAMPLE_RECORD, build_settings(livekit_api_secret=""))
    response = client.post("/api/patients/verify", json={"patientId": "298724"})
    assert response.status_code == 503
    assert response.get_json()["status"] == "voice_unavailable"
    integuru.read_patient.assert_not_called()


def test_verify_returns_call_token_that_only_carries_the_patient_id():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    body = client.post("/api/patients/verify", json={"patientId": " 298724 "}).get_json()
    claims = decode_jwt_claims(body["participantToken"])
    dispatch = claims["roomConfig"]["agents"][0]

    assert body["status"] == "found" and body["displayName"] == "Test Wedge"
    assert body["serverUrl"] == "wss://example.livekit.cloud"
    assert dispatch["agentName"] == "patient-demographics"
    assert json.loads(dispatch["metadata"]) == {"patientId": "298724"}
    assert "Wedge" not in json.dumps(claims) and "123-45-6789" not in json.dumps(claims)


def test_each_call_gets_its_own_room():
    client, _ = build_client(LookupOutcome.FOUND, SAMPLE_RECORD)
    rooms = {
        decode_jwt_claims(client.post("/api/patients/verify", json={"patientId": "298724"}).get_json()["participantToken"])["video"]["room"]
        for _ in range(3)
    }
    assert len(rooms) == 3


def test_config_reports_voice_readiness():
    ready_client, _ = build_client(LookupOutcome.FOUND)
    missing_client, _ = build_client(LookupOutcome.FOUND, settings=build_settings(livekit_url=""))
    assert ready_client.get("/api/config").get_json() == {"voiceReady": True}
    assert missing_client.get("/api/config").get_json() == {"voiceReady": False}


@pytest.mark.parametrize(
    "metadata, expected",
    [('{"patientId": "298724"}', "298724"), ("", None), (None, None), ("not json", None), ('{"patientId": "12ab"}', None), ('["298724"]', None)],
)
def test_agent_reads_patient_id_from_dispatch_metadata(metadata, expected):
    assert read_patient_id_from_metadata(metadata) == expected


def test_agent_shares_demographics_without_ssn_or_insurance():
    shared = describe_demographics_for_agent(extract_shareable_demographics(SAMPLE_RECORD))
    parsed = json.loads(shared)
    assert parsed["patient_name"] == "Test Wedge"
    assert parsed["primary_care_provider"] == "1st, Attempt"
    assert "123-45-6789" not in shared and "secret plan" not in shared
    assert "email" not in parsed


def test_agent_falls_back_when_record_is_missing():
    assert describe_demographics_for_agent(None) == "I couldn't get that record right now. Please end the call and try again."


def test_agent_stops_waiting_for_a_slow_record():
    async def run_scenario():
        never_finishes = asyncio.get_running_loop().create_future()
        return await wait_for_demographics(never_finishes, timeout_seconds=0.01)

    assert asyncio.run(run_scenario()) is None


def test_agent_stops_waiting_when_lookup_fails():
    async def run_scenario():
        async def failing_lookup():
            raise RuntimeError("boom")

        return await wait_for_demographics(asyncio.create_task(failing_lookup()), timeout_seconds=1)

    assert asyncio.run(run_scenario()) is None


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
        (200, {"status_code": 200, "body": SAMPLE_RECORD, "success": True, "request_id": "r1"}, LookupOutcome.FOUND),
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
