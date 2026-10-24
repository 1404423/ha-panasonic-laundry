"""Panasonic washer-dryer (スマホで洗濯) integration: status of the drum washer and finish-time reservations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from datetime import time as dt_time  # NOT `time`: this package has a platform module time.py, and importing it rebinds the name `time` in this namespace
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import LaundryApi, LaundryApiError
from .auth import LaundryAuth, LaundryAuthError
from .const import (
    API_TIMEZONE,
    COURSES,
    CONF_ACCESS_TOKEN,
    CONF_APPLIANCE_ID,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    MAX_RESERVE_MINUTES,
    P_COURSE,
    SCAN_INTERVAL_SECONDS,
)
from .decode import decode_history, decode_reservation, decode_state
from .reservation import (
    blockers,
    build_cancel_cmds,
    build_reserve_cmds,
    build_start_cmds,
    minutes_until,
    next_occurrence,
    start_blockers,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "select", "time", "button"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_RESERVE = "reserve"
SERVICE_CANCEL = "cancel_reservation"
SERVICE_START = "start"
RESERVE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("course"): cv.string,
        vol.Required("finish_time"): cv.time,
    }
)
CANCEL_SCHEMA = vol.Schema({vol.Optional("entry_id"): cv.string})

SEND_ATTEMPTS = 3
SEND_RETRY_DELAY = 8      # s, the cloud sometimes answers "communication with the washer failed" once
VERIFY_DELAY = 3          # s between sending and reading the status back
VERIFY_TRIES = 4


def course_options(history: list[str]) -> dict[str, str]:
    """{option text: course code} for the courses in the history (names made unique if two codes share one)."""
    options: dict[str, str] = {}
    for code in history:
        name = COURSES[code]
        if name in options:
            name = f"{name} [{code}]"
        options[name] = code
    return options


class LaundryCoordinator(DataUpdateCoordinator[dict[str, str]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: LaundryApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.api = api
        self.appliance_id: str = entry.data[CONF_APPLIANCE_ID]
        # what the select / time entities and the "reserve" button use
        self.reservation_course: str | None = None
        self.reservation_time: dt_time = dt_time(7, 0)
        self._lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, str]:
        try:
            return await self.api.async_get_status(self.appliance_id)
        except LaundryAuthError as err:
            if err.invalid_grant:
                raise ConfigEntryAuthFailed(str(err)) from err
            raise UpdateFailed(str(err)) from err
        except LaundryApiError as err:
            raise UpdateFailed(str(err)) from err

    # --- reservation --------------------------------------------------------------------------------------------

    def history(self) -> list[str]:
        return decode_history(self.data or {})

    def effective_course(self) -> str | None:
        """The course the Reserve button uses: the one chosen in the select; if none was chosen, the course that is selected
        on the washer (the only one the washer accepts through the cloud so far); else the most recent one."""
        history = self.history()
        if self.reservation_course in history:
            return self.reservation_course
        current = (self.data or {}).get(P_COURSE, "").upper()
        if current in history:
            return current
        return history[0] if history else None

    def resolve_course(self, text: str) -> str:
        """Course code for a name or code; only courses from the washer's history are allowed."""
        options = course_options(self.history())
        if text in options:
            return options[text]
        if text.upper() in options.values():
            return text.upper()
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="course_not_in_history")

    async def _async_send(self, cmds: list[tuple[str, str]]) -> None:
        last: LaundryApiError | None = None
        for attempt in range(SEND_ATTEMPTS):
            try:
                await self.api.async_control(self.appliance_id, cmds)
                return
            except LaundryApiError as err:
                last = err
                if not err.transient or attempt == SEND_ATTEMPTS - 1:
                    break
                await asyncio.sleep(SEND_RETRY_DELAY)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="send_failed", translation_placeholders={"error": str(last)}
        ) from last

    async def _async_wait_for(self, reservation: str) -> bool:
        for _ in range(VERIFY_TRIES):
            await asyncio.sleep(VERIFY_DELAY)
            await self.async_refresh()
            if decode_reservation(self.data or {}) == reservation:
                return True
        return False

    async def async_reserve(self, course: str, finish_at: datetime) -> None:
        """Reserve `course` to finish at `finish_at`. Checks the washer first and reads the state back afterwards."""
        async with self._lock:
            await self.async_refresh()
            status = self.data or {}
            for reason in blockers(status):
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key=f"blocked_{reason}")
            if decode_reservation(status) == "reserved":
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="already_reserved")
            if course not in self.history():
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="course_not_in_history")
            minutes = minutes_until(finish_at, dt_util.now())
            if not 10 <= minutes <= MAX_RESERVE_MINUTES:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="time_out_of_range")
            _LOGGER.info("Reserving course %s to finish in %s min (%s)", course, minutes, finish_at)
            try:
                await self._async_send(build_reserve_cmds(status, course, minutes))
            except HomeAssistantError as err:
                if course != status.get(P_COURSE):
                    # Tested 2026-10-12: through the cloud the washer refused other courses than the one selected on
                    # it (A1 / BF), maybe because of the course type; so say what to do instead of a bare error.
                    raise HomeAssistantError(translation_domain=DOMAIN, translation_key="course_not_accepted") from err
                raise
            if not await self._async_wait_for("reserved"):
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="reserve_not_confirmed")

    async def async_start(self) -> None:
        """Start the course that is selected on the washer now. Checks the washer first and reads the state back."""
        async with self._lock:
            await self.async_refresh()
            for reason in start_blockers(self.data or {}):
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key=f"blocked_{reason}" if reason != "already_reserved" else "start_while_reserved")
            _LOGGER.info("Starting the selected course (%s)", (self.data or {}).get(P_COURSE))
            await self._async_send(build_start_cmds())
            for _ in range(VERIFY_TRIES + 1):
                await asyncio.sleep(VERIFY_DELAY)
                await self.async_refresh()
                if decode_state(self.data or {}) in ("running", "paused"):
                    return
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="start_not_confirmed")

    async def async_cancel_reservation(self) -> None:
        """Turn the reservation off; the cloud sometimes fails once, so it is retried and checked."""
        async with self._lock:
            await self.async_refresh()
            if decode_reservation(self.data or {}) != "reserved":
                return
            for attempt in range(SEND_ATTEMPTS + 1):
                try:
                    await self._async_send(build_cancel_cmds())
                except HomeAssistantError:
                    if attempt == SEND_ATTEMPTS:
                        raise
                    await asyncio.sleep(SEND_RETRY_DELAY)
                    continue
                if await self._async_wait_for("off"):
                    return
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="cancel_not_confirmed")


