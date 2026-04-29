"""Smoke-test a Netmiko connection right after clab deploy.

Netmiko occasionally drops the first session a node accepts; this helper opens
and immediately closes a connection, retrying up to 3 times with 2-second
backoff. Catches the slow-but-recoverable case before any test does.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def smoke_test_connect(
    host: str, port: int, username: str, password: str, device_type: str
) -> None:
    """Open and immediately close a Netmiko session to ensure SSH auth works."""
    from netmiko import ConnectHandler  # noqa: PLC0415 — keep netmiko optional at module load

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            conn = ConnectHandler(
                device_type=device_type, host=host, port=port,
                username=username, password=password, conn_timeout=20,
            )
            conn.disconnect()
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("smoke connect attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2)
    raise RuntimeError(f"Netmiko connect failed after 3 attempts: {last_exc}")
