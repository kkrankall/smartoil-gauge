"""Sensors for Smart Oil Gauge tanks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SmartOilConfigEntry
from .entity import SmartOilEntity, add_tank_entities

GALLONS_PER_DAY = "gal/d"

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="gallons",
        translation_key="gallons",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="level",
        translation_key="level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="usage_rate",
        translation_key="usage_rate",
        native_unit_of_measurement=GALLONS_PER_DAY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="days_to_low",
        translation_key="days_to_low",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="days_to_eighth",
        translation_key="days_to_eighth",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="days_to_empty",
        translation_key="days_to_empty",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="gallons_to_fill",
        translation_key="gallons_to_fill",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    *(
        SensorEntityDescription(
            key=f"used_{days}",
            translation_key=f"used_{days}",
            native_unit_of_measurement=UnitOfVolume.GALLONS,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        )
        for days in ("today", "7_days", "30_days", "365_days")
    ),
    *(
        SensorEntityDescription(
            key=f"average_use_{days}",
            translation_key=f"average_use_{days}",
            native_unit_of_measurement=GALLONS_PER_DAY,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        )
        for days in ("today", "7_days", "30_days", "365_days")
    ),
    SensorEntityDescription(
        key="last_fill",
        translation_key="last_fill",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="last_fill_amount",
        translation_key="last_fill_amount",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="last_reading",
        translation_key="last_reading",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="battery",
        translation_key="battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="sensor_status",
        translation_key="sensor_status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="fillable_capacity",
        translation_key="fillable_capacity",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="low_level_alert",
        translation_key="low_level_alert",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: SmartOilConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add_tank_entities(coordinator, async_add_entities, lambda tank_id: [
        SmartOilSensor(coordinator, tank_id, description) for description in SENSORS
    ])


class SmartOilSensor(SmartOilEntity, SensorEntity):
    """A tank reading or estimate."""

    # The site's level history is for charts (apexcharts-card's
    # data_generator); it is too big and too redundant to record.
    _unrecorded_attributes = frozenset({"history"})

    @property
    def native_value(self) -> float | str | datetime | None:
        return self.value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "gallons":
            return None
        return {"history": self.coordinator.data[self.tank_id].get("level_history") or []}
