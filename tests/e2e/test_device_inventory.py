"""End-to-end tests for `ncli device` commands."""

from __future__ import annotations

import json

import pytest

from tests.e2e.harness.env import run_ncli


@pytest.mark.clab
def test_device_list_shows_session_devices(session_inventory, clab_session) -> None:
    proc = run_ncli(
        ["ncli", "-f", str(session_inventory), "device", "list"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0
    for name in clab_session:
        assert name in proc.stdout


@pytest.mark.clab
def test_device_info_masks_password(session_inventory, clab_session) -> None:
    name = next(iter(clab_session))
    proc = run_ncli(
        ["ncli", "-j", "-f", str(session_inventory), "device", "info", name],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert "***" in json.dumps(payload), f"password not masked: {proc.stdout}"


@pytest.mark.clab
def test_device_add_then_remove_round_trip(session_inventory, clab_session) -> None:
    extra = "scratch1"
    add = run_ncli(
        ["ncli", "-f", str(session_inventory), "device", "add", extra,
         "--host", "10.255.255.1", "--device-type", "cisco_ios", "--username", "x", "--password", "y"],
        capture_output=True, text=True, timeout=30,
    )
    assert add.returncode == 0, add.stderr

    listed = run_ncli(
        ["ncli", "-f", str(session_inventory), "device", "list"],
        capture_output=True, text=True, timeout=30,
    )
    assert extra in listed.stdout

    remove = run_ncli(
        ["ncli", "-f", str(session_inventory), "device", "remove", extra, "--force"],
        capture_output=True, text=True, timeout=30,
    )
    assert remove.returncode == 0, remove.stderr

    listed2 = run_ncli(
        ["ncli", "-f", str(session_inventory), "device", "list"],
        capture_output=True, text=True, timeout=30,
    )
    assert extra not in listed2.stdout
