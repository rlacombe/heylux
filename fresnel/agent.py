"""Fresnel CLI — thin client that talks to the Fresnel daemon.

Usage:
    fresnel                          Interactive mode
    fresnel "make it cozy"           One-shot command
    fresnel start                    Start the daemon
    fresnel stop                     Stop the daemon
    fresnel status                   Check daemon status
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

load_dotenv()

console = Console()

SOCKET_PATH = Path.home() / ".config" / "fresnel" / "fresnel.sock"
PID_FILE = Path.home() / ".config" / "fresnel" / "fresnel.pid"


def _daemon_running() -> bool:
    """Check if the daemon is alive."""
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # signal 0 = check if process exists
        return True
    except (ProcessLookupError, ValueError):
        # Stale PID file
        PID_FILE.unlink(missing_ok=True)
        return False


def _start_daemon() -> None:
    """Start the daemon in the background."""
    if _daemon_running():
        console.print("[dim]Daemon already running.[/dim]")
        return

    console.print("[dim]Starting Lux daemon...[/dim]")

    # Start daemon as a background process
    log_path = Path.home() / ".config" / "fresnel" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a")

    subprocess.Popen(
        [sys.executable, "-m", "fresnel.daemon"],
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )

    # Wait for socket to appear
    for _ in range(30):
        if SOCKET_PATH.exists():
            console.print("[dim]Lux is ready.[/dim]")
            return
        time.sleep(0.5)

    console.print("[red]Lux failed to start. Check ~/.config/fresnel/daemon.log[/red]")


def _stop_daemon() -> None:
    """Stop the daemon."""
    if not _daemon_running():
        console.print("[dim]Daemon not running.[/dim]")
        return

    pid = int(PID_FILE.read_text().strip())
    os.kill(pid, signal.SIGTERM)
    console.print("[dim]Daemon stopped.[/dim]")


async def _send_to_daemon(prompt: str) -> None:
    """Send a prompt to the daemon and stream the response."""
    reader, writer = await asyncio.open_unix_connection(str(SOCKET_PATH))

    writer.write(json.dumps({"prompt": prompt}).encode() + b"\n")
    await writer.drain()

    while True:
        line = await reader.readline()
        if not line:
            break

        msg = json.loads(line.decode())

        if msg["type"] == "text":
            console.print(Markdown(msg["text"]))
        elif msg["type"] == "tool":
            console.print(f"[dim]→ {msg['name']}[/dim]")
        elif msg["type"] == "error":
            console.print(f"[red]Error: {msg['text']}[/red]")
        elif msg["type"] == "done":
            break

    writer.close()
    await writer.wait_closed()


def _send(prompt: str) -> None:
    """Send a prompt, auto-starting the daemon if needed."""
    if not _daemon_running():
        _start_daemon()

    try:
        asyncio.run(_send_to_daemon(prompt))
    except (ConnectionRefusedError, FileNotFoundError):
        console.print("[yellow]Connection lost. Restarting daemon...[/yellow]")
        _start_daemon()
        asyncio.run(_send_to_daemon(prompt))


def _interactive() -> None:
    """Interactive REPL — all messages go through the daemon."""
    if not _daemon_running():
        _start_daemon()

    console.print(
        "[bold]Lux[/bold] — your chronobiology-powered lighting assistant\n"
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
        _send(user_input)
        console.print()


def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]

    if not args:
        _interactive()
    elif args[0] == "start":
        _start_daemon()
    elif args[0] == "stop":
        _stop_daemon()
    elif args[0] == "status":
        if _daemon_running():
            pid = PID_FILE.read_text().strip()
            console.print(f"[green]Daemon running (pid {pid})[/green]")
        else:
            console.print("[yellow]Daemon not running[/yellow]")
    elif args[0] == "restart":
        _stop_daemon()
        time.sleep(1)
        _start_daemon()
    else:
        prompt = " ".join(args)
        _send(prompt)


if __name__ == "__main__":
    main()
