from __future__ import annotations

from ncli.auth.base import AuthPlugin
from ncli.auth.static import StaticAuth

_registry: dict[str, type[AuthPlugin]] = {}


def register(name: str, plugin_class: type[AuthPlugin]) -> None:
    _registry[name] = plugin_class


def get(name: str) -> type[AuthPlugin]:
    if name not in _registry:
        raise KeyError(f"Auth plugin '{name}' is not registered")
    return _registry[name]


# Default registrations
register("static", StaticAuth)
