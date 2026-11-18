"""Media player with volume, playback and preset support."""
from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState, MediaType
from homeassistant.exceptions import HomeAssistantError
from .api import STRApiError
from .entity import STREntity
from .playback import resolve_station


class STRMediaPlayer(STREntity, MediaPlayerEntity):
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF |
        MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_STEP |
        MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE |
        MediaPlayerEntityFeature.STOP | MediaPlayerEntityFeature.PLAY_MEDIA |
        MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator):
        super().__init__(coordinator, "player")
        self._attr_unique_id = f"{coordinator.entry.entry_id}_player"

    @property
    def state(self):
        status = self.coordinator.data.get("status", {})
        # ST-Reborn status schema is not fully described in the supplied document;
        # restrict mapping to identifiable explicit state fields.
        raw = str(status.get("playStatus") or status.get("playState") or status.get("play_state") or status.get("state") or "").upper()
        if status.get("source") == "STANDBY":
            return MediaPlayerState.OFF
        if "PAUS" in raw:
            return MediaPlayerState.PAUSED
        if "PLAY" in raw or "BUFFER" in raw:
            return MediaPlayerState.PLAYING
        if "STANDBY" in raw or raw == "OFF":
            return MediaPlayerState.OFF
        return MediaPlayerState.IDLE

    @property
    def volume_level(self):
        value = self.coordinator.data.get("volume", {}).get("value")
        return value / 100 if isinstance(value, (int, float)) else None

    @property
    def is_volume_muted(self):
        return bool(self.coordinator.data.get("volume", {}).get("muted", False))

    @property
    def media_title(self):
        s = self.coordinator.data.get("status", {})
        if s.get("source") == "STANDBY":
            return None
        title = self.coordinator.data.get("stream_title", {}).get("title")
        return title or s.get("track") or s.get("title") or s.get("itemName")

    @property
    def media_channel(self):
        station, _slot = resolve_station(self.coordinator.data)
        return station

    @property
    def source_list(self):
        p = self.coordinator.data.get("presets", [])
        return [f"{i}: {name}" for i, name in self._presets(p)]

    @staticmethod
    def _presets(presets):
        if isinstance(presets, dict):
            presets = presets.get("presets", presets.get("slots", []))
        if not isinstance(presets, list):
            return []
        result = []
        for idx, p in enumerate(presets, 1):
            if not isinstance(p, dict):
                continue
            slot = p.get("slot", idx)
            if isinstance(slot, int) and 1 <= slot <= 12:
                name = p.get("name") or p.get("title") or f"Preset {slot}"
                result.append((slot, str(name)))
        return sorted(result)

    @property
    def extra_state_attributes(self):
        return {"presets": dict(self._presets(self.coordinator.data.get("presets", []))),
                "agent_version": self.coordinator.data.get("version", {}).get("version"),
                "preset_rows": self.coordinator.data.get("version", {}).get("presetRows", "1")}

    async def _execute(self, method, path, body=None):
        try:
            await self.coordinator.client.command(method, path, body)
        except STRApiError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self):
        await self._execute("POST", "/api/box/power", {"on": True})

    async def async_turn_off(self):
        await self._execute("POST", "/api/box/power", {"on": False})

    async def async_set_volume_level(self, volume):
        await self._execute("PUT", "/api/box/volume", {"value": round(max(0, min(1, volume)) * 100)})

    async def async_volume_up(self):
        await self.async_set_volume_level(min(1.0, (self.volume_level or 0) + 0.05))

    async def async_volume_down(self):
        await self.async_set_volume_level(max(0.0, (self.volume_level or 0) - 0.05))

    async def async_media_play(self):
        await self._execute("POST", "/api/resume")

    async def async_media_pause(self):
        await self._execute("POST", "/api/pause")

    async def async_media_stop(self):
        await self._execute("POST", "/api/stop")

    async def async_select_source(self, source):
        try:
            slot = int(source.split(":", 1)[0])
        except (ValueError, AttributeError) as exc:
            raise HomeAssistantError("Invalid preset source") from exc
        if not 1 <= slot <= 12:
            raise HomeAssistantError("Preset outside 1-12")
        await self._execute("POST", f"/api/play/{slot}")

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_type == "preset":
            try:
                slot = int(media_id)
            except (TypeError, ValueError) as exc:
                raise HomeAssistantError("Preset must be a number") from exc
            if not 1 <= slot <= 12:
                raise HomeAssistantError("Preset outside 1-12")
            await self._execute("POST", f"/api/play/{slot}")
        elif media_type in (MediaType.URL, "url") and str(media_id).startswith(("http://", "https://")):
            await self._execute("POST", "/api/play", {"url": media_id})
        else:
            raise HomeAssistantError("Supported media: preset 1-12 or HTTP(S) URL")


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([STRMediaPlayer(hass.data["str_reborn"][entry.entry_id])])
