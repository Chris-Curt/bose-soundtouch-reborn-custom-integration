"""Config flow for SoundTouch Reborn."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import STRApiError, STRClient
from .const import DOMAIN, DEFAULT_PORTS


class STRFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            # Hostnames are permitted, but not URLs, slashes or paths.
            if any(c in host for c in "/:@?# ") or not host:
                errors["base"] = "invalid_host"
            else:
                ports = ([user_input[CONF_PORT]] if user_input.get(CONF_PORT) else list(DEFAULT_PORTS))
                for port in ports:
                    try:
                        client = STRClient(async_get_clientsession(self.hass), host, port)
                        version = await client.version()
                        uid = f"{host.lower()}:{port}"
                        await self.async_set_unique_id(uid)
                        self._abort_if_unique_id_configured()
                        name = version.get("friendlyName") or host
                        return self.async_create_entry(title=f"STR {name}", data={CONF_HOST: host, CONF_PORT: port})
                    except STRApiError:
                        continue
                errors["base"] = "cannot_connect"
        schema = vol.Schema({vol.Required(CONF_HOST): str, vol.Optional(CONF_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
