from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_HOST
from .api import VirginApi, VirginApiError

STEP_USER = vol.Schema({
    vol.Optional("host", default=DEFAULT_HOST): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER)

        host = user_input["host"]
        # quick connectivity check
        api = VirginApi(host, async_get_clientsession(self.hass))
        errors = {}
        try:
            await api.fetch_snapshot()
        except VirginApiError:
            errors["host"] = "cannot_connect"

        if errors:
            return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

        return self.async_create_entry(title="Virgin Modem Status", data={"host": host})

    async def async_step_import(self, user_input: dict) -> FlowResult:
        # Optional: support YAML import
        return await self.async_step_user(user_input)
