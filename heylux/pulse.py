"""Light pulse effects for notifications and ambient breathing.

Uses phue directly for low-latency light control.
"""

import asyncio
import random
import time
from pathlib import Path
from typing import Any

from heylux.mcp.hue import _get_bridge


def _save_light_state(bridge, light_id: int) -> dict:
    """Capture current light state for later restore."""
    state = bridge.get_light(light_id)["state"]
    saved = {
        "on": state["on"],
        "bri": state.get("bri", 254),
        "colormode": state.get("colormode", "ct"),
    }
    if "ct" in state:
        saved["ct"] = state["ct"]
    if "hue" in state:
        saved["hue"] = state["hue"]
        saved["sat"] = state["sat"]
    if "xy" in state:
        saved["xy"] = state["xy"]
    return saved


def _restore_light_state(bridge, light_id: int, saved: dict) -> None:
    """Restore a previously saved light state."""
    cmd = {"transitiontime": 25}  # 2.5s fade back
    if saved["colormode"] == "xy" and "xy" in saved:
        cmd["xy"] = saved["xy"]
    elif saved["colormode"] == "ct":
        cmd["ct"] = saved.get("ct", 370)
    else:
        cmd["hue"] = saved.get("hue", 0)
        cmd["sat"] = saved.get("sat", 0)
    cmd["bri"] = saved["bri"]
    cmd["on"] = saved["on"]
    bridge.set_light(light_id, cmd)


def breathing_pulse(
    light_names: str | list[str] = "Desk lamp",
    hue: int = 46920,
    saturation: int = 160,
    breaths: int = 2,
    style: str = "chirp",
) -> None:
    """Perform a synchronized breathing pulse on one or more lights.

    Args:
        light_names: Light name(s) to pulse. String or list of strings.
        hue: Hue value (46920=blue, 8000=amber).
        saturation: Color saturation (0-254).
        breaths: Number of breath cycles.
        style: "chirp" (fast, snappy) or "slow" (gentle breathing wave).
    """
    if isinstance(light_names, str):
        light_names = [light_names]

    b = _get_bridge()

    # Resolve all light IDs
    name_map = {l.name.lower(): l.light_id for l in b.lights}
    light_ids = []
    for name in light_names:
        lid = name_map.get(name.lower())
        if lid is not None:
            light_ids.append(lid)
    if not light_ids:
        return

    # Save all states
    saved = {lid: _save_light_state(b, lid) for lid in light_ids}

    def _set_all(cmd: dict) -> None:
        for lid in light_ids:
            b.set_light(lid, cmd)

    # Timing by style
    if style == "slow":
        snap_on = 15  # 1.5s inhale
        fade_out = 25  # 2.5s exhale
        pause_on = 1.7
        pause_off = 2.7
    else:  # chirp
        snap_on = 3  # 0.3s snap
        fade_out = 5  # 0.5s fade
        pause_on = 0.5
        pause_off = 0.7

    try:
        # Initial flash
        _set_all({
            "on": True,
            "hue": hue,
            "sat": saturation,
            "bri": 254,
            "transitiontime": snap_on,
        })
        time.sleep(pause_on)

        for _ in range(breaths - 1):
            _set_all({"bri": 20, "transitiontime": fade_out})
            time.sleep(pause_off)

            _set_all({"bri": 254, "transitiontime": snap_on})
            time.sleep(pause_on)

        # Final fade out
        _set_all({"bri": 20, "transitiontime": fade_out})
        time.sleep(pause_off)

    finally:
        for lid, state in saved.items():
            _restore_light_state(b, lid, state)


# Preset pulses for calendar alerts
AMBER_HUE = 8000
BLUE_HUE = 46920


def _get_alert_lights() -> list[str]:
    """Get configured alert lights, or all lights if not configured."""
    import json
    config_file = Path.home() / ".config" / "heylux" / "calendars.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
            lights = config.get("alert_lights", [])
            if lights:
                return lights
        except (json.JSONDecodeError, ValueError):
            pass
    # Default: all lights
    try:
        b = _get_bridge()
        return [l.name for l in b.lights]
    except RuntimeError:
        return ["Desk lamp"]


def pulse_heads_up() -> None:
    """Slow amber pulse — meeting in 5 minutes."""
    breathing_pulse(_get_alert_lights(), hue=AMBER_HUE, saturation=200, breaths=4, style="slow")


def pulse_starting_now() -> None:
    """Fast blue chirp — meeting in 15 seconds."""
    breathing_pulse(_get_alert_lights(), hue=BLUE_HUE, saturation=200, breaths=5, style="chirp")


# ---------------------------------------------------------------------------
# Continuous breathing mode
# ---------------------------------------------------------------------------

