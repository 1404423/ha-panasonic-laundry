"""Shared base entity."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LaundryCoordinator
from .const import CONF_NICKNAME, DOMAIN


class LaundryEntity(CoordinatorEntity[LaundryCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: LaundryCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.appliance_id}_{key}"
        self._attr_suggested_object_id = f"drum_washer_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.appliance_id)},
            name=entry.data.get(CONF_NICKNAME) or "洗濯乾燥機",
            manufacturer="Panasonic",
        )
