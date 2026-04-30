"""Shared fixtures for NCLI test suite."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ncli.auth.base import Credentials


def pytest_addoption(parser: pytest.Parser) -> None:
    # Registered at rootdir so `--clab-host` is recognized regardless of which
    # directory pytest is invoked from. Consumed by tests/e2e/conftest.py.
    parser.addoption(
        "--clab-host",
        default=None,
        help="Remote SSH host running containerlab; unset = local executor.",
    )


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
def tmp_inventory_path(tmp_path: Path) -> Path:
    """Create a temp YAML inventory file with sample devices."""
    inv_file = tmp_path / "inventory.yaml"
    inv_file.write_text(yaml.dump(SAMPLE_INVENTORY, default_flow_style=False, sort_keys=False))
    return inv_file


@pytest.fixture()
def sample_device_config() -> dict:
    """Return a device config dict with host, device_type, and auth block."""
    return {
        "host": "10.0.0.1",
        "device_type": "cisco_ios",
        "auth": {
            "type": "password",
            "username": "admin",
            "password": "p@ssw0rd",
        },
    }


@pytest.fixture()
def mock_credentials() -> Credentials:
    """Return a Credentials instance for testing."""
    return Credentials(
        username="testuser",
        password="testpass",
        key_file=None,
        use_ssh_agent=False,
        enable_secret="enablepw",
    )
