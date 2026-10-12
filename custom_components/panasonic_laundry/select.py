"""Select: the course to reserve. Only courses from the washer's history can be chosen."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LaundryCoordinator, course_options
from .entity import LaundryEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([ReservationCourseSelect(entry.runtime_data, entry)])


class ReservationCourseSelect(LaundryEntity, SelectEntity, RestoreEntity):
    _attr_translation_key = "reservation_course"

    def __init__(self, coordinator: LaundryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "reservation_course")

    def _options(self) -> dict[str, str]:
        return course_options(self.coordinator.history())

    @property
    def options(self) -> list[str]:
        return list(self._options())

    @property
    def current_option(self) -> str | None:
        by_code = {code: name for name, code in self._options().items()}
        return by_code.get(self.coordinator.effective_course())

    async def async_select_option(self, option: str) -> None:
        self.coordinator.reservation_course = self._options()[option]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self._options():
            self.coordinator.reservation_course = self._options()[last.state]
