"""Background calendar alert loop.

Polls macOS Calendar.app via icalBuddy and fires light pulses
at configurable thresholds before meetings.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from fiat_lux.calendar import get_upcoming_events, icalbuddy_available, CALENDAR_CONFIG
from fiat_lux.pulse import pulse_heads_up, pulse_starting_now

# Alert thresholds in minutes
HEADS_UP_MINUTES = 5.0
STARTING_NOW_MINUTES = 0.25  # 15 seconds

# How often to poll (seconds)
POLL_INTERVAL = 30

# Track which alerts we've already fired: {(title, start): set of thresholds}
_fired: dict[tuple[str, str], set[str]] = {}


def _is_configured() -> bool:
    """Check if calendar alerts are set up."""
    if not icalbuddy_available():
        return False
    if not CALENDAR_CONFIG.exists():
        return False
    config = json.loads(CALENDAR_CONFIG.read_text())
    return bool(config.get("calendars"))


def _cleanup_fired() -> None:
    """Remove entries for events whose start time is in the past."""
    now = datetime.now()
    stale = []
    for key in _fired:
        _title, start_iso = key
        try:
            start = datetime.fromisoformat(start_iso)
            if start < now:
                stale.append(key)
        except ValueError:
            stale.append(key)
    for key in stale:
        del _fired[key]


def _check_and_alert() -> None:
    """Check upcoming events and fire pulses at thresholds."""
    events = get_upcoming_events(minutes_ahead=10)

    for event in events:
        key = (event["title"], event["start"])
        mins = event["minutes_until"]

        if key not in _fired:
            _fired[key] = set()

        # T-5 minutes: amber heads-up
        if mins <= HEADS_UP_MINUTES and "heads_up" not in _fired[key]:
            _fired[key].add("heads_up")
            print(f"  [alert] {event['title']} in {mins:.0f}min — heads up pulse",
                  flush=True)
            try:
                pulse_heads_up()
            except Exception as e:
                print(f"  [alert] pulse error: {e}", flush=True)

        # T-15 seconds: blue starting-now
        if mins <= STARTING_NOW_MINUTES and "starting_now" not in _fired[key]:
            _fired[key].add("starting_now")
            print(f"  [alert] {event['title']} starting now — pulse",
                  flush=True)
            try:
                pulse_starting_now()
            except Exception as e:
                print(f"  [alert] pulse error: {e}", flush=True)


async def alert_loop() -> None:
    """Background async loop that polls calendar and fires alerts.

    Runs forever until cancelled. Safe to run as an asyncio.Task.
    """
    if not _is_configured():
        print("  Calendar alerts: not configured (run 'lux setup calendar')",
              flush=True)
        return

    print("  Calendar alerts: active", flush=True)

    while True:
        try:
            # Run the blocking icalBuddy call in a thread to avoid blocking
            # the event loop (it shells out to a subprocess, typically ~100ms)
            await asyncio.to_thread(_check_and_alert)
            _cleanup_fired()
        except Exception as e:
            print(f"  [alert] error: {e}", flush=True)

        await asyncio.sleep(POLL_INTERVAL)
