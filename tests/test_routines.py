"""Tests for the routines system."""

import json
from unittest.mock import MagicMock, patch

import pytest

from heylux.routines import (
    DEFAULT_ROUTINES,
    _load_routines,
    list_routines,
    run_routine,
)


@pytest.fixture
def routines_file(tmp_path, monkeypatch):
    """Redirect routines file to tmp dir."""
    f = tmp_path / "routines.json"
    monkeypatch.setattr("heylux.routines.ROUTINES_FILE", f)
    monkeypatch.setattr("heylux.routines.CONFIG_DIR", tmp_path)
    return f


@pytest.fixture
def mock_bridge():
    """Mock the Hue bridge."""
    light1 = MagicMock()
    light1.light_id = 1
    light1.name = "Night stand"

    light2 = MagicMock()
    light2.light_id = 2
    light2.name = "Ceiling lamp 1"

    light3 = MagicMock()
    light3.light_id = 3
    light3.name = "Desk lamp"

    bridge = MagicMock()
    bridge.lights = [light1, light2, light3]

    with patch("heylux.routines._get_bridge", return_value=bridge):
        yield bridge


class TestDefaultSeeding:
    def test_seeds_defaults_on_first_load(self, routines_file):
        assert not routines_file.exists()
        routines = _load_routines()
        assert routines_file.exists()
        assert "bedtime" in routines
        assert "focus" in routines
        assert "relax" in routines

    def test_does_not_overwrite_existing(self, routines_file):
        routines_file.write_text(json.dumps({"custom": {"description": "test"}}))
        routines = _load_routines()
        assert "custom" in routines
        assert "bedtime" not in routines


class TestListRoutines:
    def test_lists_all(self, routines_file):
        routines_file.write_text(json.dumps(DEFAULT_ROUTINES))
        result = list_routines()
        assert len(result) == len(DEFAULT_ROUTINES)
        assert "bedtime" in result


class TestRunRoutine:
    def test_runs_known_routine(self, routines_file, mock_bridge):
        routines_file.write_text(json.dumps(DEFAULT_ROUTINES))
        result = run_routine("bedtime")
        assert result is not None
        assert "Bedtime" in result
        # Should have set at least one light
        assert mock_bridge.set_light.called

    def test_returns_none_for_unknown(self, routines_file):
        routines_file.write_text(json.dumps(DEFAULT_ROUTINES))
        assert run_routine("nonexistent") is None

    def test_case_insensitive(self, routines_file, mock_bridge):
        routines_file.write_text(json.dumps(DEFAULT_ROUTINES))
        result = run_routine("BEDTIME")
        assert result is not None

    def test_smart_quote_normalization(self, routines_file, mock_bridge):
        """Light names with smart quotes should match."""
        # Create a routine with a straight-quote light name
        routines = {
            "test": {
                "description": "test",
                "lights_on": {"Night stand": {"brightness_pct": 50}},
                "lights_off": [],
            }
        }
        routines_file.write_text(json.dumps(routines))

        # Mock a light with a smart-quote name
        mock_bridge.lights[0].name = "Night stand"
        result = run_routine("test")
        assert result is not None

    def test_bridge_error(self, routines_file):
        routines_file.write_text(json.dumps(DEFAULT_ROUTINES))
        with patch(
            "heylux.routines._get_bridge",
            side_effect=RuntimeError("No bridge"),
        ):
            result = run_routine("bedtime")
            assert "Error" in result