BREATHE_INHALE = 4.0  # seconds to fade up
BREATHE_EXHALE = 6.0  # seconds to fade down
BREATHE_BRI_HIGH = 150  # ~60% brightness
BREATHE_BRI_LOW = 25  # ~10% brightness
# Simulate ~1500K via hue/sat (below the bridge's 2000K CT floor)
BREATHE_HUE = 7500  # deeper amber, more golden
BREATHE_SAT = 245


def _save_all_states(bridge) -> dict[int, dict]:
    """Capture state of all lights for later restore."""
    saved = {}
    for light in bridge.lights:
        saved[light.light_id] = _save_light_state(bridge, light.light_id)
    return saved


def _restore_all_states(bridge, saved: dict[int, dict]) -> None:
    """Restore all lights to their saved states."""
    for light_id, state in saved.items():
        _restore_light_state(bridge, light_id, state)


def _breathe_tick(bridge, light_ids: list[int], inhale: bool) -> None:
    """Execute a single inhale or exhale on all lights."""
    bri = BREATHE_BRI_HIGH if inhale else BREATHE_BRI_LOW
    duration = BREATHE_INHALE if inhale else BREATHE_EXHALE
    cmd = {
        "on": True,
        "bri": bri,
        "hue": BREATHE_HUE,
        "sat": BREATHE_SAT,
        "transitiontime": round(duration * 10),
    }
    for lid in light_ids:
        bridge.set_light(lid, cmd)


async def breathing_mode_loop(light_ids: list[int] | None = None) -> dict[int, Any]:
    """Run continuous breathing on lights until cancelled.

    Returns the saved states dict so the caller can restore after cancellation.
    This is an async coroutine meant to run as an asyncio.Task.
    """
    b = _get_bridge()

    if light_ids is None:
        light_ids = [l.light_id for l in b.lights]

    saved = _save_all_states(b)

    # Initial setup: set all lights to deep amber at low brightness
    for lid in light_ids:
        b.set_light(lid, {
            "on": True,
            "bri": BREATHE_BRI_LOW,
            "hue": BREATHE_HUE,
            "sat": BREATHE_SAT,
            "transitiontime": 20,
        })
    await asyncio.sleep(2.0)

    try:
        while True:
            # Inhale
            await asyncio.to_thread(_breathe_tick, b, light_ids, True)
            await asyncio.sleep(BREATHE_INHALE + 0.2)
            # Exhale
            await asyncio.to_thread(_breathe_tick, b, light_ids, False)
            await asyncio.sleep(BREATHE_EXHALE + 0.2)
    except asyncio.CancelledError:
        # Restore lights to pre-breathing state
        await asyncio.to_thread(_restore_all_states, b, saved)
        raise


# ---------------------------------------------------------------------------
# Candle mode — physics-based flickering candlelight simulation
#
# Based on photodiode measurements of real candle flames (Park 2013),
# flame oscillation dynamics (Nature Scientific Reports 2018), and
# reverse-engineered candle LED chips (cpldcpu 2013/2016).
#
# Key insights from the research:
#   - Real candles are mostly bright with occasional dips (not centered)
#   - Flicker spectrum is flat to ~4 Hz then rolls off at 40 dB/decade
#   - Gusts cause fast dips with slow damped recovery
#   - Color and brightness are coupled: dimmer = redder, brighter = yellower
#   - Perlin noise gives natural temporal coherence (no jarring jumps)
#   - Hue bridge interpolates transitions internally — send ~1 cmd/sec/bulb
# ---------------------------------------------------------------------------

# CIE xy coordinates along the Planckian locus — centered deep red ~1500K
_CANDLE_XY_1400K = (0.5850, 0.3930)  # very deep red — dimmest moments
_CANDLE_XY_1500K = (0.5790, 0.3960)  # center — deep red candle
_CANDLE_XY_1700K = (0.5650, 0.4030)  # warm amber — brightest moments

# Brightness: two-layer design
#   Layer 1 — slow swell: lazy sinusoidal undulation (the main movement)
#   Layer 2 — fast shimmer: tiny Perlin jitter (adds life without distraction)
# Each light follows its own independent random pattern (decorrelated offsets).
CANDLE_BRI_BASELINE = 165   # ~65% — resting brightness
CANDLE_BRI_HIGH = 190       # ~75% — swell peak
CANDLE_BRI_LOW = 140        # ~55% — swell trough, always readable

# Slow swell — lazy, hypnotic wave you barely notice consciously
CANDLE_SWELL_PERIOD = (10.0, 18.0)  # seconds per cycle

# Fast shimmer — tiny amplitude, just barely visible, adds organic life
CANDLE_FLICKER_RANGE = 10   # +/- from swell position (very subtle)

