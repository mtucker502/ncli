from __future__ import annotations

from abc import ABC, abstractmethod


class InventoryPlugin(ABC):
    @abstractmethod
    def load(self) -> dict[str, dict]:
        ...

    @abstractmethod
    def save(self, devices: dict[str, dict]) -> None:
        ...

    def get_groups(self) -> dict[str, list[str]]:
        return {}

    def get_defaults(self) -> dict:
        return {}
