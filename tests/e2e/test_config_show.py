"""End-to-end tests for `ncli config show`."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.clab
def test_config_show_returns_running_config(session_inventory, clab_session) -> None:
    for name in clab_session:
        proc = subprocess.run(
            ["ncli", "-f", str(session_inventory), "config", "show", name],
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, f"{name}: {proc.stderr}"
        assert proc.stdout.strip(), f"{name}: empty config"


@pytest.mark.clab
@pytest.mark.parametrize("name_filter,section", [
    # Junos `show configuration system` is a sensible section probe.
    ("crpd", "system"),
    # Arista cEOS `show running-config | section management`.
    ("ceos", "management"),
])
def test_config_show_section_filters(session_inventory, clab_session, name_filter, section) -> None:
    target = next((n for n in clab_session if name_filter in n), None)
    if target is None:
        pytest.skip(f"no {name_filter} device in session")
    proc = subprocess.run(
        ["ncli", "-f", str(session_inventory), "config", "show", target, section],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
