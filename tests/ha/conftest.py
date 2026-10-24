"""Fixtures for the tests that run inside Home Assistant. All data below is obviously fake."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fakes import APPLIANCE_ID
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.panasonic_laundry.const import (
    CONF_ACCESS_TOKEN,
    CONF_APPLIANCE_ID,
    CONF_EXPIRES_AT,
    CONF_NICKNAME,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/ of this repository."""
    return


@pytest.fixture
def entry_data() -> dict:
    return {
        CONF_ACCESS_TOKEN: "fake-access-token",
        CONF_REFRESH_TOKEN: "fake-refresh-token",
        CONF_EXPIRES_AT: 4102444800.0,          # year 2100: never refreshed during a test
        CONF_APPLIANCE_ID: APPLIANCE_ID,
        CONF_NICKNAME: "Fake washer (NA-FAKE)",
    }


@pytest.fixture
def mock_entry(entry_data) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=APPLIANCE_ID, title="Fake washer (NA-FAKE)")


@pytest.fixture
def status() -> dict[str, str]:
    """A washer that is on, idle, door closed, remote operation permitted, no reservation."""
    return {"0080": "30", "0088": "42", "00B0": "42", "0100": "01", "0090": "42", "00D0": "A1", "00E2": "00"}


@pytest.fixture
def mock_api(status):
    """Replaces the cloud calls of LaundryApi; nothing here touches the network."""
    with patch("custom_components.panasonic_laundry.LaundryApi.async_get_status", AsyncMock(return_value=status)) as get_status, patch(
        "custom_components.panasonic_laundry.LaundryApi.async_control", AsyncMock()
    ) as control:
        yield {"get_status": get_status, "control": control}
