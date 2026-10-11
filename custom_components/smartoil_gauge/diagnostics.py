"""Diagnostics for Smart Oil Gauge."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SmartOilConfigEntry

# "buy" holds the fuel dealer's order link, which carries a token.
TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "title", "unique_id", "zip_code",
             "sensor_id", "buy"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SmartOilConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "tanks": async_redact_data(coordinator.tanks, TO_REDACT),
        "values": coordinator.data,
    }
