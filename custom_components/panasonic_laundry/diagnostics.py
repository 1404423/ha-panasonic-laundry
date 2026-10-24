"""Diagnostics: what a user can attach to an issue. Tokens, ids and the washer's nickname are redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import LaundryCoordinator
from .const import CONF_ACCESS_TOKEN, CONF_APPLIANCE_ID, CONF_EXPIRES_AT, CONF_NICKNAME, CONF_REFRESH_TOKEN

TO_REDACT = {CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, CONF_EXPIRES_AT, CONF_APPLIANCE_ID, CONF_NICKNAME, "title", "unique_id"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator: LaundryCoordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "status": dict(coordinator.data or {}),          # the washer's raw property codes (no personal data)
        "reservation_course": coordinator.reservation_course,
        "reservation_time": coordinator.reservation_time.isoformat(),
    }
