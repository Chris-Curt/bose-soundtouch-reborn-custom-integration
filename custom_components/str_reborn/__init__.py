"""Home Assistant integration for local SoundTouch Reborn agents."""
from __future__ import annotations

from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import config_validation as cv
from .api import STRApiError, STRClient
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.MEDIA_PLAYER, Platform.BUTTON, Platform.SENSOR]


class STRCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, client: STRClient, entry: ConfigEntry):
        super().__init__(hass, _LOGGER, name=f"STR {entry.title}", update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS))
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.snapshot()
        except STRApiError as exc:
            raise UpdateFailed(str(exc)) from exc


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def announce(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        entries = hass.data.get(DOMAIN, {})
        coordinator = entries.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError("SoundTouch Reborn entry not found")
        try:
            await coordinator.client.announce(
                text=call.data.get("text"), url=call.data.get("url"),
                lang=call.data.get("language", "de"), volume=call.data.get("volume"))
        except (STRApiError, ValueError) as exc:
            raise HomeAssistantError(str(exc)) from exc
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "announce", announce, schema=vol.Schema({
        vol.Required("entry_id"): cv.string,
        vol.Exclusive("text", "audio"): cv.string,
        vol.Exclusive("url", "audio"): cv.url,
        vol.Optional("language", default="de"): cv.string,
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = STRClient(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = STRCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
