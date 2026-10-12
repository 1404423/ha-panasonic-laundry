"""Decoding of the washer's status properties (no Home Assistant imports, unit-testable)."""

from __future__ import annotations

from .const import (
    P_HISTORY,
    P_RESERVATION,
    P_RESERVE_FINISH,
    P_RESERVE_START,
    COURSES,
    P_COURSE,
    P_DOOR,
    P_FAULT,
    P_POWER,
    P_PROGRESS,
    P_REMAIN_ALL,
    P_REMAIN_DRY,
    P_REMAIN_WASH,
    P_STAGE,
    PROGRESS,
    STAGES,
)

UNAVAILABLE_HEX = {"FFFF", "ffff", ""}


def hhmm_to_minutes(value: str | None) -> int | None:
    """'0123' (hex bytes HH, MM) -> minutes; FFFF / missing -> None."""
    if value is None or value in UNAVAILABLE_HEX or len(value) != 4:
        return None
    return int(value[:2], 16) * 60 + int(value[2:], 16)


def decode_state(status: dict[str, str]) -> str:
    """off / error / running / paused / done / waiting."""
    if status.get(P_POWER) == "31":
        return "off"
    if status.get(P_FAULT) == "41":
        return "error"
    kind = STAGES.get((status.get(P_STAGE) or "").upper(), ("", "wait"))[1]
    return {"run": "running", "pause": "paused", "done": "done", "wait": "waiting"}[kind]


def decode_remaining(status: dict[str, str]) -> int | None:
    """Remaining minutes: the combined washing+drying value first, else whichever is present."""
    for prop in (P_REMAIN_ALL, P_REMAIN_WASH, P_REMAIN_DRY):
        minutes = hhmm_to_minutes(status.get(prop))
        if minutes is not None:
            return minutes
    return None


def decode_progress_text(status: dict[str, str]) -> str | None:
    return PROGRESS.get((status.get(P_PROGRESS) or "").upper())


def decode_course_text(status: dict[str, str]) -> str | None:
    return COURSES.get((status.get(P_COURSE) or "").upper())


def decode_door(status: dict[str, str]) -> str | None:
    """'open' / 'closed' (ECHONET: 41 open, 42 closed)."""
    return {"41": "open", "42": "closed"}.get(status.get(P_DOOR) or "")


def decode_history(status: dict[str, str]) -> list[str]:
    """Course codes of the recent runs (0x012B), newest first; empty slots and unknown codes are skipped."""
    raw = status.get(P_HISTORY) or ""
    codes = []
    for i in range(0, len(raw) - 7, 8):
        code = raw[i : i + 2].upper()
        if code in COURSES and code not in ("00", "FF"):
            codes.append(code)
    return codes


def decode_reservation(status: dict[str, str]) -> str | None:
    """'reserved' / 'off' from 0x0090 (41 / 42)."""
    return {"41": "reserved", "42": "off"}.get(status.get(P_RESERVATION) or "")


def decode_reserve_finish_minutes(status: dict[str, str]) -> int | None:
    return hhmm_to_minutes(status.get(P_RESERVE_FINISH)) if decode_reservation(status) == "reserved" else None


def decode_reserve_start_minutes(status: dict[str, str]) -> int | None:
    return hhmm_to_minutes(status.get(P_RESERVE_START)) if decode_reservation(status) == "reserved" else None
