"""Safety blocklist enforcement — runs without containerlab.

The blocklist short-circuits before any SSH attempt, so these tests use a
fake inventory pointing at TEST-NET-1 (RFC 5737) and never connect.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.e2e.harness.env import run_ncli


def _write_fake_inventory(path: Path) -> Path:
    doc = {
        "devices": {
            "fake1": {
                "host": "192.0.2.1",
                "port": 22,
                "device_type": "juniper_junos",
                "auth": {
                    "type": "password",
                    "username": "root",
                    "password": "clab123",
                },
            },
        },
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    path.chmod(0o600)
    return path


def test_blocked_exec_command_exit_2(tmp_path) -> None:
    inventory = _write_fake_inventory(tmp_path / "inventory.yaml")
    block_file = tmp_path / "block.cmd"
    block_file.write_text("^request system reboot\n")

    proc = run_ncli(
        ["ncli", "-f", str(inventory), "command", "run", "fake1", "request system reboot"],
        capture_output=True, text=True,
        env_overrides={"NCLI_BLOCK_CMD": str(block_file)},
        timeout=10,
    )
    assert proc.returncode == 2
    assert "Blocked" in (proc.stdout + proc.stderr)


def test_blocked_config_line_exit_2(tmp_path) -> None:
    inventory = _write_fake_inventory(tmp_path / "inventory.yaml")
    block_file = tmp_path / "block.cfg"
    block_file.write_text("^delete\\b\n")

    cfg = tmp_path / "candidate.conf"
    cfg.write_text("delete system services ssh\n")

    proc = run_ncli(
        ["ncli", "-f", str(inventory), "config", "push", "fake1", str(cfg)],
        capture_output=True, text=True,
        env_overrides={"NCLI_BLOCK_CFG": str(block_file)},
        timeout=10,
    )
    assert proc.returncode == 2
    assert "Blocked" in (proc.stdout + proc.stderr)
