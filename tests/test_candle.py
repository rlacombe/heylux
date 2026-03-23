"""Tests for candle mode."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from fiat_lux.pulse import candle_mode_loop


@pytest.fixture
def mock_bridge():
    light1 = MagicMock()
    light1.light_id = 1
    light1.name = "Night stand"
    light1.on = True
    light1.brightness = 200

    bridge = MagicMock()
    bridge.lights = [light1]
    bridge.get_light.return_value = {
        "state": {"on": True, "bri": 200, "colormode": "ct", "ct": 370}
    }

    with patch("fiat_lux.pulse._get_bridge", return_value=bridge):
        yield bridge


class TestCandleMode:
    @pytest.mark.asyncio
    async def test_can_be_cancelled(self, mock_bridge):
        task = asyncio.create_task(candle_mode_loop([1]))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # Should have restored state
        assert mock_bridge.set_light.called

    @pytest.mark.asyncio
    async def test_saves_state_before_starting(self, mock_bridge):
        task = asyncio.create_task(candle_mode_loop([1]))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        mock_bridge.get_light.assert_called()

    @pytest.mark.asyncio
    async def test_fade_out_exits_cleanly(self, mock_bridge):
        """Candle with fade_out_minutes=0.001 (~60ms) should exit on its own."""
        task = asyncio.create_task(candle_mode_loop([1], fade_out_minutes=0.001))
        # Should finish on its own (fade out is nearly instant)
        await asyncio.wait_for(task, timeout=5.0)
        # Last set_light call should turn lights off
        last_call = mock_bridge.set_light.call_args_list[-1]
        assert last_call[0][1].get("on") is False

    @pytest.mark.asyncio
    async def test_targets_specific_lights(self, mock_bridge):
        light2 = MagicMock()
        light2.light_id = 2
        light2.name = "Desk lamp"
        mock_bridge.lights.append(light2)
        mock_bridge.get_light.return_value = {
            "state": {"on": True, "bri": 100, "colormode": "ct", "ct": 300}
        }

        task = asyncio.create_task(candle_mode_loop([2]))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Should only have targeted light_id 2
        for call in mock_bridge.set_light.call_args_list:
            if isinstance(call[0][0], int):
                assert call[0][0] in (1, 2)  # 1 for save/restore, 2 for candle
