from __future__ import annotations

import threading
import time
from typing import Optional

VERIFIED_PATIENT_LIFETIME_SECONDS = 30 * 60


class VerifiedPatientCache:
    def __init__(self, lifetime_seconds: int = VERIFIED_PATIENT_LIFETIME_SECONDS, clock=time.monotonic):
        self._lifetime_seconds = lifetime_seconds
        self._clock = clock
        self._entries: dict = {}
        self._lock = threading.Lock()

    def remember(self, patient_id: str, demographics: dict) -> None:
        with self._lock:
            self._entries[patient_id] = (self._clock(), demographics)

    def recall(self, patient_id: str) -> Optional[dict]:
        with self._lock:
            entry = self._entries.get(patient_id)
            if entry is None:
                return None
            stored_at, demographics = entry
            if self._clock() - stored_at > self._lifetime_seconds:
                del self._entries[patient_id]
                return None
            return demographics
