"""Render a temp ncli inventory.yaml that points at resolved DeviceEndpoints."""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.e2e.harness.endpoint import DeviceEndpoint


def write_inventory(path: Path, endpoints: dict[str, DeviceEndpoint]) -> Path:
    """Create a temp inventory at `path` and return it.

    The shape mirrors the YAML schema described in docs/inventory-schema.md —
    each device has host, device_type, optional port, and an `auth` block.
    """
    devices: dict[str, dict] = {}
    for name, ep in endpoints.items():
        devices[name] = {
            "host": ep.host,
            "port": ep.port,
            "device_type": ep.device_type,
            "auth": {
                "type": "password",
                "username": ep.username,
                "password": ep.password,
            },
        }
    doc = {"devices": devices}
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    path.chmod(0o600)
    return path
