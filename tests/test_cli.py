"""Tests for CLI commands using Click's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from ncli.cli.main import cli


SAMPLE_INVENTORY = {
    "defaults": {
        "device_type": "cisco_asa",
        "auth": {
            "type": "password",
            "username": "admin",
            "password": "secret123",
        },
    },
    "devices": {
        "firewall1": {
            "host": "192.168.1.1",
        },
        "switch1": {
            "host": "192.168.1.2",
            "device_type": "arista_eos",
            "tags": ["core", "dc1"],
        },
        "router1": {
            "host": "192.168.1.3",
            "device_type": "cisco_ios",
            "tags": ["edge"],
        },
    },
    "groups": {
        "datacenter": ["firewall1", "switch1"],
        "edge": ["router1"],
    },
}


@pytest.fixture()
def inv_file(tmp_path: Path) -> Path:
    p = tmp_path / "inventory.yaml"
    p.write_text(yaml.dump(SAMPLE_INVENTORY, default_flow_style=False, sort_keys=False))
    return p


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestCLIGlobal:
    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "ncli" in result.output
        assert "0.1.0" in result.output

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Multi-vendor" in result.output or "NCLI" in result.output


class TestDeviceList:
    def test_device_list(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, ["-f", str(inv_file), "device", "list"])
        assert result.exit_code == 0
        assert "firewall1" in result.output
        assert "switch1" in result.output
        assert "router1" in result.output

    def test_device_list_json(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, ["-f", str(inv_file), "--json", "device", "list"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "firewall1" in parsed
        assert "switch1" in parsed

    def test_device_list_sanitizes_passwords(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, ["-f", str(inv_file), "--json", "device", "list"])
        assert result.exit_code == 0
        assert "secret123" not in result.output
        assert "***" in result.output

    def test_device_list_by_group(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, ["-f", str(inv_file), "--json", "device", "list", "--group", "datacenter"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "firewall1" in parsed
        assert "switch1" in parsed
        assert "router1" not in parsed

    def test_device_list_by_tag(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, ["-f", str(inv_file), "--json", "device", "list", "--tag", "edge"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "router1" in parsed
        assert "firewall1" not in parsed


class TestDeviceInfo:
    def test_device_info(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, ["-f", str(inv_file), "device", "info", "switch1"])
        assert result.exit_code == 0
        assert "switch1" in result.output
        assert "192.168.1.2" in result.output

    def test_device_info_unknown(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, ["-f", str(inv_file), "device", "info", "nonexistent"])
        assert result.exit_code != 0


class TestDeviceAdd:
    def test_device_add(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, [
            "-f", str(inv_file), "device", "add", "newdev",
            "--host", "10.10.10.10",
            "--device-type", "cisco_ios",
        ])
        assert result.exit_code == 0
        assert "Added device 'newdev'" in result.output

        # Verify it was saved
        raw = yaml.safe_load(inv_file.read_text())
        assert "newdev" in raw["devices"]

    def test_device_add_invalid_type(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, [
            "-f", str(inv_file), "device", "add", "baddev",
            "--host", "10.10.10.10",
            "--device-type", "not_real",
        ])
        assert result.exit_code != 0


class TestDeviceRemove:
    def test_device_remove_with_force(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, [
            "-f", str(inv_file), "device", "remove", "router1", "--force",
        ])
        assert result.exit_code == 0
        assert "Removed device 'router1'" in result.output

        raw = yaml.safe_load(inv_file.read_text())
        assert "router1" not in raw["devices"]

    def test_device_remove_nonexistent(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(cli, [
            "-f", str(inv_file), "device", "remove", "ghost", "--force",
        ])
        assert result.exit_code != 0

    def test_device_remove_prompt_abort(self, runner: CliRunner, inv_file: Path) -> None:
        result = runner.invoke(
            cli,
            ["-f", str(inv_file), "device", "remove", "router1"],
            input="n\n",
        )
        assert result.exit_code != 0
        # Device should still exist
        raw = yaml.safe_load(inv_file.read_text())
        assert "router1" in raw["devices"]
