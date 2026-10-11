"""Base entity for Smart Oil Gauge tanks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BASE_URL
from .const import DOMAIN
from .coordinator import SmartOilCoordinator


class SmartOilEntity(CoordinatorEntity[SmartOilCoordinator]):
    """One value for one tank; each tank is a device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmartOilCoordinator, tank_id: str,
                 description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.tank_id = tank_id
        self._attr_unique_id = f"{tank_id}_{description.key}"
        tank = coordinator.tanks[tank_id]
        sensors = tank.get("sensors") or []
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tank_id)},
            name=tank.get("tank_name") or f"Oil Tank {tank_id}",
            manufacturer="Connected Consumer Fuel",
            model="Smart Oil Gauge" if sensors else "Virtual Smart Oil Gauge",
            serial_number=str(sensors[0]["sensor_id"]) if sensors and sensors[0].get("sensor_id") else None,
            configuration_url=str((BASE_URL / "app.php").with_query(tid=tank_id)),
        )

    @property
    def available(self) -> bool:
        return super().available and self.tank_id in self.coordinator.data

    @property
    def value(self) -> Any:
        return self.coordinator.data[self.tank_id].get(self.entity_description.key)


def add_tank_entities(coordinator: SmartOilCoordinator,
                      add_entities: Callable[[list], None],
                      make: Callable[[str], list]) -> None:
    """Add entities for every tank now, and for tanks added to the account later."""
    known: set[str] = set()

    @callback
    def _add_new_tanks() -> None:
        new = [tank_id for tank_id in coordinator.data if tank_id not in known]
        if new:
            known.update(new)
            add_entities([entity for tank_id in new for entity in make(tank_id)])

    _add_new_tanks()
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_add_new_tanks))