# Gust: gentle dips, won't lose your page
CANDLE_GUST_BRI = (80, 110)      # barely noticeable
CANDLE_GUST_INTERVAL = (15.0, 30.0)
CANDLE_GUST_DIP_TT = (3, 6)      # fast dip: 0.3-0.6s
CANDLE_GUST_RECOVER_TT = (20, 40)  # slow recovery: 2.0-4.0s

# Near-extinguishment: disabled — no surprise dips while reading
CANDLE_NEAR_SNUFF_CHANCE = 0.0
CANDLE_NEAR_SNUFF_BRI = (80, 100)
CANDLE_NEAR_SNUFF_TT = (2, 4)

# Tick timing: fast updates so shimmer feels smooth, not steppy
CANDLE_TICK_INTERVAL = (0.3, 0.6)


def _perlin_1d(t: float) -> float:
    """Simple 1D Perlin-like noise using smoothed interpolation between random gradients.

    Returns a value in [-1, 1] with natural temporal coherence.
    Uses a hash function so identical t values produce identical output.
    """
    import math

    def _fade(x: float) -> float:
        return x * x * x * (x * (x * 6 - 15) + 10)

    def _grad(h: int) -> float:
        # Pseudo-random gradient from hash
        return ((h * 2654435761 & 0xFFFFFFFF) / 0xFFFFFFFF) * 2 - 1

    floor = math.floor(t)
    frac = t - floor
    i = int(floor) & 0xFFFF

    g0 = _grad(i)
    g1 = _grad(i + 1)

    u = _fade(frac)
    return g0 * frac * (1 - u) + g1 * (frac - 1) * u


def _candle_xy_for_brightness(bri: int) -> list[float]:
    """Map brightness to candle color: dimmer = redder, brighter = yellower.

    This couples color and brightness the way real thermal emission works:
    a dimmer flame is cooler (redder), a brighter flame is hotter (yellower).
    Deep red range: 1400K (darkest dips) to 1700K (brightest moments).
    """
    # Normalize brightness to 0-1 range within our operating range
    t = max(0.0, min(1.0, (bri - CANDLE_BRI_LOW) / max(1, CANDLE_BRI_HIGH - CANDLE_BRI_LOW)))

    # Interpolate along Planckian locus: dim(1400K) -> center(1500K) -> bright(1700K)
    if t < 0.5:
        # Lower half: 1400K -> 1500K
        s = t * 2
        x = _CANDLE_XY_1400K[0] + s * (_CANDLE_XY_1500K[0] - _CANDLE_XY_1400K[0])
        y = _CANDLE_XY_1400K[1] + s * (_CANDLE_XY_1500K[1] - _CANDLE_XY_1400K[1])
    else:
        # Upper half: 1500K -> 1700K
        s = (t - 0.5) * 2
        x = _CANDLE_XY_1500K[0] + s * (_CANDLE_XY_1700K[0] - _CANDLE_XY_1500K[0])
        y = _CANDLE_XY_1500K[1] + s * (_CANDLE_XY_1700K[1] - _CANDLE_XY_1500K[1])

    return [round(x, 4), round(y, 4)]


def _candle_tick(bridge, light_ids: list[int], tick_time: float,
                 per_light_offsets: dict[int, float],
                 per_light_bri: dict[int, int],
                 fade: float) -> None:
    """One shimmer tick — each light gets tiny Perlin jitter around its own swell."""
    for lid in light_ids:
        breath_bri = per_light_bri[lid]

        # Fast shimmer: tiny Perlin noise, symmetric (no asymmetric dips)
        noise = _perlin_1d(tick_time * 2.0 + per_light_offsets[lid])
        jitter = noise * CANDLE_FLICKER_RANGE

        bri = round(breath_bri + jitter)
        bri = max(1, min(254, round(bri * fade)))

        # Near-extinguishment: rare dramatic dip
        if random.random() < CANDLE_NEAR_SNUFF_CHANCE:
            bri = random.randint(*CANDLE_NEAR_SNUFF_BRI)
            tt = random.randint(*CANDLE_NEAR_SNUFF_TT)
        else:
            tt = random.randint(8, 18)

        xy = _candle_xy_for_brightness(bri)
        # Slight per-light color jitter
        xy[0] += random.uniform(-0.004, 0.004)
        xy[1] += random.uniform(-0.002, 0.002)

        bridge.set_light(lid, {"bri": bri, "xy": xy, "transitiontime": tt})


def _candle_gust(bridge, light_ids: list[int]) -> None:
    """Wind gust — all lights dim together, fast."""
    gust_bri = random.randint(*CANDLE_GUST_BRI)
    tt = random.randint(*CANDLE_GUST_DIP_TT)
    xy = _candle_xy_for_brightness(gust_bri)
    for lid in light_ids:
        bridge.set_light(lid, {"bri": gust_bri, "xy": xy, "transitiontime": tt})


