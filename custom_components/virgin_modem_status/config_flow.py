from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_SCAN_INTERVAL
from .api import VirginApi

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
        try:
            await api.get_status()
        except Exception as e:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER,
                errors={"base": "cannot_connect"},
                description_placeholders={"err": str(e)}
            )

        return self.async_create_entry(title=f"Virgin Modem ({host})", data={"host": host})

    async def async_step_import(self, data):
        return await self.async_step_user(data)

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        schema = vol.Schema({
            vol.Optional("scan_interval", default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int
        })
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=schema)
        return self.async_create_entry(title="", data=user_input)
