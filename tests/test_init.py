"""Setting up the integration and the entities it creates."""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartoil_gauge.api import (
    SmartOilAuthError,
    SmartOilClient,
    SmartOilConnectionError,
)
from custom_components.smartoil_gauge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import NOW_ISO, load


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(domain=DOMAIN, unique_id="kevin", title="kevin",
                            data={CONF_USERNAME: "kevin", CONF_PASSWORD: "right"})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def site():
    with (
        patch.object(SmartOilClient, "get_tanks",
                     AsyncMock(return_value=load("tanks_list.json")["tanks"])) as tanks,
        patch.object(SmartOilClient, "get_graph_data",
                     AsyncMock(return_value=load("graph_data.json"))) as graph,
        patch.object(SmartOilClient, "session_cookie", new_callable=PropertyMock,
                     return_value="sid1"),
    ):
        yield tanks, graph


async def test_entities(hass: HomeAssistant, entry, site, freezer, hass_storage) -> None:
    freezer.move_to(NOW_ISO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    expected = {
        "sensor.my_tank_gallons": "68.84",
        "sensor.my_tank_level": "25.0",
        "sensor.my_tank_usage_rate": "1.42",
        "sensor.my_tank_days_to_low_level": "0.1",
        "sensor.my_tank_days_to_1_8_tank": "24.3",
        "sensor.my_tank_days_to_empty": "48.5",
        "sensor.my_tank_gallons_to_fill": "182.2",
        "sensor.my_tank_used_today": "-1.77",
        "sensor.my_tank_average_use_today": "-4.8",
        "sensor.my_tank_average_use_last_7_days": "1.4",
        "sensor.my_tank_average_use_last_30_days": "0.8",
        "sensor.my_tank_average_use_last_365_days": "1.9",
        "sensor.my_tank_used_last_7_days": "10.29",
        "sensor.my_tank_used_last_30_days": "24.26",
        "sensor.my_tank_used_last_365_days": "693.46",
        "sensor.my_tank_last_fill": "2026-03-26T05:04:35+00:00",
        "sensor.my_tank_last_fill_amount": "149.8",
        "sensor.my_tank_temperature": "71.2",
        "sensor.my_tank_last_reading": "2026-10-11T13:09:13+00:00",
        "sensor.my_tank_battery": "Good",
        "sensor.my_tank_sensor_status": "Active",
        "sensor.my_tank_capacity": "275.0",
        "sensor.my_tank_fillable_capacity": "251.0",
        "sensor.my_tank_low_level_alert": "25.0",
        "binary_sensor.my_tank_low_level": "off",
        "binary_sensor.my_tank_sensor_offline": "off",
    }
    actual = {entity_id: hass.states.get(entity_id).state if hass.states.get(entity_id) else None
              for entity_id in expected}
    assert actual == expected
    assert hass.states.get("sensor.my_tank_gallons").attributes["unit_of_measurement"] == "gal"
    assert hass.states.get("sensor.my_tank_temperature").attributes["unit_of_measurement"] == "°F"

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, "1001"), entry.entry_id)
    assert device.name == "My Tank"
    assert device.serial_number == "3001"
    # The login cookie is saved for the next start.
    assert hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"] == {"session": "sid1"}

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_saved_cookie_is_reused(hass: HomeAssistant, entry, site, hass_storage) -> None:
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {"session": "saved"},
    }
    with patch.object(SmartOilClient, "restore_session") as restore:
        assert await hass.config_entries.async_setup(entry.entry_id)
    restore.assert_called_once_with("saved")


async def test_history_failure_keeps_level(hass: HomeAssistant, entry, site) -> None:
    site[1].side_effect = SmartOilConnectionError("timeout")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.my_tank_gallons").state == "68.84"
    assert hass.states.get("sensor.my_tank_used_last_7_days").state == "unknown"


async def test_rejected_login_starts_reauth(hass: HomeAssistant, entry, site) -> None:
    site[0].side_effect = SmartOilAuthError("Invalid username or password.")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_site_down_retries(hass: HomeAssistant, entry, site) -> None:
    site[0].side_effect = SmartOilConnectionError("timeout")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics_redact(hass: HomeAssistant, entry, site) -> None:
    from custom_components.smartoil_gauge.diagnostics import async_get_config_entry_diagnostics

    assert await hass.config_entries.async_setup(entry.entry_id)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "right" not in text
    assert diag["entry"]["data"][CONF_USERNAME] == "**REDACTED**"
    assert diag["tanks"]["1001"]["zip_code"] == "**REDACTED**"
    assert diag["values"]["1001"]["gallons"] == 68.84
