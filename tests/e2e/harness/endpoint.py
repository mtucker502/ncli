"""Device endpoint and deployed-lab dataclasses.

`DeviceEndpoint` is the only object tests touch — they get a tuple of
(host, port, username, password, device_type) regardless of whether the lab
is local or tunneled over SSH.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceEndpoint:
    name: str               # node name from the topology
    host: str               # IP or 127.0.0.1 for tunneled
    port: int               # 22 for local, allocated port for tunneled
    username: str
    password: str
    device_type: str        # netmiko device_type


@dataclass
class Lab:
    """Handle returned by Executor.deploy(); opaque to tests."""
    name: str
    topology_yaml_path: str  # path on the executor host
    inspect_raw: dict        # parsed `clab inspect --format json` for cleanup
