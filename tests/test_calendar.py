"""Tests for calendar event parsing."""

from datetime import datetime, timedelta
from unittest.mock import patch

from heylux.calendar import _parse_events, get_upcoming_events


class TestParseEvents:
    def test_basic_event(self):
        output = (
            "• Team Standup\n"
            "    2026-03-23 09:00 - 09:30\n"
        )
        events = _parse_events(output)
        assert len(events) == 1
        assert events[0]["title"] == "Team Standup"
        assert "2026-03-23" in events[0]["start"]

    def test_multiple_events(self):
        output = (
            "• Team Standup\n"
            "    2026-03-23 09:00 - 09:30\n"
            "• Lunch with Alice\n"
            "    2026-03-23 12:00 - 13:00\n"
        )
        events = _parse_events(output)
        assert len(events) == 2
        assert events[0]["title"] == "Team Standup"
        assert events[1]["title"] == "Lunch with Alice"

    def test_empty_output(self):
        assert _parse_events("") == []

    def test_no_datetime_line(self):
        output = "• Event Without Time\n"
        events = _parse_events(output)
        assert len(events) == 0

    def test_event_with_location(self):
        """Events may have extra lines between title and datetime."""
        output = (
            "• Planning Meeting\n"
            "    location: Room 42\n"
            "    2026-03-23 14:00 - 15:00\n"
        )
        events = _parse_events(output)
        assert len(events) == 1
        assert events[0]["title"] == "Planning Meeting"

    def test_minutes_until(self):
        """minutes_until should be computed relative to now."""
        # Create an event 5 minutes from now
        future = datetime.now() + timedelta(minutes=5)
        time_str = future.strftime("%Y-%m-%d %H:%M")
        output = f"• Soon\n    {time_str} - {time_str}\n"
        events = _parse_events(output)
        assert len(events) == 1
        assert 4 <= events[0]["minutes_until"] <= 6


class TestGetUpcomingEvents:
    @patch("heylux.calendar._load_config")
    def test_returns_empty_when_no_calendars(self, mock_config):
        mock_config.return_value = {"calendars": []}
        assert get_upcoming_events() == []

    @patch("heylux.calendar._load_config")
    def test_returns_empty_when_no_config(self, mock_config):
        mock_config.return_value = {}
        assert get_upcoming_events() == []

    @patch("heylux.calendar.subprocess.run")
    @patch("heylux.calendar._load_config")
    def test_deduplicates_events(self, mock_config, mock_run):
        mock_config.return_value = {"calendars": ["Work"]}
        future = datetime.now() + timedelta(minutes=3)
        time_str = future.strftime("%Y-%m-%d %H:%M")
        # Same event appears twice
        mock_run.return_value = type("Result", (), {
            "returncode": 0,
            "stdout": (
                f"• Meeting\n    {time_str} - {time_str}\n"
                f"• Meeting\n    {time_str} - {time_str}\n"
            ),
        })()
        events = get_upcoming_events(minutes_ahead=10)
        assert len(events) == 1
