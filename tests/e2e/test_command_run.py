"""End-to-end coverage for `ncli command run`."""

from __future__ import annotations

import json
import subprocess

import pytest


@pytest.mark.clab
def test_show_version_runs_against_session_devices(session_inventory, clab_session) -> None:
    """`ncli command run <dev> "show version"` exits 0 with non-empty output, every vendor."""
    for name in clab_session:
        proc = subprocess.run(
            ["ncli", "-f", str(session_inventory), "command", "run", name, "show version"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"{name}: rc={proc.returncode} stderr={proc.stderr!r}"
        assert proc.stdout.strip(), f"{name}: empty stdout"


@pytest.mark.clab
def test_command_run_json_envelope(session_inventory, clab_session) -> None:
    name = next(iter(clab_session))
    proc = subprocess.run(
        ["ncli", "-j", "-f", str(session_inventory), "command", "run", name, "show version"],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    json.loads(proc.stdout)  # raises if invalid


@pytest.mark.clab
def test_command_multi_runs_n_commands(session_inventory, clab_session) -> None:
    name = next(iter(clab_session))
    proc = subprocess.run(
        ["ncli", "-f", str(session_inventory), "command", "multi", name, "show version", "show clock"],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert "show version" in proc.stdout
    assert "show clock" in proc.stdout


@pytest.mark.clab
def test_command_batch_across_devices(session_inventory, clab_session) -> None:
    proc = subprocess.run(
        ["ncli", "-f", str(session_inventory), "command", "batch", "show version", *clab_session.keys()],
        capture_output=True, text=True, timeout=240,
    )
    assert proc.returncode == 0, proc.stderr
    for name in clab_session:
        assert f"--- {name} ---" in proc.stdout


@pytest.mark.clab
def test_command_run_unknown_device(session_inventory) -> None:
    proc = subprocess.run(
        ["ncli", "-f", str(session_inventory), "command", "run", "no-such-device", "show version"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 1
    assert "not found" in proc.stderr.lower()
