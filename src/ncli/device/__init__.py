"""Device connection and configuration operations."""

from ncli.device.config_ops import config_diff, config_push
from ncli.device.connection import NetmikoConnection

__all__ = [
    "NetmikoConnection",
    "config_diff",
    "config_push",
]
