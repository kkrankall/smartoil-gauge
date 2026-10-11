"""Polls Smart Oil Gauge for every tank on the account."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmartOilAuthError, SmartOilClient, SmartOilError
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL
from .parse import parse_tank

type SmartOilConfigEntry = ConfigEntry[SmartOilCoordinator]


class SmartOilCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetches the tank list and each tank's history; data is keyed by tank id."""

    config_entry: SmartOilConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SmartOilConfigEntry,
                 client: SmartOilClient) -> None:
        super().__init__(hass, LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=UPDATE_INTERVAL)
        self.client = client
        # Raw tank-list entries, for device info and diagnostics.
        self.tanks: dict[str, dict[str, Any]] = {}
        # The login cookie is kept across restarts so HA doesn't send the
        # password every time it starts.
        self._store: Store[dict[str, str]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._saved_cookie: str | None = None

    async def _async_setup(self) -> None:
        saved = await self._store.async_load() or {}
        if saved.get("session"):
            self._saved_cookie = saved["session"]
            self.client.restore_session(saved["session"])

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            tanks = await self.client.get_tanks()
            graphs: dict[str, dict[str, Any] | None] = {}
            for tank in tanks:
                tank_id = str(tank["tank_id"])
                try:
                    graphs[tank_id] = await self.client.get_graph_data(tank)
                except SmartOilAuthError:
                    raise
                except SmartOilError as err:
                    # Level and usage still update; the history sensors go unknown.
                    LOGGER.warning("Tank %s: usage history unavailable (%s)", tank_id, err)
                    graphs[tank_id] = None
        except SmartOilAuthError as err:
            raise ConfigEntryAuthFailed(f"Smart Oil Gauge rejected the login: {err}") from err
        except SmartOilError as err:
            raise UpdateFailed(str(err)) from err

        cookie = self.client.session_cookie
        if cookie and cookie != self._saved_cookie:
            await self._store.async_save({"session": cookie})
            self._saved_cookie = cookie

        now = time.time()
        self.tanks = {str(tank["tank_id"]): tank for tank in tanks}
        return {tank_id: parse_tank(tank, graphs.get(tank_id), now)
                for tank_id, tank in self.tanks.items()}
