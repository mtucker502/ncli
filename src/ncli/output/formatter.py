from __future__ import annotations

import json
from enum import Enum
from pprint import pformat
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

_SENSITIVE_KEYS = frozenset({
    "password",
    "secret",
    "key",
    "private_key",
    "token",
    "auth_key",
    "community",
    "passphrase",
})


class OutputFormat(Enum):
    TEXT = "text"
    JSON = "json"
    XML = "xml"


def format_output(data: Any, fmt: OutputFormat = OutputFormat.TEXT) -> str:
    if fmt is OutputFormat.JSON:
        return json.dumps(data, indent=2, default=str)

    if fmt is OutputFormat.XML:
        return _to_xml(data)

    if isinstance(data, str):
        return data
    return pformat(data, width=120)


def format_device_list(devices: dict[str, dict], fmt: OutputFormat) -> str:
    sanitized = {name: _sanitize(info) for name, info in devices.items()}
    return format_output(sanitized, fmt)


def format_error(message: str, fmt: OutputFormat) -> str:
    if fmt is OutputFormat.JSON:
        return json.dumps({"error": message}, indent=2)
    if fmt is OutputFormat.XML:
        return _to_xml({"error": message})
    return f"ERROR: {message}"


# --- internal helpers --------------------------------------------------------

def _sanitize(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: "***" if _is_sensitive(k) else _sanitize(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_sanitize(item) for item in data]
    return data


def _is_sensitive(key: str) -> bool:
    lower = key.lower()
    return any(s in lower for s in _SENSITIVE_KEYS)


def _to_xml(data: Any, root_tag: str = "root") -> str:
    root = Element(root_tag)
    _build_xml(root, data)
    return tostring(root, encoding="unicode")


def _build_xml(parent: Element, data: Any) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            child = SubElement(parent, str(key))
            _build_xml(child, value)
    elif isinstance(data, list):
        for item in data:
            child = SubElement(parent, "item")
            _build_xml(child, item)
    else:
        parent.text = str(data) if data is not None else ""
