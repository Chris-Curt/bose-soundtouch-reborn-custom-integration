"""Smoke tests for ST-Reborn status parsing without Home Assistant runtime."""
import base64
import importlib.util
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'custom_components' / 'str_reborn' / 'playback.py'
spec = importlib.util.spec_from_file_location('str_reborn_playback_under_test', MODULE)
playback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(playback)


class PlaybackParsingTest(unittest.TestCase):
    def test_standby(self):
        xml = '<nowPlaying source="STANDBY"><ContentItem source="STANDBY" /></nowPlaying>'
        status = playback.parse_now_playing(xml)
        self.assertEqual(playback.resolve_station({'status': status}), (None, None))

    def test_seventh_preset_resolves_stored_name(self):
        info = {"streamUrl": "http://127.0.0.1:8888/stream/7"}
        encoded = base64.urlsafe_b64encode(json.dumps(info).encode()).decode().rstrip('=')
        xml = f'<nowPlaying source="LOCAL_INTERNET_RADIO"><ContentItem location="/station?data={encoded}"><itemName>Live label</itemName></ContentItem><stationName>Live label</stationName><playStatus>PLAY_STATE</playStatus></nowPlaying>'
        status = playback.parse_now_playing(xml)
        self.assertEqual(playback.resolve_station({
            'status':status,
            'presets':[{'slot':7,'name':'Schlagerparadies'}]
        }), ('Schlagerparadies', 7))

    def test_exact_name_fallback(self):
        status = {'source':'LOCAL_INTERNET_RADIO','stationName':'Radio Paloma - Partyschlager'}
        self.assertEqual(playback.resolve_station({'status':status,'presets':[{'slot':1,'name':'Radio Paloma - Partyschlager'}]}), ('Radio Paloma - Partyschlager', 1))

    def test_malformed_xml_rejected(self):
        with self.assertRaises(ValueError):
            playback.parse_now_playing('<nowPlaying>')


if __name__ == '__main__':
    unittest.main()
