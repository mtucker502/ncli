"""End-to-end tests for `ncli device` commands."""

from __future__ import annotations

import json
import subprocess

import pytest


@pytest.mark.clab
def test_device_list_shows_session_devices(session_inventory, clab_session) -> None:
    proc = subprocess.run(
        ["ncli", "-f", str(session_inventory), "device", "list"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    for name in clab_session:
        assert name in proc.stdout


@pytest.mark.clab
def test_device_info_masks_password(session_inventory, clab_session) -> None:
    name = next(iter(clab_session))
    proc = subprocess.run(
        ["ncli", "-j", "-f", str(session_inventory), "device", "info", name],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert "***" in json.dumps(payload), f"password not masked: {proc.stdout}"


@pytest.mark.clab
def test_device_add_then_remove_round_trip(session_inventory, clab_session) -> None:
    extra = "scratch1"
    add = subprocess.run(
        ["ncli", "-f", str(session_inventory), "device", "add", extra,
         "--host", "10.255.255.1", "--device-type", "cisco_ios", "--username", "x", "--password", "y"],
        capture_output=True, text=True,
    )
    assert add.returncode == 0, add.stderr

    listed = subprocess.run(
        ["ncli", "-f", str(session_inventory), "device", "list"],
        capture_output=True, text=True,
    )
    assert extra in listed.stdout

    remove = subprocess.run(
        ["ncli", "-f", str(session_inventory), "device", "remove", extra, "--force"],
        capture_output=True, text=True,
    )
    assert remove.returncode == 0, remove.stderr

    listed2 = subprocess.run(
        ["ncli", "-f", str(session_inventory), "device", "list"],
        capture_output=True, text=True,
    )
    assert extra not in listed2.stdout
