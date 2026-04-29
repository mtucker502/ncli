"""End-to-end coverage for `ncli command run`."""

from __future__ import annotations

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
