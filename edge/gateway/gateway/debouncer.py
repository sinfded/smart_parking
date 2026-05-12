"""Debounces ultrasonic distance readings into confirmed slot state transitions.

Rules (from CLAUDE.md):
  - Rolling window of 5 readings per slot.
  - 3 consecutive readings must agree before a state change is confirmed.
  - < 80 cm  → occupied  |  > 120 cm → free  |  in-between → ignored.
  - 10-second cooldown after each confirmed transition.
"""

import asyncio
from collections import deque
from datetime import datetime
from typing import Awaitable, Callable

import structlog

from .config import Settings

log = structlog.get_logger()

StateCallback = Callable[[str, str], Awaitable[None]]  # (slot_label, new_state)


class SlotDebouncer:
    def __init__(self, settings: Settings) -> None:
        self._s         = settings
        self._window: deque[str] = deque(maxlen=settings.rolling_window)
        self._state     = "unknown"
        self._cooldown  = False

    def classify(self, distance_cm: float) -> str | None:
        if distance_cm < self._s.distance_occupied_cm:
            return "occupied"
        if distance_cm > self._s.distance_free_cm:
            return "free"
        return None  # in dead-band, ignore

    def push(self, distance_cm: float) -> str | None:
        """Return a new confirmed state, or None if no transition yet."""
        reading = self.classify(distance_cm)
        if reading is None:
            return None
        self._window.append(reading)

        # Need confirm_readings consecutive matching readings at the tail
        tail = list(self._window)[-self._s.confirm_readings:]
        if len(tail) < self._s.confirm_readings:
            return None
        if len(set(tail)) != 1:
            return None
        new_state = tail[0]
        if new_state == self._state or self._cooldown:
            return None
        return new_state

    async def apply(self, new_state: str) -> None:
        self._state    = new_state
        self._cooldown = True
        await asyncio.sleep(self._s.cooldown_seconds)
        self._cooldown = False


class Debouncer:
    def __init__(self, settings: Settings, on_state_change: StateCallback) -> None:
        self._s        = settings
        self._callback = on_state_change
        self._slots: dict[str, SlotDebouncer] = {}

    async def handle(self, slot_label: str, payload: dict) -> None:
        distance = payload.get("distance_cm")
        if distance is None:
            return

        if slot_label not in self._slots:
            self._slots[slot_label] = SlotDebouncer(self._s)

        debouncer = self._slots[slot_label]
        new_state = debouncer.push(float(distance))
        if new_state is None:
            return

        log.info("slot.transition", label=slot_label, state=new_state)
        asyncio.create_task(debouncer.apply(new_state))
        await self._callback(slot_label, new_state)
