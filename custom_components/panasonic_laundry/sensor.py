"""Sensors: state, door, course, stage, time remaining, reservation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .decode import (
    decode_course_text,
    decode_door,
    decode_progress_text,
    decode_remaining,
    decode_reservation,
    decode_reserve_start_minutes,
    decode_state,
)
from .entity import LaundryEntity


@dataclass(frozen=True, kw_only=True)
class LaundrySensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, str]], Any]
    attrs_fn: Callable[[dict[str, str]], dict[str, Any]] | None = None


# The order here is the order of the entities on the device page (it follows the order of creation).
SENSORS: tuple[LaundrySensorDescription, ...] = (
    LaundrySensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "waiting", "running", "paused", "done", "error"],
        value_fn=decode_state,
    ),
    LaundrySensorDescription(
        key="door",
        translation_key="door",
        device_class=SensorDeviceClass.ENUM,
        options=["open", "closed"],
        value_fn=decode_door,
    ),
    LaundrySensorDescription(key="course", translation_key="course", value_fn=decode_course_text),
    # 工程: the finer of the two status properties (0121 'driving situation': washing / rinsing / spinning / drying /
    # unwinding / nanoe / reservation wait ...). The coarser 00E2 'transition state' only repeated this while running;
    # its end-of-run kinds are covered by the 状態 sensor.
    LaundrySensorDescription(key="stage", translation_key="stage", value_fn=decode_progress_text),
    LaundrySensorDescription(
        key="remaining",
        translation_key="remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=decode_remaining,
    ),
    LaundrySensorDescription(
        key="reservation",
        translation_key="reservation",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "reserved"],
        value_fn=decode_reservation,
    ),
    LaundrySensorDescription(
        key="reservation_start_in",
        translation_key="reservation_start_in",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=decode_reserve_start_minutes,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(LaundrySensor(coordinator, entry, d) for d in SENSORS)


class LaundrySensor(LaundryEntity, SensorEntity):
    entity_description: LaundrySensorDescription

    def __init__(self, coordinator, entry: ConfigEntry, description: LaundrySensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None
