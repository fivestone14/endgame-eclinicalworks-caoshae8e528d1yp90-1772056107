from __future__ import annotations

from typing import Any, Optional

MAX_PATIENT_ID_LENGTH = 10


def clean_patient_id(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text if is_valid_patient_id(text) else None


def is_valid_patient_id(text: str) -> bool:
    return text.isdigit() and 1 <= len(text) <= MAX_PATIENT_ID_LENGTH
