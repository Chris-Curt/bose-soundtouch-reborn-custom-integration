"""Shared entity metadata."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class STREntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, suffix: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{suffix}"

    @property
    def device_info(self):
        v = self.coordinator.data.get("version", {})
        return {
            "identifiers": {("str_reborn", self.coordinator.entry.entry_id)},
            "name": v.get("friendlyName") or self.coordinator.entry.title,
            "manufacturer": "Bose / ST-Reborn",
            "model": v.get("model") or "SoundTouch",
            "sw_version": v.get("version"),
        }
