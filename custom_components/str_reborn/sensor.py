"""Station, current title and ST-Reborn version sensors."""
from homeassistant.components.sensor import SensorEntity

from .entity import STREntity
from .playback import resolve_station


class STRSensor(STREntity, SensorEntity):
    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self):
        data = self.coordinator.data
        status = data.get("status", {})
        if self.key == "version":
            return data.get("version", {}).get("version")
        if self.key == "station":
            station, _slot = resolve_station(data)
            if station:
                # HA entity states have a maximum of 255 characters.
                return station if len(station) <= 255 else station[:252] + "..."
            if status.get("source") == "STANDBY":
                return "Standby"
            if status.get("source") in ("AUX", "BLUETOOTH"):
                return status["source"].capitalize()
            return None
        if self.key == "track":
            if status.get("source") == "STANDBY":
                return None
            value = (data.get("stream_title", {}).get("title")
                     or status.get("track") or status.get("title"))
            if isinstance(value, str):
                return value if len(value) <= 255 else value[:252] + "..."
            return None
        return None

    @property
    def extra_state_attributes(self):
        if self.key == "version":
            v = self.coordinator.data.get("version", {})
            return {"build": v.get("build"), "preset_rows": v.get("presetRows", "1")}
        if self.key == "station":
            station, slot = resolve_station(self.coordinator.data)
            return {
                "preset_slot": slot,
                "quelle": self.coordinator.data.get("status", {}).get("source"),
                "vollstaendiger_name": station if station and len(station) > 255 else None,
            }
        return {}


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data["str_reborn"][entry.entry_id]
    async_add_entities([
        STRSensor(c, "station", "Sender", "mdi:radio-tower"),
        STRSensor(c, "track", "Aktueller Titel", "mdi:music-note"),
        STRSensor(c, "version", "ST-Reborn-Version", "mdi:information-outline"),
    ])
