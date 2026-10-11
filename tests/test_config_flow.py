"""The setup and re-authentication forms."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartoil_gauge.api import (
    SmartOilAuthError,
    SmartOilClient,
    SmartOilConnectionError,
)
from custom_components.smartoil_gauge.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import load


@pytest.fixture
def login():
    with (
        patch.object(SmartOilClient, "login", AsyncMock()) as login,
        patch.object(SmartOilClient, "get_tanks",
                     AsyncMock(return_value=load("tanks_list.json")["tanks"])),
        patch("custom_components.smartoil_gauge.async_setup_entry", AsyncMock(return_value=True)),
    ):
        yield login


async def test_user_flow(hass: HomeAssistant, login) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: " Kevin@Example.com ", CONF_PASSWORD: "right"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kevin@Example.com"
    assert result["data"] == {CONF_USERNAME: "Kevin@Example.com", CONF_PASSWORD: "right"}
    assert result["result"].unique_id == "kevin@example.com"


@pytest.mark.parametrize(("error", "key"), [
    (SmartOilAuthError("bad"), "invalid_auth"),
    (SmartOilConnectionError("down"), "cannot_connect"),
    (ValueError("boom"), "unknown"),
])
async def test_user_flow_errors_then_recovers(hass: HomeAssistant, login, error, key) -> None:
    login.side_effect = error
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "kevin", CONF_PASSWORD: "x"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}

    login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "kevin", CONF_PASSWORD: "right"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_no_tanks(hass: HomeAssistant, login) -> None:
    with patch.object(SmartOilClient, "get_tanks", AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "kevin", CONF_PASSWORD: "right"})
    assert result["errors"] == {"base": "no_tanks"}


async def test_already_configured(hass: HomeAssistant, login) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="kevin", data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "Kevin", CONF_PASSWORD: "right"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, login) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="kevin", title="kevin",
                            data={CONF_USERNAME: "kevin", CONF_PASSWORD: "old"})
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    login.side_effect = SmartOilAuthError("bad")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "x"})
    assert result["errors"] == {"base": "invalid_auth"}

    login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
