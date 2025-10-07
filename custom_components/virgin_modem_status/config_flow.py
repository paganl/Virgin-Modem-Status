"""Virgin Modem Status – Home Assistant custom integration."""
from __future__ import annotations
import asyncio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_HOST
from .api import VirginApi, VirginApiError

STEP_USER = vol.Schema({
    vol.Required("host", default=DEFAULT_HOST): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER)

        host = (user_input.get("host") or "").strip()
        errors: dict[str, str] = {}

        if not host:
            errors["host"] = "invalid_host"
            return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

        # Avoid duplicate entries for the same host
        await self.async_set_unique_id(f"{DOMAIN}:{host}")
        self._abort_if_unique_id_configured()

        # Quick connectivity check with a short timeout (api has its own default, but keep this snappy)
        api = VirginApi(host, async_get_clientsession(self.hass))
        try:
            # If your VirginApi supports per-call timeout, pass it; otherwise rely on default.
            await asyncio.wait_for(api.fetch_snapshot(), timeout=8)
        except asyncio.TimeoutError:
            errors["base"] = "connection_timeout"
        except VirginApiError:
            errors["base"] = "cannot_connect"
        except Exception:
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

        return self.async_create_entry(title="Virgin Modem Status", data={"host": host})

    async def async_step_import(self, user_input: dict) -> FlowResult:
        # Optional YAML import → reuse same validation
        return await self.async_step_user(user_input)
