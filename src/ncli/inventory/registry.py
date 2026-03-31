from __future__ import annotations

from ncli.inventory.base import InventoryPlugin
from ncli.inventory.yaml_inventory import YamlInventory

_registry: dict[str, type[InventoryPlugin]] = {}


def register(name: str, plugin_class: type[InventoryPlugin]) -> None:
    _registry[name] = plugin_class


def get(name: str) -> type[InventoryPlugin]:
    if name not in _registry:
        raise KeyError(f"Inventory plugin '{name}' is not registered")
    return _registry[name]


# Default registrations
register("yaml", YamlInventory)
