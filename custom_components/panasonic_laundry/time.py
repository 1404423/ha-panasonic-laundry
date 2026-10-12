"""Time: the time of day the reserved run should be finished."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LaundryCoordinator
from .entity import LaundryEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([ReservationFinishTime(entry.runtime_data, entry)])


class ReservationFinishTime(LaundryEntity, TimeEntity, RestoreEntity):
    _attr_translation_key = "reservation_finish_time"

    def __init__(self, coordinator: LaundryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "reservation_finish_time")

    @property
    def native_value(self) -> time:
        return self.coordinator.reservation_time

    async def async_set_value(self, value: time) -> None:
        self.coordinator.reservation_time = value.replace(second=0, microsecond=0)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            try:
                self.coordinator.reservation_time = time.fromisoformat(last.state)
            except ValueError:
                pass
