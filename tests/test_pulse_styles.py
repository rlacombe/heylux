"""Tests for pulse styles and multi-light synchronization."""

import json
from unittest.mock import MagicMock, patch

import pytest

from fiat_lux.pulse import breathing_pulse, _get_alert_lights


@pytest.fixture
def mock_bridge():
    light1 = MagicMock()
    light1.light_id = 1
    light1.name = "Desk lamp"
    light1.on = True
    light1.brightness = 200

    light2 = MagicMock()
    light2.light_id = 2
    light2.name = "Lantern"
    light2.on = True
    light2.brightness = 150

    bridge = MagicMock()
    bridge.lights = [light1, light2]
    bridge.get_light.return_value = {
        "state": {"on": True, "bri": 200, "colormode": "ct", "ct": 370}
    }

    with patch("fiat_lux.pulse._get_bridge", return_value=bridge):
        yield bridge


class TestPulseStyles:
    @patch("fiat_lux.pulse.time.sleep")
    def test_chirp_is_fast(self, mock_sleep, mock_bridge):
        breathing_pulse("Desk lamp", breaths=2, style="chirp")
        # Chirp sleeps are short (0.5, 0.7)
        for call in mock_sleep.call_args_list:
            assert call[0][0] <= 1.0

    @patch("fiat_lux.pulse.time.sleep")
    def test_slow_is_longer(self, mock_sleep, mock_bridge):
        breathing_pulse("Desk lamp", breaths=2, style="slow")
        # Slow has sleeps > 1.0
        has_long_sleep = any(call[0][0] > 1.0 for call in mock_sleep.call_args_list)
        assert has_long_sleep


class TestMultiLightSync:
    @patch("fiat_lux.pulse.time.sleep")
    def test_synced_pulse_hits_all_lights(self, mock_sleep, mock_bridge):
        breathing_pulse(["Desk lamp", "Lantern"], breaths=2, style="chirp")
        # Both lights should have been set in each tick
        light_ids_set = set()
        for call in mock_bridge.set_light.call_args_list:
            light_ids_set.add(call[0][0])
        assert 1 in light_ids_set
        assert 2 in light_ids_set

    @patch("fiat_lux.pulse.time.sleep")
    def test_single_light_as_string(self, mock_sleep, mock_bridge):
        breathing_pulse("Desk lamp", breaths=1, style="chirp")
        assert mock_bridge.set_light.called

    @patch("fiat_lux.pulse.time.sleep")
    def test_unknown_light_skipped(self, mock_sleep, mock_bridge):
        breathing_pulse("Nonexistent", breaths=1, style="chirp")
        # No set_light calls for the pulse (only restore if any)
        # With no valid lights, nothing should happen
        assert not mock_bridge.set_light.called


class TestAlertLightsConfig:
    def test_defaults_to_all_lights(self, mock_bridge):
        with patch("fiat_lux.pulse.Path") as mock_path:
            mock_path.home.return_value = MagicMock()
            config_file = mock_path.home() / ".config" / "fiat_lux" / "calendars.json"
            config_file.exists.return_value = False
            lights = _get_alert_lights()
            assert len(lights) == 2

    def test_reads_config(self, tmp_path, mock_bridge):
        config = {"calendars": ["Work"], "alert_lights": ["Desk lamp"]}
        config_file = tmp_path / "calendars.json"
        config_file.write_text(json.dumps(config))

        with patch("fiat_lux.pulse.Path.home", return_value=tmp_path):
            # Need to construct the right path
            (tmp_path / ".config" / "fiat_lux").mkdir(parents=True, exist_ok=True)
            (tmp_path / ".config" / "fiat_lux" / "calendars.json").write_text(
                json.dumps(config)
            )
            lights = _get_alert_lights()
            assert lights == ["Desk lamp"]
