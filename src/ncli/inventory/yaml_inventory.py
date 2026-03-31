from __future__ import annotations

from pathlib import Path

import yaml

from ncli.device.validation import validate_device_config
from ncli.inventory.base import InventoryPlugin


class YamlInventory(InventoryPlugin):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._raw: dict = {}

    def load(self) -> dict[str, dict]:

        with open(self._path) as f:
            self._raw = yaml.safe_load(f) or {}

        defaults = self._raw.get("defaults", {})
        devices: dict[str, dict] = {}

        for name, config in self._raw.get("devices", {}).items():
            merged = {**defaults, **config}
            validate_device_config(name, merged)
            devices[name] = merged

        return devices

    def save(self, devices: dict[str, dict]) -> None:
        self._raw["devices"] = devices
        with open(self._path, "w") as f:
            yaml.dump(self._raw, f, default_flow_style=False, sort_keys=False)

    def get_groups(self) -> dict[str, list[str]]:
        return self._raw.get("groups", {})

    def get_defaults(self) -> dict:
        return self._raw.get("defaults", {})
