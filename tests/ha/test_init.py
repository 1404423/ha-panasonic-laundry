"""Setup, unload, failures at setup, the services' error paths and the diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.panasonic_laundry.api import LaundryApiError
from custom_components.panasonic_laundry.auth import LaundryAuthError
from custom_components.panasonic_laundry.const import DOMAIN
from custom_components.panasonic_laundry.diagnostics import async_get_config_entry_diagnostics

GET_STATUS = "custom_components.panasonic_laundry.LaundryApi.async_get_status"


async def test_setup_and_unload(hass: HomeAssistant, mock_entry, mock_api) -> None:
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("sensor") and hass.states.async_entity_ids("button")
    assert hass.services.has_service(DOMAIN, "reserve") and hass.services.has_service(DOMAIN, "start")
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_cloud_down_at_setup_retries(hass: HomeAssistant, mock_entry) -> None:
    mock_entry.add_to_hass(hass)
    with patch(GET_STATUS, AsyncMock(side_effect=LaundryApiError("down"))):
        await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_expired_login_starts_reauth(hass: HomeAssistant, mock_entry) -> None:
    mock_entry.add_to_hass(hass)
    with patch(GET_STATUS, AsyncMock(side_effect=LaundryAuthError("expired", invalid_grant=True))):
        await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_missing_time_zone_data_fails_setup_cleanly(hass: HomeAssistant, mock_entry, mock_api) -> None:
    mock_entry.add_to_hass(hass)
    with patch("custom_components.panasonic_laundry.dt_util.async_get_time_zone", AsyncMock(return_value=None)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_time_zone_is_resolved_once_not_per_request(hass: HomeAssistant, mock_entry) -> None:
    """The reviewer's point: no ZoneInfo(...) per request. The zone object handed to LaundryApi is reused for every call."""
    from custom_components.panasonic_laundry.api import LaundryApi

    mock_entry.add_to_hass(hass)
    lookups = AsyncMock(wraps=__import__("homeassistant.util.dt", fromlist=["dt"]).async_get_time_zone)
    with patch("custom_components.panasonic_laundry.dt_util.async_get_time_zone", lookups), patch(GET_STATUS, AsyncMock(return_value={})):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        api: LaundryApi = mock_entry.runtime_data.api
        zone = api._time_zone
        for _ in range(3):
            assert api._time_zone is zone
    assert lookups.await_count == 1


async def test_reserve_with_an_unknown_course_is_refused(hass: HomeAssistant, mock_entry, mock_api) -> None:
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "reserve", {"course": "no such course", "finish_time": "07:00:00"}, blocking=True)
    mock_api["control"].assert_not_awaited()


async def test_diagnostics_redact_secrets(hass: HomeAssistant, mock_entry, mock_api) -> None:
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, mock_entry)
    text = str(diag)
    for secret in ("fake-access-token", "fake-refresh-token", "FAKE-APPLIANCE-0001", "Fake washer"):
        assert secret not in text
    assert diag["entry"]["data"]["access_token"] == "**REDACTED**"
    assert "status" in diag
