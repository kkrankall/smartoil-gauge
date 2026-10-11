"""Config flow for Smart Oil Gauge."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SmartOilAuthError, SmartOilClient, SmartOilConnectionError
from .const import DOMAIN, LOGGER

PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password"))
USER_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): TextSelector(TextSelectorConfig(autocomplete="username")),
    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
})
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR})


class SmartOilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in to a Smart Oil Gauge account."""

    VERSION = 1

    async def _async_validate(self, username: str, password: str) -> str | None:
        """Try the login; return an error key, or None if it worked."""
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        try:
            client = SmartOilClient(session, username, password)
            await client.login()
            if not await client.get_tanks():
                return "no_tanks"
        except SmartOilAuthError:
            return "invalid_auth"
        except SmartOilConnectionError:
            LOGGER.debug("Smart Oil Gauge unreachable during setup", exc_info=True)
            return "cannot_connect"
        except Exception:
            LOGGER.exception("Unexpected error logging in to Smart Oil Gauge")
            return "unknown"
        finally:
            session.detach()
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            if not (error := await self._async_validate(username, user_input[CONF_PASSWORD])):
                return self.async_create_entry(title=username, data={
                    CONF_USERNAME: username,
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                })
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_validate(entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
            if not error:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]})
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
