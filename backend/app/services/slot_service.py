"""Simulated hospital appointment slot database.

Each provider has a pool of time slots for the next 3 days.
Slots are pre-populated at first access and persisted in the in-memory store.
When a booking is confirmed, the corresponding slot is marked as BOOKED.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


# Business hours — 30-minute slots
_SLOT_TIMES = [
    (9, 0), (9, 30), (10, 0), (10, 30), (11, 0),
    (14, 0), (14, 30), (15, 0), (15, 30), (16, 0), (16, 30),
]

# Fraction of slots that start pre-booked (simulates existing appointments)
_PREBOOKED_RATIO = 0.30


def _seed(provider_id: str, day_offset: int, slot_idx: int) -> int:
    """Deterministic pseudo-random seed so the same provider always has the
    same initial availability pattern — simulating a stable hospital DB."""
    h = 0
    for ch in provider_id:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return (h ^ (day_offset * 0x9E3779B9) ^ (slot_idx * 0x6C62272E)) & 0xFFFFFFFF


def initialize_slots(provider_id: str) -> list[dict[str, Any]]:
    """Generate the full 3-day slot list for a provider.

    Returns a list of slot dicts:
        slot_id   – unique string identifier
        iso       – ISO 8601 datetime string
        date_label – human-readable date (e.g. "Tue, Apr 22")
        time_label – human-readable time (e.g. "9:30 AM")
        status    – "available" | "booked"
    """
    slots: list[dict[str, Any]] = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for day_offset in range(1, 4):          # tomorrow, day+2, day+3
        date = today + timedelta(days=day_offset)
        date_label = date.strftime('%a, %b %-d')

        for idx, (hour, minute) in enumerate(_SLOT_TIMES):
            dt = date.replace(hour=hour, minute=minute)
            slot_id = f"{provider_id}_{date.strftime('%Y%m%d')}_{hour:02d}{minute:02d}"

            # Deterministic pre-booked decision
            seed = _seed(provider_id, day_offset, idx)
            pre_booked = (seed % 100) < int(_PREBOOKED_RATIO * 100)

            am_pm = 'AM' if hour < 12 else 'PM'
            display_hour = hour if hour <= 12 else hour - 12
            time_label = f"{display_hour}:{minute:02d} {am_pm}"

            slots.append({
                'slot_id': slot_id,
                'iso': dt.isoformat(),
                'date_label': date_label,
                'time_label': time_label,
                'status': 'booked' if pre_booked else 'available',
            })

    return slots


def get_or_init_slots(provider_id: str, store_ref: Any) -> list[dict[str, Any]]:
    """Return slots from the store, initializing them if first access."""
    if provider_id not in store_ref.provider_slots:
        store_ref.provider_slots[provider_id] = initialize_slots(provider_id)
    return store_ref.provider_slots[provider_id]


def mark_slot_booked(provider_id: str, slot_id: str, store_ref: Any) -> bool:
    """Mark a specific slot as booked. Returns True if the slot was found and
    was available, False if already booked or not found."""
    slots = get_or_init_slots(provider_id, store_ref)
    for slot in slots:
        if slot['slot_id'] == slot_id:
            if slot['status'] == 'booked':
                return False   # already taken
            slot['status'] = 'booked'
            return True
    return False
