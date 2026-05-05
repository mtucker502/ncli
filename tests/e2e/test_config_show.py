"""End-to-end tests for `ncli config show`."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import device_with_netmiko_type
from tests.e2e.harness.env import run_ncli


@pytest.mark.clab
def test_config_show_returns_running_config(session_inventory, clab_session) -> None:
    for name in clab_session:
        proc = run_ncli(
            ["ncli", "-f", str(session_inventory), "config", "show", name],
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, f"{name}: {proc.stderr}"
        assert proc.stdout.strip(), f"{name}: empty config"


@pytest.mark.clab
@pytest.mark.parametrize("netmiko_type,section", [
    ("juniper_junos", "system"),
    ("arista_eos", "management"),
])
def test_config_show_section_filters(session_inventory, clab_session, netmiko_type, section) -> None:
    target = device_with_netmiko_type(clab_session, netmiko_type)
    if target is None:
        pytest.skip(f"no {netmiko_type} device in session")
    proc = run_ncli(
        ["ncli", "-f", str(session_inventory), "config", "show", target.name, section],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
