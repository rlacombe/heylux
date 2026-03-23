"""Tests for daemon startup failure detection in the CLI."""

import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from heylux.agent import _start_daemon, SOCKET_PATH, PID_FILE


@pytest.fixture(autouse=True)
def tmp_paths(tmp_path, monkeypatch):
    """Redirect socket/PID paths to a temp dir so tests don't touch real config."""
    sock = tmp_path / "lux.sock"
    pid = tmp_path / "lux.pid"
    monkeypatch.setattr("heylux.agent.SOCKET_PATH", sock)
    monkeypatch.setattr("heylux.agent.PID_FILE", pid)
    return sock, pid


@pytest.fixture
def mock_console(monkeypatch):
    """Capture console output."""
    console = MagicMock()
    monkeypatch.setattr("heylux.agent.console", console)
    return console


class TestStartDaemonFailFast:
    """_start_daemon should detect a crashed daemon process immediately."""

    def test_detects_crashed_daemon(self, tmp_paths, mock_console, tmp_path):
        """If the daemon process exits with an error, _start_daemon should
        report the failure immediately instead of waiting the full timeout."""
        sock, pid = tmp_paths
        log_path = tmp_path / "daemon.log"

        # Simulate a daemon that crashes immediately (exit code 1)
        fake_proc = MagicMock()
        fake_proc.poll.return_value = 1  # process already exited
        fake_proc.returncode = 1

        with (
            patch("heylux.agent._daemon_running", return_value=False),
            patch("heylux.agent.subprocess.Popen", return_value=fake_proc),
            patch("heylux.agent.Path.home", return_value=tmp_path),
            patch("heylux.agent.time.sleep") as mock_sleep,
        ):
            start = time.monotonic()
            _start_daemon()
            elapsed = time.monotonic() - start

        # Should NOT have waited the full 15 seconds
        assert elapsed < 2.0, f"_start_daemon took {elapsed:.1f}s — should fail fast"

        # Should report the exit code
        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "exited with code 1" in printed

    def test_succeeds_when_socket_appears(self, tmp_paths, mock_console, tmp_path):
        """If the socket appears, _start_daemon should report success."""
        sock, pid = tmp_paths

        fake_proc = MagicMock()
        call_count = 0

        def poll_side_effect():
            return None  # process still running

        def sleep_side_effect(_):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                sock.touch()  # simulate socket appearing after 1 second

        fake_proc.poll.side_effect = poll_side_effect

        with (
            patch("heylux.agent._daemon_running", return_value=False),
            patch("heylux.agent.subprocess.Popen", return_value=fake_proc),
            patch("heylux.agent.Path.home", return_value=tmp_path),
            patch("heylux.agent.time.sleep", side_effect=sleep_side_effect),
        ):
            _start_daemon()

        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "ready" in printed.lower()

    def test_skips_if_already_running(self, tmp_paths, mock_console):
        """If the daemon is already running, don't start a new one."""
        with patch("heylux.agent._daemon_running", return_value=True):
            _start_daemon()

        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "already running" in printed.lower()
