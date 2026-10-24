"""Config flow: login paste, device choice, error keys, duplicates and re-authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.panasonic_laundry.api import LaundryApiError
from custom_components.panasonic_laundry.auth import LaundryAuthError
from custom_components.panasonic_laundry.config_flow import LOGIN_FIELD
from custom_components.panasonic_laundry.const import CONF_APPLIANCE_ID, DOMAIN

from fakes import APPLIANCE_ID, FAKE_CODE

TOKENS = {"access_token": "fake-access", "refresh_token": "fake-refresh", "expires_in": 3600}
DEVICES = [{"appliance_id": APPLIANCE_ID, "nickname": "Fake washer", "product_code": "NA-FAKE"}]
EXCHANGE = "custom_components.panasonic_laundry.config_flow.async_exchange_code"
DEVICES_CALL = "custom_components.panasonic_laundry.config_flow.LaundryApi.async_get_devices"


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    assert "authorize_url" in result["description_placeholders"]
    return result


async def test_full_flow(hass: HomeAssistant, mock_api) -> None:
    result = await _start(hass)
    with patch(EXCHANGE, AsyncMock(return_value=TOKENS)), patch(DEVICES_CALL, AsyncMock(return_value=DEVICES)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "device"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_APPLIANCE_ID: APPLIANCE_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["access_token"] == "fake-access" and result["data"][CONF_APPLIANCE_ID] == APPLIANCE_ID
    assert result["result"].unique_id == APPLIANCE_ID


async def test_errors_are_shown_and_recoverable(hass: HomeAssistant) -> None:
    for exc, key in ((LaundryAuthError("bad"), "invalid_auth"), (LaundryApiError("down"), "cannot_connect")):
        result = await _start(hass)
        with patch(EXCHANGE, AsyncMock(side_effect=exc)):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
        assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": key}
    # recover on the same form
    with patch(EXCHANGE, AsyncMock(return_value=TOKENS)), patch(DEVICES_CALL, AsyncMock(return_value=DEVICES)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
    assert result["step_id"] == "device"


async def test_no_devices(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(EXCHANGE, AsyncMock(return_value=TOKENS)), patch(DEVICES_CALL, AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
    assert result["errors"] == {"base": "no_devices"}


async def test_state_mismatch(hass: HomeAssistant) -> None:
    result = await _start(hass)
    link = f"auth0://auth.digital.panasonic.com/android/com.panasonic.SmartLaundry/callback?code={FAKE_CODE}&state=not-this-dialog"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: link})
    assert result["errors"] == {"base": "state_mismatch"}


async def test_missing_time_zone_data_is_an_error_not_a_crash(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(EXCHANGE, AsyncMock(return_value=TOKENS)), patch(
        "custom_components.panasonic_laundry.config_flow.dt_util.async_get_time_zone", AsyncMock(return_value=None)
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
    assert result["errors"] == {"base": "unknown"}


async def test_every_error_key_has_a_text(hass: HomeAssistant) -> None:
    """The keys the flow can return must exist in strings.json (a missing one would show as a bare key)."""
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parents[2] / "custom_components" / DOMAIN
    for name in ("strings.json", "translations/en.json", "translations/ja.json"):
        errors = json.loads((base / name).read_text())["config"]["error"]
        for key in ("invalid_auth", "cannot_connect", "no_devices", "state_mismatch", "wrong_account", "unknown"):
            assert key in errors, f"{name} lacks {key}"


async def test_duplicate_is_aborted(hass: HomeAssistant, mock_entry, mock_api) -> None:
    mock_entry.add_to_hass(hass)
    result = await _start(hass)
    with patch(EXCHANGE, AsyncMock(return_value=TOKENS)), patch(DEVICES_CALL, AsyncMock(return_value=DEVICES)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_APPLIANCE_ID: APPLIANCE_ID})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"


async def test_reauth_updates_the_tokens(hass: HomeAssistant, mock_entry, mock_api) -> None:
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reauth_confirm"
    with patch(EXCHANGE, AsyncMock(return_value={**TOKENS, "access_token": "new-access"})), patch(DEVICES_CALL, AsyncMock(return_value=DEVICES)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert mock_entry.data["access_token"] == "new-access"


async def test_reauth_with_a_foreign_account(hass: HomeAssistant, mock_entry, mock_api) -> None:
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)
    other = [{"appliance_id": "SOMEONE-ELSES", "nickname": "x", "product_code": "y"}]
    with patch(EXCHANGE, AsyncMock(return_value=TOKENS)), patch(DEVICES_CALL, AsyncMock(return_value=other)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {LOGIN_FIELD: FAKE_CODE})
    assert result["errors"] == {"base": "wrong_account"}
