from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import requests

from settings import Settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
ATTEMPTS_BEFORE_GIVING_UP = 2
ENVELOPE_KEYS_IN_PRIORITY_ORDER = ("output", "result", "data", "body")
MAX_ENVELOPE_DEPTH = 3


class LookupOutcome(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    AUTH_FAILED = "auth_failed"


@dataclass(frozen=True)
class PatientLookup:
    outcome: LookupOutcome
    record: Optional[dict] = None


class InteguruClient:
    def __init__(self, settings: Settings, http: Optional[requests.Session] = None):
        self._settings = settings
        self._http = http or requests.Session()

    def read_patient(self, patient_id: str) -> PatientLookup:
        if not self._settings.integuru_api_key:
            logger.error("INTEGURU_API_KEY is not set")
            return PatientLookup(LookupOutcome.AUTH_FAILED)

        for attempt_number in range(1, ATTEMPTS_BEFORE_GIVING_UP + 1):
            lookup = self._attempt_read(patient_id, attempt_number)
            if lookup.outcome is not LookupOutcome.UNAVAILABLE:
                return lookup
        return PatientLookup(LookupOutcome.UNAVAILABLE)

    def _attempt_read(self, patient_id: str, attempt_number: int) -> PatientLookup:
        try:
            response = self._http.post(
                self._settings.integuru_invoke_url,
                headers={"Authorization": f"Bearer {self._settings.integuru_api_key}"},
                json=self._build_read_request(patient_id),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            logger.warning("Integuru request failed on attempt %s: %s", attempt_number, error)
            return PatientLookup(LookupOutcome.UNAVAILABLE)

        return classify_integuru_response(response.status_code, safely_parse_json(response))

    def _build_read_request(self, patient_id: str) -> dict:
        return {
            "integration_id": self._settings.demographics_integration_id,
            "account_id": self._settings.integuru_account_id,
            "input": {"action": "read", "patient_id": patient_id},
        }


def safely_parse_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        logger.warning("Integuru returned non-JSON body with status %s", response.status_code)
        return None


def classify_integuru_response(http_status: int, payload: Any) -> PatientLookup:
    if http_status in (401, 403):
        logger.error("Integuru rejected the API key (status %s)", http_status)
        return PatientLookup(LookupOutcome.AUTH_FAILED)
    if http_status == 404:
        return PatientLookup(LookupOutcome.NOT_FOUND)
    if http_status >= 400:
        logger.warning("Integuru returned status %s", http_status)
        return PatientLookup(LookupOutcome.UNAVAILABLE)

    inner_status, record = unwrap_integration_payload(payload)
    if inner_status == 404:
        return PatientLookup(LookupOutcome.NOT_FOUND)
    if inner_status is not None and inner_status >= 400:
        logger.warning("Integration reported status %s", inner_status)
        return PatientLookup(LookupOutcome.UNAVAILABLE)
    if looks_like_missing_patient(record):
        return PatientLookup(LookupOutcome.NOT_FOUND)
    return PatientLookup(LookupOutcome.FOUND, record)


def unwrap_integration_payload(payload: Any) -> tuple:
    inner_status = None
    current = payload
    for _ in range(MAX_ENVELOPE_DEPTH):
        if not isinstance(current, dict):
            break
        if isinstance(current.get("status_code"), int):
            inner_status = current["status_code"]
        if "personal_info" in current:
            return inner_status, current
        nested = next((current[key] for key in ENVELOPE_KEYS_IN_PRIORITY_ORDER if isinstance(current.get(key), dict)), None)
        if nested is None:
            break
        current = nested
    return inner_status, current if isinstance(current, dict) else None


def looks_like_missing_patient(record: Optional[dict]) -> bool:
    if not record or record.get("error"):
        return True
    personal_info = record.get("personal_info") or {}
    identifying_values = (personal_info.get("fname"), personal_info.get("lname"), personal_info.get("dob"))
    return not any(str(value or "").strip() for value in identifying_values)