def _candle_recover(bridge, light_ids: list[int], breath_bri: int,
                    per_light_offsets: dict[int, float]) -> None:
    """Recover from a gust — slow, with per-light variation."""
    tt = random.randint(*CANDLE_GUST_RECOVER_TT)
    for lid in light_ids:
        bri = breath_bri + random.randint(-15, 15)
        bri = max(1, min(254, bri))
        xy = _candle_xy_for_brightness(bri)
        xy[0] += random.uniform(-0.003, 0.003)
        bridge.set_light(lid, {"bri": bri, "xy": xy, "transitiontime": tt})


async def candle_mode_loop(
    light_ids: list[int] | None = None,
    fade_out_minutes: float = 0,
) -> None:
    """Run continuous candle mode on lights until cancelled.

    Two-layer simulation per light:
      1. Slow swell: lazy sinusoidal undulation (the main visible movement)
      2. Fast shimmer: tiny Perlin-noise jitter (adds organic life)
    Plus occasional gentle wind gusts.

    Each light is fully independent — its own swell period, swell phase,
    and Perlin noise offset, so multiple candles never look synchronized.

    Color is coupled to brightness along the Planckian locus (1400-1700K)
    using CIE xy coordinates, reaching below Hue's 2000K ct floor.

    If fade_out_minutes > 0, gradually dims over that duration then turns off.
    """
    import math

    b = _get_bridge()

    if light_ids is None:
        light_ids = [l.light_id for l in b.lights]

    saved = _save_all_states(b)

    # Per-light independent parameters for full decorrelation:
    #   - Perlin noise offset: different shimmer pattern per light
    #   - Swell period: each light breathes at its own pace
    #   - Swell phase offset: lights start at different points in their cycle
    per_light_offsets = {lid: random.uniform(0, 100) for lid in light_ids}
    per_light_swell_period = {lid: random.uniform(*CANDLE_SWELL_PERIOD) for lid in light_ids}
    per_light_swell_phase = {lid: random.uniform(0, 1) for lid in light_ids}

    # Fade into candle color
    xy_start = _candle_xy_for_brightness(CANDLE_BRI_BASELINE)
    for lid in light_ids:
        b.set_light(lid, {
            "on": True,
            "xy": xy_start,
            "bri": CANDLE_BRI_BASELINE,
            "transitiontime": 20,
        })
    await asyncio.sleep(2.2)

    try:
        next_gust = asyncio.get_event_loop().time() + random.uniform(*CANDLE_GUST_INTERVAL)
        start_time = asyncio.get_event_loop().time()
        fade_out_seconds = fade_out_minutes * 60

        while True:
            now = asyncio.get_event_loop().time()
            elapsed = now - start_time

            # Fade-out envelope
            if fade_out_seconds > 0:
                fade = max(0.0, 1.0 - elapsed / fade_out_seconds)
                if fade <= 0:
                    for lid in light_ids:
                        b.set_light(lid, {"on": False, "transitiontime": 30})
                    return
            else:
                fade = 1.0

            # Per-light independent swell — each light has its own period and phase
            per_light_bri = {}
            for lid in light_ids:
                period = per_light_swell_period[lid]
                phase_offset = per_light_swell_phase[lid]
                phase = ((elapsed / period) + phase_offset) % 1.0
                wave = (math.sin(phase * 2 * math.pi - math.pi / 2) + 1) / 2
                per_light_bri[lid] = round(CANDLE_BRI_LOW + wave * (CANDLE_BRI_HIGH - CANDLE_BRI_LOW))

            # Use average swell for gust recovery target
            avg_bri = sum(per_light_bri.values()) // len(per_light_bri)

            # Wind gust check
            if now >= next_gust:
                await asyncio.to_thread(_candle_gust, b, light_ids)
                dip_time = random.uniform(0.3, 0.8)
                await asyncio.sleep(dip_time)
                await asyncio.to_thread(
                    _candle_recover, b, light_ids, avg_bri, per_light_offsets
                )
                recover_time = random.uniform(2.5, 4.5)
                await asyncio.sleep(recover_time)
                next_gust = now + random.uniform(*CANDLE_GUST_INTERVAL)
            else:
                # Fast shimmer tick — tiny jitter on each light's own swell
                await asyncio.to_thread(
                    _candle_tick, b, light_ids, elapsed,
                    per_light_offsets, per_light_bri, fade,
                )
                await asyncio.sleep(random.uniform(*CANDLE_TICK_INTERVAL))

    except asyncio.CancelledError:
        await asyncio.to_thread(_restore_all_states, b, saved)
        raise
