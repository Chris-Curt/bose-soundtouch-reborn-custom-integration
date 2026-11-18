"""Twelve preset buttons and one explicit refresh button."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from .api import STRApiError
from .entity import STREntity


class STRPresetButton(STREntity, ButtonEntity):
    def __init__(self, coordinator, slot):
        super().__init__(coordinator, f"preset_{slot}")
        self.slot = slot
        self._attr_name = f"Preset {slot}"
        self._attr_icon = "mdi:radio"

    @property
    def available(self):
        return super().available and (self.slot <= 6 or str(self.coordinator.data.get("version", {}).get("presetRows")) == "2")

    async def async_press(self):
        try:
            await self.coordinator.client.play_preset(self.slot)
        except STRApiError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()


class STRRefreshButton(STREntity, ButtonEntity):
    _attr_name = "Status aktualisieren"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator):
        super().__init__(coordinator, "refresh")

    async def async_press(self):
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["str_reborn"][entry.entry_id]
    async_add_entities([STRPresetButton(coordinator, i) for i in range(1, 13)] + [STRRefreshButton(coordinator)])
