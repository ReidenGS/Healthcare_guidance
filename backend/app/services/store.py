from __future__ import annotations

from datetime import datetime
from typing import Any


class InMemoryStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.answers: dict[str, list[dict[str, Any]]] = {}
        self.feedback: dict[str, list[dict[str, Any]]] = {}
        self.insurance_checks: dict[str, dict[str, Any]] = {}
        self.booking_intents: dict[str, dict[str, Any]] = {}
        # Simulated provider booking database — all confirmed appointments
        self.all_bookings: list[dict[str, Any]] = []

    def now_iso(self) -> str:
        return datetime.now().astimezone().isoformat()


store = InMemoryStore()
