"""Fast-path heuristics for common commands.

Pattern-matches user input and executes directly via phue — no LLM needed.
Returns None if the command doesn't match any known pattern.
"""

import re

from fresnel.tools.circadian import get_circadian_state
from fresnel.tools.hue import _get_bridge
from fresnel.routines import run_routine, list_routines

BRIGHTNESS_STEP = 20  # percent per brighter/dimmer


def try_shortcut(text: str) -> str | None:
    """Try to handle a command directly. Returns response text, or None to fall through to LLM."""
    text = text.strip().lower()

    # --- On / Off ---
    if re.match(r"^(turn\s+)?(all\s+)?(my\s+)?(the\s+)?lights?\s+off$", text):
        return _all_off()

    if re.match(r"^(turn\s+)?(all\s+)?(my\s+)?(the\s+)?lights?\s+on$", text):
        return _all_on()

    if text in ("off", "goodnight", "good night"):
        return _all_off()

    if text == "on":
        return _all_on()

    # --- Brightness: absolute ---
    m = re.match(r"^(?:set\s+)?(?:brightness\s+(?:to\s+)?)?(\d{1,3})\s*%$", text)
    if m:
        return _set_brightness(int(m.group(1)))

    m = re.match(r"^dim\s+(?:to\s+)?(\d{1,3})\s*%?$", text)
    if m:
        return _set_brightness(int(m.group(1)))

    # --- Brightness: relative ---
    if text in ("brighter", "bright", "brighten", "more light", "more"):
        return _adjust_brightness(BRIGHTNESS_STEP)

    if text in ("dimmer", "dim", "darker", "less light", "less"):
        return _adjust_brightness(-BRIGHTNESS_STEP)

    m = re.match(r"^(brighter|dimmer)\s+(\d{1,3})\s*%?$", text)
    if m:
        step = int(m.group(2))
        return _adjust_brightness(step if m.group(1) == "brighter" else -step)

    # --- Circadian ---
    if text in ("circadian", "set for now", "set to now", "optimize", "auto"):
        return _apply_circadian()

    # --- Routines ---
    if text in ("routines", "list routines"):
        routines = list_routines()
        if not routines:
            return "No routines saved."
        lines = ["Routines:"]
        for name, desc in routines.items():
            lines.append(f"  {name} — {desc}")
        return "\n".join(lines)

    # Try matching a routine name directly
    result = run_routine(text)
    if result is not None:
        return result

    return None


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def _all_off() -> str:
    b = _get_bridge()
    for light in b.lights:
        b.set_light(light.light_id, {"on": False, "transitiontime": 10})
    return "All lights off."


def _all_on() -> str:
    b = _get_bridge()
    for light in b.lights:
        b.set_light(light.light_id, {"on": True, "transitiontime": 10})
    return "All lights on."


def _apply_circadian() -> str:
    b = _get_bridge()
    state = get_circadian_state()

    bri = round(state["brightness_pct"] * 254 / 100)
    ct = round(1_000_000 / state["kelvin"])

    cmd = {"on": True, "bri": bri, "ct": ct, "transitiontime": 20}

    active = [a.lower() for a in state["active_lights"]]

    for light in b.lights:
        if light.name.lower() in active:
            b.set_light(light.light_id, cmd)
        else:
            b.set_light(light.light_id, {"on": False, "transitiontime": 20})

    return (
        f"Circadian: {state['mode_name']} "
        f"({state['kelvin']}K, {state['brightness_pct']}%)"
    )


def _set_brightness(pct: int) -> str:
    pct = max(0, min(100, pct))
    b = _get_bridge()
    bri = round(pct * 254 / 100)
    for light in b.lights:
        if light.on:
            b.set_light(light.light_id, {"bri": bri, "transitiontime": 4})
    return f"Brightness: {pct}%"


def _adjust_brightness(step: int) -> str:
    b = _get_bridge()
    changed = []
    for light in b.lights:
        if light.on:
            current_pct = round(light.brightness * 100 / 254)
            new_pct = max(1, min(100, current_pct + step))
            new_bri = round(new_pct * 254 / 100)
            b.set_light(light.light_id, {"bri": new_bri, "transitiontime": 4})
            changed.append(new_pct)

    if not changed:
        return "No lights are on."

    avg = round(sum(changed) / len(changed))
    direction = "Brighter" if step > 0 else "Dimmer"
    return f"{direction}: ~{avg}%"