# --- setup ------------------------------------------------------------------------------------------------------


def _coordinators(hass: HomeAssistant, entry_id: str | None) -> list[LaundryCoordinator]:
    entries = [e for e in hass.config_entries.async_loaded_entries(DOMAIN) if entry_id in (None, e.entry_id)]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_washer")
    return [e.runtime_data for e in entries]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def handle_reserve(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call.data.get("entry_id")):
            course = coordinator.resolve_course(call.data["course"])
            await coordinator.async_reserve(course, next_occurrence(call.data["finish_time"], dt_util.now()))

    async def handle_cancel(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call.data.get("entry_id")):
            await coordinator.async_cancel_reservation()

    async def handle_start(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call.data.get("entry_id")):
            await coordinator.async_start()

    hass.services.async_register(DOMAIN, SERVICE_RESERVE, handle_reserve, schema=RESERVE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_START, handle_start, schema=CANCEL_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CANCEL, handle_cancel, schema=CANCEL_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async def _store_tokens(tokens: dict[str, Any]) -> None:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **tokens})

    auth = LaundryAuth(
        async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        expires_at=entry.data[CONF_EXPIRES_AT],
        on_tokens_updated=_store_tokens,
    )
    time_zone = await dt_util.async_get_time_zone(API_TIMEZONE)         # loaded in the executor, once, not per request
    if time_zone is None:
        raise ConfigEntryError(f"Time zone data for {API_TIMEZONE} is not available")
    coordinator = LaundryCoordinator(hass, entry, LaundryApi(async_get_clientsession(hass), auth, time_zone))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
