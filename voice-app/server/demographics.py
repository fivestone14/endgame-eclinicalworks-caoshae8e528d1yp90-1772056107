from __future__ import annotations

from typing import Optional

SHAREABLE_FIELDS_BY_SECTION = {
    "personal_info": {
        "fname": "first_name",
        "mname": "middle_name",
        "lname": "last_name",
        "PreferredName": "preferred_name",
        "dob": "date_of_birth",
        "sex": "sex",
        "deceased": "deceased",
    },
    "contact": {
        "phone": "home_phone",
        "mobile": "mobile_phone",
        "email": "email",
    },
    "address": {
        "address1": "address_line_1",
        "address2": "address_line_2",
        "city": "city",
        "state": "state",
        "zip": "zip",
        "Country": "country",
    },
    "demographics": {
        "maritalstatus": "marital_status",
        "race": "race",
        "EthnicityName": "ethnicity",
        "language": "language",
        "Translator": "needs_translator",
    },
    "providers": {
        "doctorName": "primary_care_provider",
    },
}

YES_NO_FIELDS = {"deceased", "needs_translator"}


def extract_shareable_demographics(record: Optional[dict]) -> dict:
    record = record or {}
    shareable = {}
    for section_name, field_names in SHAREABLE_FIELDS_BY_SECTION.items():
        section = record.get(section_name) or {}
        for source_key, public_key in field_names.items():
            value = normalize_field_value(section.get(source_key))
            if value is None:
                continue
            shareable[public_key] = describe_yes_no(value) if public_key in YES_NO_FIELDS else value
    return shareable


def normalize_field_value(value) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def describe_yes_no(value: str) -> str:
    return "yes" if value in ("1", "Y", "y", "true", "True") else "no"


def build_display_name(demographics: dict) -> str:
    name_parts = (demographics.get("first_name"), demographics.get("last_name"))
    return " ".join(part for part in name_parts if part) or "Unknown patient"
