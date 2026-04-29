"""Wait for an SSH port to become reachable.

clab reports a node as `running` before SSH is reachable, especially for cEOS.
We probe the TCP port directly with exponential backoff.
"""

from __future__ import annotations

import socket
import time

DEFAULT_DELAYS = (1, 2, 4, 8, 16, 32)  # cumulative ~63s


def wait_ssh_open(host: str, port: int, *, deadline_s: float, delays: tuple[int, ...] = DEFAULT_DELAYS) -> bool:
    """Return True once `host:port` accepts a TCP connection, False on timeout."""
    started = time.monotonic()
    delay_iter = iter(delays)
    while time.monotonic() - started < deadline_s:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        try:
            time.sleep(next(delay_iter))
        except StopIteration:
            time.sleep(8)
    return False
