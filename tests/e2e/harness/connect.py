"""Smoke-test a Netmiko connection right after clab deploy.

Netmiko occasionally drops the first session a node accepts; this helper opens
a session, sends a vendor-appropriate cheap command to verify the CLI is fully
responsive (cEOS in particular accepts SSH while `EOS Warmup Service` is still
running, but the CLI lags behind), and retries with backoff until the per-vendor
budget is exhausted.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# Cheap, side-effect-free commands that fail fast if the CLI isn't fully up.
# Sending a real command ensures the SSH session can carry data, not just that
# the banner+auth+prompt-detection succeeded — cEOS in particular accepts
# connections during `EOS Warmup Service` startup but the CLI lags briefly.
_READY_CHECK_CMD: dict[str, str] = {
    "arista_eos": "show version",
    "juniper_junos": "show version",
    "nokia_srl": "info system information",
}


def _exercise_cli(conn, device_type: str) -> None:  # noqa: ANN001
    """Run a vendor-appropriate readiness command if one is registered."""
    cmd = _READY_CHECK_CMD.get(device_type)
    if cmd:
        conn.send_command(cmd, read_timeout=30)


def smoke_test_connect(
    host: str,
    port: int,
    username: str,
    password: str,
    device_type: str,
    *,
    retries: int = 3,
    backoff_s: float = 2.0,
) -> None:
    """Open a Netmiko session, exercise the CLI to confirm full readiness, then close."""
    from netmiko import ConnectHandler  # noqa: PLC0415 — keep netmiko optional at module load

    # paramiko logs the SSH-banner-read failure (ConnectionResetError +
    # multi-frame stack trace) at ERROR level on every banner-reset retry
    # during early cEOS warmup. The retries are expected and recoverable, so
    # the noise is misleading. Suppress paramiko.transport during the loop;
    # we still emit a single WARNING per attempt below.
    paramiko_log = logging.getLogger("paramiko.transport")
    prev_level = paramiko_log.level
    paramiko_log.setLevel(logging.CRITICAL)

    last_exc: Exception | None = None
    try:
        for attempt in range(retries):
            try:
                conn = ConnectHandler(
                    device_type=device_type, host=host, port=port,
                    username=username, password=password, conn_timeout=20,
                )
                try:
                    _exercise_cli(conn, device_type)
                finally:
                    conn.disconnect()
                if attempt > 0:
                    logger.info(
                        "smoke connect succeeded on attempt %d/%d (%s)",
                        attempt + 1, retries, device_type,
                    )
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "smoke connect attempt %d/%d failed: %s", attempt + 1, retries, exc
                )
                if attempt < retries - 1:
                    time.sleep(backoff_s)
    finally:
        paramiko_log.setLevel(prev_level)
    raise RuntimeError(f"Netmiko connect failed after {retries} attempts: {last_exc}")
