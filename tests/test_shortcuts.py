"""Tests for the shortcut pattern-matching system."""

from unittest.mock import MagicMock, patch

import pytest

from fiat_lux.shortcuts import (
    SHORTCUT_BREATHE_START,
    SHORTCUT_BREATHE_STOP,
    SHORTCUT_CANDLE_START,
    try_shortcut,
)


@pytest.fixture(autouse=True)
def mock_bridge():
    """Mock the Hue bridge so shortcuts don't need real hardware."""
    light1 = MagicMock()
    light1.light_id = 1
    light1.name = "Ceiling lamp 1"
    light1.on = True
    light1.brightness = 200

    light2 = MagicMock()
    light2.light_id = 2
    light2.name = "Desk lamp"
    light2.on = True
    light2.brightness = 150

    bridge = MagicMock()
    bridge.lights = [light1, light2]

    with patch("fiat_lux.shortcuts._get_bridge", return_value=bridge):
        yield bridge


class TestOnOff:
    def test_lights_off(self):
        assert try_shortcut("lights off") == SHORTCUT_BREATHE_STOP

    def test_turn_my_lights_off(self):
        assert try_shortcut("turn my lights off") == SHORTCUT_BREATHE_STOP

    def test_turn_all_lights_off(self):
        assert try_shortcut("turn all lights off") == SHORTCUT_BREATHE_STOP

    def test_off(self):
        assert try_shortcut("off") == SHORTCUT_BREATHE_STOP

    def test_goodnight(self):
        assert try_shortcut("goodnight") == SHORTCUT_BREATHE_STOP

    def test_good_night(self):
        assert try_shortcut("good night") == SHORTCUT_BREATHE_STOP

    def test_lights_on(self):
        result = try_shortcut("lights on")
        assert result is not None
        assert "on" in result.lower()

    def test_on(self):
        result = try_shortcut("on")
        assert result is not None


class TestBrightness:
    def test_absolute_50_percent(self):
        result = try_shortcut("50%")
        assert result is not None
        assert "50%" in result

    def test_dim_to_30(self):
        result = try_shortcut("dim to 30%")
        assert result is not None
        assert "30%" in result

    def test_set_brightness_to_80(self):
        result = try_shortcut("set brightness to 80%")
        assert result is not None
        assert "80%" in result

    def test_brighter(self):
        result = try_shortcut("brighter")
        assert result is not None
        assert "brighter" in result.lower()

    def test_dimmer(self):
        result = try_shortcut("dimmer")
        assert result is not None
        assert "dimmer" in result.lower()

    def test_less(self):
        result = try_shortcut("less")
        assert result is not None

    def test_more(self):
        result = try_shortcut("more")
        assert result is not None


class TestCircadian:
    @patch("fiat_lux.shortcuts.get_circadian_state")
    def test_circadian(self, mock_state):
        mock_state.return_value = {
            "kelvin": 5000,
            "brightness_pct": 80,
            "active_lights": ["ceiling", "desk"],
            "mode_name": "Morning Focus",
        }
        result = try_shortcut("circadian")
        assert result is not None
        assert "Morning Focus" in result

    @patch("fiat_lux.shortcuts.get_circadian_state")
    def test_auto(self, mock_state):
        mock_state.return_value = {
            "kelvin": 5000,
            "brightness_pct": 80,
            "active_lights": ["ceiling"],
            "mode_name": "Morning Focus",
        }
        result = try_shortcut("auto")
        assert result is not None


class TestRoutines:
    @patch("fiat_lux.shortcuts.list_routines")
    def test_list_routines(self, mock_list):
        mock_list.return_value = {"bedtime": "Reading in bed", "focus": "Deep work"}
        result = try_shortcut("routines")
        assert result is not None
        assert "bedtime" in result
        assert "focus" in result

    @patch("fiat_lux.shortcuts.run_routine")
    def test_named_routine(self, mock_run):
        mock_run.return_value = "Bedtime: Reading in bed"
        result = try_shortcut("bedtime")
        assert result == "Bedtime: Reading in bed"

    @patch("fiat_lux.shortcuts.run_routine")
    def test_unknown_routine_returns_none(self, mock_run):
        mock_run.return_value = None
        result = try_shortcut("something weird Lux wouldn't know")
        assert result is None


class TestCandle:
    def test_candle(self):
        assert try_shortcut("candle") == SHORTCUT_CANDLE_START

    def test_candle_mode(self):
        assert try_shortcut("candle mode") == SHORTCUT_CANDLE_START

    def test_candlelight(self):
        assert try_shortcut("candlelight") == SHORTCUT_CANDLE_START


class TestBreathing:
    def test_breathe(self):
        assert try_shortcut("breathe") == SHORTCUT_BREATHE_START

    def test_breathing(self):
        assert try_shortcut("breathing") == SHORTCUT_BREATHE_START

    def test_breathing_mode(self):
        assert try_shortcut("breathing mode") == SHORTCUT_BREATHE_START

    def test_stop(self):
        assert try_shortcut("stop") == SHORTCUT_BREATHE_STOP

    def test_stop_breathing(self):
        assert try_shortcut("stop breathing") == SHORTCUT_BREATHE_STOP

    def test_normal(self):
        assert try_shortcut("normal") == SHORTCUT_BREATHE_STOP


class TestFallthrough:
    @patch("fiat_lux.shortcuts.run_routine", return_value=None)
    def test_unknown_command_returns_none(self, _):
        assert try_shortcut("make it feel like a sunset") is None

    @patch("fiat_lux.shortcuts.run_routine", return_value=None)
    def test_empty_string_returns_none(self, _):
        assert try_shortcut("") is None

    @patch("fiat_lux.shortcuts.run_routine", return_value=None)
    def test_case_insensitive(self, _):
        assert try_shortcut("BREATHE") == SHORTCUT_BREATHE_START
        assert try_shortcut("LIGHTS OFF") == SHORTCUT_BREATHE_STOP
