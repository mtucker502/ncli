"""End-to-end safety blocklist enforcement."""

from __future__ import annotations

import os
import subprocess

import pytest


@pytest.mark.clab
def test_blocked_exec_command_exit_2(session_inventory, clab_session, tmp_path) -> None:
    block_file = tmp_path / "block.cmd"
    block_file.write_text("^request system reboot\n")
    target = next((n for n in clab_session if "crpd" in n), next(iter(clab_session)))

    proc = subprocess.run(
        ["ncli", "-f", str(session_inventory), "command", "run", target, "request system reboot"],
        capture_output=True, text=True,
        env={**os.environ, "NCLI_BLOCK_CMD": str(block_file)},
        timeout=10,
    )
    assert proc.returncode == 2
    assert "Blocked" in (proc.stdout + proc.stderr)


@pytest.mark.clab
def test_blocked_config_line_exit_2(session_inventory, clab_session, tmp_path) -> None:
    block_file = tmp_path / "block.cfg"
    block_file.write_text("^delete\\b\n")
    target = next((n for n in clab_session if "crpd" in n), next(iter(clab_session)))

    cfg = tmp_path / "candidate.conf"
    cfg.write_text("delete system services ssh\n")

    proc = subprocess.run(
        ["ncli", "-f", str(session_inventory), "config", "push", target, str(cfg)],
        capture_output=True, text=True,
        env={**os.environ, "NCLI_BLOCK_CFG": str(block_file)},
        timeout=10,
    )
    assert proc.returncode == 2
    assert "Blocked" in (proc.stdout + proc.stderr)
