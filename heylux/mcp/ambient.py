"""Ambient mode tools — candle and breathing modes as Claude-callable tools.

These tools manage long-running ambient light animations. They share state
with the daemon's shortcut handler via module-level task management.
"""

import asyncio
from typing import Any

from claude_agent_sdk import tool

from heylux.pulse import candle_mode_loop, breathing_mode_loop
from heylux.mcp.hue import _get_bridge

# Shared ambient task — accessed by both tools and daemon shortcut handler
_ambient_task: asyncio.Task | None = None


async def stop_ambient() -> bool:
    """Stop any running ambient mode. Returns True if one was running."""
    global _ambient_task
    if _ambient_task is not None and not _ambient_task.done():
        _ambient_task.cancel()
        try:
            await _ambient_task
        except asyncio.CancelledError:
            pass
        _ambient_task = None
        return True
    _ambient_task = None
    return False


async def start_candle(light_ids: list[int] | None = None,
                       fade_out_minutes: float = 0) -> None:
    """Stop any current ambient mode and start candle mode."""
    global _ambient_task
    await stop_ambient()
    _ambient_task = asyncio.create_task(
        candle_mode_loop(light_ids, fade_out_minutes=fade_out_minutes)
    )


async def start_breathe(light_ids: list[int] | None = None) -> None:
    """Stop any current ambient mode and start breathing mode."""
    global _ambient_task
    await stop_ambient()
    _ambient_task = asyncio.create_task(breathing_mode_loop(light_ids))


def _resolve_names(names: list[str]) -> list[int] | None:
    """Resolve light names to IDs. Returns None for all lights."""
    if not names:
        return None
    b = _get_bridge()
    name_map = {l.name.lower(): l.light_id for l in b.lights}
    ids = []
    for name in names:
        lid = name_map.get(name.lower())
        if lid is not None:
            ids.append(lid)
    return ids or None


def _text(msg: str) -> dict[str, Any]:
    return {"type": "text", "text": msg}


@tool(
    "start_candle_mode",
    "Start candle mode — a flickering, wind-blown candlelight simulation on "
    "one or more lights. Uses physics-based Perlin noise flicker with color "
    "shifts along the Planckian locus (1600K-2300K). Runs continuously until "
    "stopped. Optionally fades out over a duration. "
    "Call with no lights to target all lights.",
    {
        "type": "object",
        "properties": {
            "lights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Light names to put in candle mode. Empty/omit for all lights.",
            },
            "fade_out_minutes": {
                "type": "number",
                "description": "Gradually dim and turn off after this many minutes. 0 = run forever.",
            },
        },
    },
)
async def start_candle_mode_tool(args: dict[str, Any]) -> dict[str, Any]:
    lights = args.get("lights", [])
    fade = float(args.get("fade_out_minutes", 0))
    light_ids = _resolve_names(lights)
    label = ", ".join(lights) if lights else "all lights"
    fade_label = f", fading out over {int(fade)}min" if fade else ""
    try:
        await start_candle(light_ids, fade_out_minutes=fade)
        return _text(f"Candle mode started on {label}{fade_label}. Say 'stop' to end.")
    except Exception as e:
        return _text(f"Failed to start candle mode: {e}")


@tool(
    "start_breathing_mode",
    "Start breathing mode — a slow, gentle inhale/exhale glow on one or more "
    "lights. Deep amber (~1500K), soothing for winding down. Runs continuously "
    "until stopped. Call with no lights to target all lights.",
    {
        "type": "object",
        "properties": {
            "lights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Light names for breathing mode. Empty/omit for all lights.",
            },
        },
    },
)
async def start_breathing_mode_tool(args: dict[str, Any]) -> dict[str, Any]:
    lights = args.get("lights", [])
    light_ids = _resolve_names(lights)
    label = ", ".join(lights) if lights else "all lights"
    try:
        await start_breathe(light_ids)
        return _text(f"Breathing mode started on {label}. Say 'stop' to end.")
    except Exception as e:
        return _text(f"Failed to start breathing mode: {e}")


@tool(
    "stop_ambient_mode",
    "Stop any running ambient mode (candle, breathing). Restores lights to "
    "their previous state.",
    {"type": "object", "properties": {}},
)
async def stop_ambient_mode_tool(args: dict[str, Any]) -> dict[str, Any]:
    was_running = await stop_ambient()
    if was_running:
        return _text("Ambient mode stopped. Lights restored.")
    return _text("No ambient mode was running.")


ALL_AMBIENT_TOOLS = [
    start_candle_mode_tool,
    start_breathing_mode_tool,
    stop_ambient_mode_tool,
]
