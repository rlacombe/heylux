# Fresnel

A chronobiology-powered lighting agent for Philips Hue, built with the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents/claude-agent-sdk).

Fresnel is a CLI agent that manages your Philips Hue lights based on circadian science. It knows when to energize you with cool bright light, when to wind you down with warm amber, and how to protect your sleep — all backed by real photobiology research.

Named after [Augustin-Jean Fresnel](https://en.wikipedia.org/wiki/Augustin-Jean_Fresnel), who revolutionized our understanding of light.

## Features

- **Circadian automation** — time-based lighting recommendations grounded in melanopsin sensitivity, melatonin suppression, and cortisol regulation
- **Natural language control** — "make it cozy", "I need to focus", "wind me down for bed"
- **Built-in Hue control** — no external MCP servers needed. Bridge pairing, light/group/scene control all built in
- **User memory** — learns your name, room layout, sleep habits, and preferences across sessions
- **Scientist persona** — Fresnel explains *why* certain light matters, not just what to set

## Quickstart

```bash
# Clone and install
git clone https://github.com/rlacombe/fresnel.git
cd fresnel
uv sync

# Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run
uv run fresnel
```

On first launch, Fresnel will introduce itself and guide you through pairing your Hue Bridge.

## Usage

```bash
# Interactive mode
uv run fresnel

# One-shot commands
uv run fresnel "set my lights for right now"
uv run fresnel "I need to focus for 2 hours"
uv run fresnel "wind me down for bed"

# Built-in shortcuts
uv run fresnel circadian    # Apply current circadian recommendation
uv run fresnel setup        # Guided Hue Bridge setup
```

## How it works

Fresnel combines three layers:

1. **Circadian engine** — a time-based curve with 12 waypoints covering pre-dawn through deep night, interpolating color temperature (2000K-6500K) and brightness based on the current time
2. **Hue control** — direct bridge communication via [phue](https://github.com/studioimaginaire/phue) for lights, groups, and scenes
3. **Claude agent** — the Claude Agent SDK provides natural language understanding, tool orchestration, and conversational memory

All tools run as an in-process MCP server — no subprocesses, no external dependencies beyond the Hue Bridge itself.

## Configuration

Fresnel stores its config in `~/.config/fresnel/`:
- `hue.json` — Bridge IP and API credentials (created during setup)
- `user.json` — Your profile and preferences (built up through conversation)

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An Anthropic API key
- A Philips Hue Bridge + Hue bulbs

## License

MIT
