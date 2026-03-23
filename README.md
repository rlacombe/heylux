# Fiat-Lux

*"Let there be light."*

Meet **Lux** — a chronobiology-powered lighting agent for Philips Hue. Lux manages your lights for better focus, energy, and sleep, grounded in real photobiology research.

## Features

- **Instant commands** — "lights off", "bedtime", "focus", "brighter" execute directly (<1s)
- **Named routines** — "bedtime", "morning", "focus", "relax" — customizable through conversation
- **Natural language** — "make it Rilakkuma-colored", "sunset in my room" via Claude
- **Circadian automation** — time-based lighting grounded in melanopsin sensitivity and melatonin research
- **Calendar alerts** — breathing pulse on your desk lamp before meetings (amber at T-5min, blue at T-15s)
- **Persistent daemon** — boots once, stays warm, every command after that is fast
- **User memory** — Lux learns your name, room layout, sleep habits across sessions
- **Built-in Hue control** — no external MCP servers needed

## Architecture

Lux runs as a daemon with two execution paths:

```
User input → CLI
               │
               ├─ Shortcuts (regex + routines)  →  direct phue  < 1s
               │
               └─ Claude (persistent session)   →  tool calls   ~ 5s
```

**Shortcuts** pattern-match common commands and named routines, executing directly via phue. No LLM, no network latency.

**Claude** handles everything else via a persistent `ClaudeSDKClient` session. The daemon boots the Claude Code process once and keeps it warm — subsequent messages skip the cold start.

## Quickstart

```bash
git clone https://github.com/rlacombe/fiat-lux.git
cd fiat-lux
uv sync

# Start Lux
uv run lux start

# Talk to Lux
uv run lux "hello"
uv run lux setup          # guided Hue Bridge pairing
```

Requires a Claude Code subscription (Pro/Max). No API key needed if you're logged in.

To avoid typing `uv run` every time, create a symlink:

```bash
ln -s $(uv run which lux) ~/.local/bin/lux
```

Make sure `~/.local/bin` is in your `PATH`.

## Usage

```bash
# Daemon management
uv run lux start           # start the daemon
uv run lux stop            # stop it
uv run lux status          # check if running
uv run lux restart         # restart

# Interactive mode
uv run lux                 # REPL

# Instant shortcuts (< 1s)
uv run lux "lights off"
uv run lux "lights on"
uv run lux "brighter"
uv run lux "dimmer"
uv run lux "50%"
uv run lux "circadian"

# Routines (< 1s, customizable)
uv run lux "bedtime"       # nightstand + lantern, warm
uv run lux "morning"       # ceiling + desk, cool bright
uv run lux "focus"         # ceiling + desk, peak alertness
uv run lux "reading"       # nightstand + desk, warm white
uv run lux "relax"         # lantern + nightstand, low amber
uv run lux "goodnight"     # everything off
uv run lux "routines"      # list all routines

# Natural language (~ 5s, via Claude)
uv run lux "make it cozy"
uv run lux "sunset in my room"
uv run lux "update my bedtime routine to keep the lantern on"
```

## Configuration

Lux stores everything in `~/.config/fiat_lux/`:

| File | Purpose |
|---|---|
| `hue.json` | Bridge IP and API credentials |
| `user.json` | User profile and preferences |
| `routines.json` | Named lighting presets |
| `calendars.json` | Calendars to monitor for meeting alerts |
| `lux.sock` | Daemon Unix socket |
| `daemon.log` | Daemon log output |

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A Philips Hue Bridge + Hue bulbs
- Claude Code subscription (Pro or Max plan)

## License

MIT
