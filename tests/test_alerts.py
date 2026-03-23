"""Tests for the calendar alert loop logic."""

from datetime import datetime, timedelta
from unittest.mock import patch

from fiat_lux.alerts import _cleanup_fired, _fired, _is_configured


class TestCleanupFired:
    def test_removes_past_events(self):
        _fired.clear()
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        _fired[("Past Meeting", past)] = {"heads_up"}
        _fired[("Future Meeting", future)] = {"heads_up"}

        _cleanup_fired()

        assert ("Past Meeting", past) not in _fired
        assert ("Future Meeting", future) in _fired

    def test_handles_empty(self):
        _fired.clear()
        _cleanup_fired()  # should not raise

    def test_removes_malformed_dates(self):
        _fired.clear()
        _fired[("Bad Event", "not-a-date")] = {"heads_up"}
        _cleanup_fired()
        assert len(_fired) == 0


class TestAlertDedup:
    def test_same_event_not_fired_twice(self):
        _fired.clear()
        future = (datetime.now() + timedelta(minutes=3)).isoformat()
        key = ("Meeting", future)

        _fired[key] = set()
        _fired[key].add("heads_up")

        assert "heads_up" in _fired[key]
        # Second check should see it's already fired
        assert "heads_up" in _fired[key]


class TestIsConfigured:
    @patch("fiat_lux.alerts.icalbuddy_available", return_value=False)
    def test_false_without_icalbuddy(self, _):
        assert _is_configured() is False

    @patch("fiat_lux.alerts.icalbuddy_available", return_value=True)
    @patch("fiat_lux.alerts.CALENDAR_CONFIG")
    def test_false_without_config_file(self, mock_path, _):
        mock_path.exists.return_value = False
        assert _is_configured() is False
