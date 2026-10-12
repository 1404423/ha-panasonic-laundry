"""Building and checking reservation commands (no Home Assistant imports, unit-testable).

A finish-time reservation is one control request with 0092 (time until finished, hex HH MM), 0090 = 41 (timer on) and
00D0 (course); cancelling is 0090 = 42. Verified on a NA-LX127CL-W on 2026-10-12.
"""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta

from .const import (
    MAX_RESERVE_MINUTES,
    P_COURSE,
    P_DETERGENT_MODE,
    P_DOOR,
    P_FAULT,
    P_POWER,
    P_REMOTE,
    P_START,
    P_RESERVATION,
    P_RESERVE_FINISH,
    P_SOFTENER_MODE,
    P_STAGE,
    STAGES,
)


def hex_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02X}{minutes % 60:02X}"


def next_occurrence(at: time, now: datetime) -> datetime:
    """The next time the clock shows `at` (today if still ahead, else tomorrow); seconds are dropped."""
    target = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def minutes_until(target: datetime, now: datetime) -> int:
    """Minutes from now to `target`, rounded up to the 10-minute steps the washer works in."""
    return math.ceil(((target - now).total_seconds() / 60) / 10) * 10


def blockers(status: dict[str, str]) -> list[str]:
    """Reasons why a reservation must not be sent now (translation keys); empty = go."""
    problems = []
    if status.get(P_POWER) != "30":
        problems.append("power_off")
    if status.get(P_FAULT) == "41":
        problems.append("fault")
    if STAGES.get((status.get(P_STAGE) or "").upper(), ("", "wait"))[1] != "wait":
        problems.append("not_waiting")
    if status.get(P_DOOR) != "42":
        problems.append("door_open")
    if status.get(P_REMOTE) != "01":
        problems.append("remote_not_permitted")
    return problems


def build_reserve_cmds(status: dict[str, str], course: str, minutes: int) -> list[tuple[str, str]]:
    if not 10 <= minutes <= MAX_RESERVE_MINUTES:
        raise ValueError(f"finish time out of range: {minutes} min")
    cmds = [(P_RESERVE_FINISH, hex_hhmm(minutes)), (P_RESERVATION, "41"), (P_COURSE, course)]
    if int(course, 16) < 0xA0:  # washing / washing+drying courses: keep the current detergent/softener input modes
        for prop in (P_DETERGENT_MODE, P_SOFTENER_MODE):
            if status.get(prop):
                cmds.append((prop, status[prop]))
    return cmds


def build_cancel_cmds() -> list[tuple[str, str]]:
    return [(P_RESERVATION, "42")]


def build_start_cmds() -> list[tuple[str, str]]:
    """Start the course that is selected on the washer right now (the official app's "start" without a new course)."""
    return [(P_START, "41")]


def start_blockers(status: dict[str, str]) -> list[str]:
    """Same checks as for a reservation, plus: a reservation must be cancelled first."""
    problems = blockers(status)
    if status.get(P_RESERVATION) == "41":
        problems.append("already_reserved")
    return problems
