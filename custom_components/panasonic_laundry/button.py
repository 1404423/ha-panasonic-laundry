"""Buttons: reserve with the chosen course and finish time, cancel the reservation, start the selected course now."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import LaundryCoordinator
from .const import DOMAIN
from .entity import LaundryEntity
from .reservation import next_occurrence


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([ReserveButton(coordinator, entry), CancelReservationButton(coordinator, entry), StartButton(coordinator, entry)])


class ReserveButton(LaundryEntity, ButtonEntity):
    _attr_translation_key = "reserve"

    def __init__(self, coordinator: LaundryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "reserve")

    async def async_press(self) -> None:
        coordinator = self.coordinator
        code = coordinator.effective_course()
        if code is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="course_not_in_history")
        await coordinator.async_reserve(code, next_occurrence(coordinator.reservation_time, dt_util.now()))


class CancelReservationButton(LaundryEntity, ButtonEntity):
    _attr_translation_key = "cancel_reservation"

    def __init__(self, coordinator: LaundryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "cancel_reservation")

    async def async_press(self) -> None:
        await self.coordinator.async_cancel_reservation()


class StartButton(LaundryEntity, ButtonEntity):
    """Starts the course that is selected on the washer. The washer's own 遠隔 (remote) lamp has to be lit, which is the
    physical safety gate; the drum must be loaded (or empty for a tank course) by a person."""

    _attr_translation_key = "start"

    def __init__(self, coordinator: LaundryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "start")

    async def async_press(self) -> None:
        await self.coordinator.async_start()
