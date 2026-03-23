"""Calendar integration — setup and event polling via icalBuddy.

Uses macOS Calendar.app (which aggregates Google, iCloud, Exchange, etc.)
through the icalBuddy CLI tool.
"""

import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "fiat_lux"
CALENDAR_CONFIG = CONFIG_DIR / "calendars.json"


def _load_config() -> dict:
    if CALENDAR_CONFIG.exists():
        return json.loads(CALENDAR_CONFIG.read_text())
    return {}


def _save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CALENDAR_CONFIG.write_text(json.dumps(config, indent=2))


def icalbuddy_available() -> bool:
    """Check if icalBuddy is installed."""
    return shutil.which("icalBuddy") is not None


def install_icalbuddy() -> bool:
    """Install icalBuddy via Homebrew. Returns True on success."""
    if shutil.which("brew") is None:
        return False
    result = subprocess.run(
        ["brew", "install", "ical-buddy"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def list_calendars() -> list[dict]:
    """List all calendars from macOS Calendar.app.

    Returns a list of dicts with 'name', 'type', and 'uid' keys.
    """
    result = subprocess.run(
        ["icalBuddy", "-nc", "calendars"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    calendars = []
    current = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("• "):
            if current:
                calendars.append(current)
            current = {"name": line[2:]}
        elif line.startswith("type: "):
            current["type"] = line[6:]
        elif line.startswith("UID: "):
            current["uid"] = line[5:]
    if current:
        calendars.append(current)

    return calendars


def get_upcoming_events(minutes_ahead: int = 10) -> list[dict]:
    """Get events starting within the next N minutes.

    Only checks calendars configured in calendars.json.
    Returns list of dicts with 'title', 'start', 'minutes_until' keys.
    """
    config = _load_config()
    calendar_names = config.get("calendars", [])
    if not calendar_names:
        return []

    # Build include-calendars argument
    ic_arg = ",".join(calendar_names)

    # icalBuddy uses eventsToday+N (days), so look ahead enough days
    days_ahead = max(1, minutes_ahead // 1440 + 1)

    result = subprocess.run(
        [
            "icalBuddy",
            "-nc",       # no calendar names in output
            "-nrd",      # no relative dates
            "-n",        # only events from now on
            "-ea",       # exclude all-day events
            "-iep", "title,datetime",  # only title + datetime
            "-df", "%Y-%m-%d %H:%M",
            "-ic", ic_arg,
            f"eventsToday+{days_ahead}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    events = _parse_events(result.stdout)
    # Filter to window and deduplicate by title+start
    seen = set()
    unique = []
    for e in events:
        if not (0 <= e["minutes_until"] <= minutes_ahead):
            continue
        key = (e["title"], e["start"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def _parse_events(output: str) -> list[dict]:
    """Parse icalBuddy event output into structured dicts."""
    events = []
    current_title = None

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("• "):
            current_title = line[2:]
        elif current_title and ("at " in line or " - " in line):
            # Try to parse datetime from lines like "2026-03-23 08:30 - 10:00"
            match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", line)
            if match:
                try:
                    start = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
                    minutes_until = (start - datetime.now()).total_seconds() / 60
                    events.append({
                        "title": current_title,
                        "start": start.isoformat(),
                        "minutes_until": round(minutes_until, 1),
                    })
                except ValueError:
                    pass

    return events


def setup_interactive() -> bool:
    """Interactive setup flow for calendar alerts.

    Checks for icalBuddy, lists calendars, lets user pick.
    Returns True if setup completed successfully.
    """
    # Step 1: ensure icalBuddy is available
    if not icalbuddy_available():
        print("icalBuddy is not installed. It reads events from macOS Calendar.app.")
        answer = input("Install via Homebrew? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            print("Installing ical-buddy...")
            if not install_icalbuddy():
                print("Failed to install. Is Homebrew available?")
                return False
            print("Installed!")
        else:
            print("Calendar alerts require icalBuddy. Setup cancelled.")
            return False

    # Step 2: list calendars
    calendars = list_calendars()
    if not calendars:
        print("No calendars found in macOS Calendar.app.")
        return False

    # Filter out obvious non-event calendars for default suggestion
    skip_keywords = {"holiday", "holidays", "reminder", "reminders"}
    defaults = []
    print("\nAvailable calendars:\n")
    for i, cal in enumerate(calendars, 1):
        name = cal["name"]
        is_default = not any(kw in name.lower() for kw in skip_keywords)
        marker = "*" if is_default else " "
        print(f"  {marker} {i}. {name} ({cal.get('type', '?')})")
        if is_default:
            defaults.append(i)

    print(f"\n  * = included by default")
    print(f"\nEnter calendar numbers separated by commas, or press Enter for defaults.")
    choice = input(f"Calendars [{','.join(str(d) for d in defaults)}]: ").strip()

    if choice:
        try:
            indices = [int(x.strip()) for x in choice.split(",")]
        except ValueError:
            print("Invalid input.")
            return False
    else:
        indices = defaults

    selected = []
    for i in indices:
        if 1 <= i <= len(calendars):
            selected.append(calendars[i - 1]["name"])

    if not selected:
        print("No calendars selected.")
        return False

    # Step 3: save config
    config = _load_config()
    config["calendars"] = selected
    _save_config(config)

    print(f"\nSaved {len(selected)} calendar(s) to {CALENDAR_CONFIG}:")
    for name in selected:
        print(f"  - {name}")
    print("\nCalendar alerts are ready!")
    return True
