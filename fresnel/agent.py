"""Fresnel — A chronobiology-powered lighting agent for Philips Hue.

Usage:
    fresnel                          Interactive mode
    fresnel "make it cozy"           One-shot command
    fresnel circadian                Apply current circadian recommendation
    fresnel setup                    Guide Hue Bridge setup
"""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    create_sdk_mcp_server,
    query,
)
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

from fresnel.tools.circadian import get_circadian_recommendation
from fresnel.tools.hue import ALL_HUE_TOOLS
from fresnel.tools.memory import ALL_MEMORY_TOOLS, get_profile_context

load_dotenv()

console = Console()
BASE_SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

# Fresnel's custom tools as an in-process MCP server
fresnel_tools = create_sdk_mcp_server(
    name="fresnel",
    version="0.1.0",
    tools=[get_circadian_recommendation, *ALL_HUE_TOOLS, *ALL_MEMORY_TOOLS],
)


def _build_system_prompt() -> str:
    """Build system prompt with user profile injected if available."""
    profile_ctx = get_profile_context()
    if profile_ctx:
        return BASE_SYSTEM_PROMPT + "\n\n" + profile_ctx
    return BASE_SYSTEM_PROMPT


def _build_options() -> ClaudeAgentOptions:
    """Build the ClaudeAgentOptions with MCP servers and permissions."""
    return ClaudeAgentOptions(
        system_prompt=_build_system_prompt(),
        mcp_servers={"fresnel": fresnel_tools},
        allowed_tools=["mcp__fresnel__*"],
        permission_mode="acceptEdits",
        max_turns=10,
        # Isolate Fresnel from the user's Claude Code config/memories
        setting_sources=[],
    )


async def _run_query(prompt: str) -> None:
    """Run a single Fresnel query and stream the response."""
    options = _build_options()

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            mcp_status = message.data.get("mcp_servers", [])
            for server in mcp_status:
                if server.get("status") != "connected":
                    console.print(
                        f"[yellow]Warning: {server.get('name')} failed to connect[/yellow]"
                    )

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    console.print(Markdown(block.text))
                elif hasattr(block, "name"):
                    console.print(f"[dim]→ {block.name}[/dim]")

        elif isinstance(message, ResultMessage):
            if message.subtype != "success":
                console.print(f"[red]Error: {message.subtype}[/red]")


async def _interactive() -> None:
    """Run Fresnel in interactive mode."""
    console.print(
        "[bold]Fresnel[/bold] — your chronobiology-powered lighting assistant\n"
        "[dim]Type a command, or 'quit' to exit.[/dim]\n"
    )

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        console.print()
        await _run_query(user_input)
        console.print()


def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]

    if not args:
        asyncio.run(_interactive())
    elif args[0] == "circadian":
        asyncio.run(
            _run_query(
                "Check the current circadian recommendation and apply it to my lights. "
                "Tell me what you're setting and why."
            )
        )
    elif args[0] == "setup":
        asyncio.run(
            _run_query(
                "Help me set up my Philips Hue Bridge. Walk me through discovering "
                "the bridge on my network, pressing the link button, and verifying "
                "the connection. List all my lights when done."
            )
        )
    else:
        # Treat all args as a natural language prompt
        prompt = " ".join(args)
        asyncio.run(_run_query(prompt))


if __name__ == "__main__":
    main()
