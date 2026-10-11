"""Binary sensors for Smart Oil Gauge tanks."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SmartOilConfigEntry
from .entity import SmartOilEntity, add_tank_entities

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    # On when the level is below the low-level alert set on the website.
    BinarySensorEntityDescription(
        key="low_level",
        translation_key="low_level",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    # On after 96 h without a reading, when the website flags the gauge offline.
    BinarySensorEntityDescription(
        key="sensor_offline",
        translation_key="sensor_offline",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: SmartOilConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add_tank_entities(coordinator, async_add_entities, lambda tank_id: [
        SmartOilBinarySensor(coordinator, tank_id, description) for description in BINARY_SENSORS
    ])


class SmartOilBinarySensor(SmartOilEntity, BinarySensorEntity):
    """A tank alert."""

    @property
    def is_on(self) -> bool | None:
        return self.value
