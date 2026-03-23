"""Tests for the pulse effects system."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from fiat_lux.pulse import (
    breathing_pulse,
    breathing_mode_loop,
    _save_light_state,
    _restore_light_state,
)


@pytest.fixture
def mock_bridge():
    """Mock the Hue bridge."""
    light1 = MagicMock()
    light1.light_id = 1
    light1.name = "Desk lamp"
    light1.on = True
    light1.brightness = 200

    bridge = MagicMock()
    bridge.lights = [light1]
    bridge.get_light.return_value = {
        "state": {
            "on": True,
            "bri": 200,
            "colormode": "ct",
            "ct": 370,
        }
    }

    with patch("fiat_lux.pulse._get_bridge", return_value=bridge):
        yield bridge


class TestSaveRestoreState:
    def test_saves_ct_mode(self, mock_bridge):
        mock_bridge.get_light.return_value = {
            "state": {"on": True, "bri": 200, "colormode": "ct", "ct": 370}
        }
        saved = _save_light_state(mock_bridge, 1)
        assert saved["on"] is True
        assert saved["bri"] == 200
        assert saved["colormode"] == "ct"
        assert saved["ct"] == 370

    def test_saves_hs_mode(self, mock_bridge):
        mock_bridge.get_light.return_value = {
            "state": {
                "on": True,
                "bri": 150,
                "colormode": "hs",
                "hue": 46920,
                "sat": 200,
            }
        }
        saved = _save_light_state(mock_bridge, 1)
        assert saved["colormode"] == "hs"
        assert saved["hue"] == 46920
        assert saved["sat"] == 200

    def test_restore_ct_mode(self, mock_bridge):
        saved = {"on": True, "bri": 200, "colormode": "ct", "ct": 370}
        _restore_light_state(mock_bridge, 1, saved)
        mock_bridge.set_light.assert_called_once()
        cmd = mock_bridge.set_light.call_args[0][1]
        assert cmd["ct"] == 370
        assert cmd["bri"] == 200

    def test_restore_hs_mode(self, mock_bridge):
        saved = {"on": True, "bri": 150, "colormode": "hs", "hue": 46920, "sat": 200}
        _restore_light_state(mock_bridge, 1, saved)
        cmd = mock_bridge.set_light.call_args[0][1]
        assert cmd["hue"] == 46920
        assert cmd["sat"] == 200


class TestBreathingPulse:
    @patch("fiat_lux.pulse.time.sleep")
    def test_saves_and_restores(self, mock_sleep, mock_bridge):
        breathing_pulse("Desk lamp", hue=8000, saturation=200, breaths=1)
        # First call is the pulse, later calls include restore
        calls = mock_bridge.set_light.call_args_list
        assert len(calls) >= 2
        # Last call should be the restore
        last_cmd = calls[-1][0][1]
        assert "ct" in last_cmd or "hue" in last_cmd

    @patch("fiat_lux.pulse.time.sleep")
    def test_no_crash_on_unknown_light(self, mock_sleep, mock_bridge):
        # Should return silently if light not found
        breathing_pulse("Unknown light", hue=8000, saturation=200, breaths=1)
        mock_bridge.set_light.assert_not_called()


class TestBreathingMode:
    @pytest.mark.asyncio
    async def test_can_be_cancelled(self, mock_bridge):
        task = asyncio.create_task(breathing_mode_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Should have called set_light for restore
        assert mock_bridge.set_light.called

    @pytest.mark.asyncio
    async def test_saves_state_before_starting(self, mock_bridge):
        task = asyncio.create_task(breathing_mode_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # get_light should have been called to save state
        mock_bridge.get_light.assert_called()
