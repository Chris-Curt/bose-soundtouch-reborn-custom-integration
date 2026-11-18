"""Small, local-only HTTP client for the SoundTouch Reborn control API."""
from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .playback import parse_now_playing


class STRApiError(Exception):
    """Device or protocol error."""


class STRClient:
    def __init__(self, session: ClientSession, host: str, port: int) -> None:
        self.session = session
        self.host = host
        self.port = port
        self.base = f"http://{host}:{port}"
        self._command_lock = asyncio.Lock()

    async def request(self, method: str, path: str, body: Any = None) -> Any:
        try:
            async with self.session.request(
                method, self.base + path, json=body if body is not None else None,
                timeout=ClientTimeout(total=8),
                allow_redirects=False,
            ) as response:
                if response.status >= 400:
                    detail = (await response.text())[:200]
                    raise STRApiError(f"{method} {path}: HTTP {response.status} {detail}")
                if response.content_type == "application/json" or response.content_type.endswith("+json"):
                    return await response.json()
                raw = await response.text()
                if path == "/api/status" and raw.lstrip().startswith("<"):
                    try:
                        return parse_now_playing(raw)
                    except ValueError as exc:
                        raise STRApiError("Invalid Bose nowPlaying XML") from exc
                if not raw.strip():
                    return {}
                raise STRApiError(f"Unexpected non-JSON response for {path}")
        except (TimeoutError, ClientError) as exc:
            raise STRApiError(f"Cannot reach {self.base}: {exc}") from exc

    async def version(self) -> dict:
        result = await self.request("GET", "/api/agent/version")
        if not isinstance(result, dict) or not result.get("version"):
            raise STRApiError("Device did not return a valid ST-Reborn version")
        return result

    async def snapshot(self) -> dict:
        # Version probe acts as protocol validation; optional endpoints can fail independently.
        version = await self.version()
        async def attempt(path: str):
            try:
                return await self.request("GET", path)
            except STRApiError:
                return None
        status, volume, presets, title = await asyncio.gather(
            attempt("/api/status"), attempt("/api/box/volume"),
            attempt("/api/presets"), attempt("/api/stream/title")
        )
        return {"version": version, "status": status or {}, "volume": volume or {},
                "presets": presets or [], "stream_title": title or {}}

    async def command(self, method: str, path: str, body: Any = None) -> Any:
        async with self._command_lock:
            return await self.request(method, path, body)

    async def set_power(self, on: bool) -> None:
        await self.command("POST", "/api/box/power", {"on": on})

    async def set_volume(self, value: int) -> None:
        await self.command("PUT", "/api/box/volume", {"value": max(0, min(100, value))})

    async def play_preset(self, slot: int) -> None:
        if not 1 <= slot <= 12:
            raise ValueError("Preset must be 1 through 12")
        await self.command("POST", f"/api/play/{slot}")

    async def announce(self, *, text: str | None = None, url: str | None = None,
                       lang: str = "de", volume: int | None = None) -> None:
        if bool(text) == bool(url):
            raise ValueError("Specify either text or URL")
        body: dict[str, Any] = {"text": text} if text else {"url": url}
        if text:
            body["lang"] = lang
        if volume is not None:
            body["volume"] = max(0, min(100, volume))
        await self.command("POST", "/api/announce", body)
