"""Bose nowPlaying XML decoder and STR preset-name resolution.

This module has no Home Assistant imports so that the parser can be unit-tested.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET


def parse_now_playing(xml: str) -> dict:
    """Convert the XML returned by GET /api/status to a small dictionary."""
    if len(xml) > 32768:
        raise ValueError("nowPlaying XML too large")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError("Invalid nowPlaying XML") from exc
    if root.tag.rsplit("}", 1)[-1] != "nowPlaying":
        raise ValueError("Unexpected XML root element")
    data = dict(root.attrib)
    for child in root:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "ContentItem":
            item = dict(child.attrib)
            for sub in child:
                item[sub.tag.rsplit("}", 1)[-1]] = (sub.text or "").strip()
            data["content_item"] = item
        else:
            data[tag] = (child.text or "").strip()
    return data


def preset_entries(value) -> list[dict]:
    """Normalize the API's list of saved presets."""
    if isinstance(value, dict):
        value = value.get("presets", value.get("slots", []))
    if not isinstance(value, list):
        return []
    result = []
    for idx, record in enumerate(value, start=1):
        if not isinstance(record, dict):
            continue
        try:
            slot = int(record.get("slot", idx))
        except (ValueError, TypeError):
            continue
        if 1 <= slot <= 12 and isinstance(record.get("name"), str):
            result.append({**record, "slot": slot})
    return result


def _slot_in_stream_url(url: str) -> int | None:
    """Recognize local STR slot paths, never infer from arbitrary integers."""
    if not isinstance(url, str) or not url:
        return None
    path = urlsplit(url).path
    match = re.fullmatch(r"/stream/(\d{1,2})", path)
    if not match:
        match = re.fullmatch(r"/spotify/stream-(\d{1,2})\.ogg", path)
    if match:
        slot = int(match.group(1))
        if 1 <= slot <= 12:
            return slot
    return None


def _preset_slot_from_location(location: str) -> int | None:
    """Decode the native radio descriptor's locally proxied stream slot."""
    direct = _slot_in_stream_url(location)
    if direct:
        return direct
    if not isinstance(location, str) or not location.startswith("/station?"):
        return None
    encoded = parse_qs(urlsplit(location).query).get("data", [""])[0]
    if not encoded or len(encoded) > 4096:
        return None
    try:
        descriptor = json.loads(base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        ))
        if isinstance(descriptor, dict):
            return _slot_in_stream_url(descriptor.get("streamUrl", ""))
    except (ValueError, TypeError, binascii.Error):
        return None
    return None


def resolve_station(snapshot: dict) -> tuple[str | None, int | None]:
    """Return the SAVED preset name and its slot when the speaker uses one.

    If no slot is identifiable, use an exact unique match of the firmware's
    itemName/stationName against the saved names. If this is ordinary radio
    playback unrelated to a saved preset, report its live station name.
    """
    status = snapshot.get("status") or {}
    if not isinstance(status, dict):
        return None, None
    source = str(status.get("source") or "").upper()
    if source in ("STANDBY", "AUX", "BLUETOOTH", "INVALID_SOURCE"):
        return None, None
    presets = preset_entries(snapshot.get("presets"))
    item = status.get("content_item") or {}
    if not isinstance(item, dict):
        item = {}
    slot = _preset_slot_from_location(item.get("location", ""))
    if slot is not None:
        match = next((p for p in presets if p["slot"] == slot), None)
        if match:
            return match["name"], slot

    candidates = [item.get("itemName"), status.get("stationName")]
    for name in candidates:
        if not isinstance(name, str) or not name.strip():
            continue
        matching = [p for p in presets
                    if " ".join(p["name"].split()).casefold()
                    == " ".join(name.split()).casefold()]
        if len(matching) == 1:
            return matching[0]["name"], matching[0]["slot"]
        if matching:
            return matching[0]["name"], None

    if source in ("LOCAL_INTERNET_RADIO", "INTERNET_RADIO"):
        live_name = status.get("stationName") or item.get("itemName")
        if isinstance(live_name, str) and live_name.strip():
            return live_name.strip(), None
    return None, None
