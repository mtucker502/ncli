# Writing Inventory Plugins

NCLI's inventory system is pluggable. The built-in `YamlInventory` reads from YAML files, but you can implement custom inventory sources like NetBox, Ansible inventory, a database, or an API.

## The InventoryPlugin Interface

All inventory plugins extend `ncli.inventory.base.InventoryPlugin`:

```python
from abc import ABC, abstractmethod


class InventoryPlugin(ABC):
    @abstractmethod
    def load(self) -> dict[str, dict]:
        """Load devices from the inventory source.

        Returns a dict mapping device name to device config dict.
        Each device config must contain at least 'host' and 'device_type'.
        """
        ...

    @abstractmethod
    def save(self, devices: dict[str, dict]) -> None:
        """Persist the device inventory back to the source."""
        ...

    def get_groups(self) -> dict[str, list[str]]:
        """Return group definitions: {group_name: [device_names]}.

        Default implementation returns an empty dict.
        """
        return {}

    def get_defaults(self) -> dict:
        """Return default config values applied to all devices.

        Default implementation returns an empty dict.
        """
        return {}
```

## Device Config Contract

Each device dict returned by `load()` must contain:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `host` | str | Yes | Hostname or IP address |
| `device_type` | str | Yes | Valid Netmiko device type (validated against `CLASS_MAPPER_BASE`) |
| `port` | int | No | SSH/Telnet port |
| `timeout` | int | No | Connection timeout in seconds |
| `username` | str | No | Username |
| `auth` | dict | No | Auth block with `type`, `password`, `key_file`, `enable_secret` |
| `tags` | list[str] | No | Tags for filtering |

## Example: NetBox Inventory Plugin

```python
from ncli.inventory.base import InventoryPlugin
import requests


class NetBoxInventory(InventoryPlugin):
    def __init__(self, url: str, token: str, tag: str | None = None) -> None:
        self._url = url.rstrip("/")
        self._headers = {"Authorization": f"Token {token}"}
        self._tag = tag

    def load(self) -> dict[str, dict]:
        params = {}
        if self._tag:
            params["tag"] = self._tag

        resp = requests.get(
            f"{self._url}/api/dcim/devices/",
            headers=self._headers,
            params=params,
        )
        resp.raise_for_status()

        devices = {}
        for nb_device in resp.json()["results"]:
            name = nb_device["name"]
            primary_ip = nb_device["primary_ip"]["address"].split("/")[0]
            platform = nb_device.get("platform", {}).get("slug", "linux")

            devices[name] = {
                "host": primary_ip,
                "device_type": self._map_platform(platform),
                "tags": [t["slug"] for t in nb_device.get("tags", [])],
            }

        return devices

    def save(self, devices: dict[str, dict]) -> None:
        raise NotImplementedError("NetBox inventory is read-only")

    def get_groups(self) -> dict[str, list[str]]:
        # Could map NetBox sites or roles to groups
        return {}

    @staticmethod
    def _map_platform(slug: str) -> str:
        mapping = {
            "cisco-ios": "cisco_ios",
            "cisco-asa": "cisco_asa",
            "arista-eos": "arista_eos",
            "juniper-junos": "juniper_junos",
        }
        return mapping.get(slug, slug)
```

## Registering Your Plugin

Register your plugin with the inventory registry so it can be looked up by name:

```python
from ncli.inventory.registry import register
from my_plugins.netbox import NetBoxInventory

register("netbox", NetBoxInventory)
```

Retrieve it later:

```python
from ncli.inventory.registry import get

plugin_class = get("netbox")
inventory = plugin_class(url="https://netbox.example.com", token="abc123")
devices = inventory.load()
```

The built-in `YamlInventory` is registered as `"yaml"` by default.

## Validation

Use `ncli.device.validation.validate_device_config()` to validate devices returned by your plugin:

```python
from ncli.device.validation import validate_device_config

for name, config in devices.items():
    validate_device_config(name, config)
    # Raises ValueError if host or device_type is missing
    # Raises ValueError if device_type is not a valid Netmiko type
```

The `YamlInventory` calls this automatically during `load()`. Custom plugins should do the same.

## Tips

- Always validate `device_type` against Netmiko's supported types at load time
- If your source is read-only, raise `NotImplementedError` in `save()`
- Merge any defaults in `load()` before returning -- the consumer expects fully resolved configs
- Return stable device names as dict keys -- these are used throughout the CLI for targeting
