"""Ssh multiplexing + local port-forward helpers.

We use OpenSSH ControlMaster — one TCP connection to the remote host, every
subsequent ssh/scp call rides on the same socket. Tunnels are set up by
re-issuing the ssh client with `-O forward` against the master.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def alloc_local_port() -> int:
    """Bind to port 0, read back the OS-allocated port, release it."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@dataclass
class SshMaster:
    """A multiplexed SSH connection to a single remote host."""
    host: str
    user: str | None = None
    port: int = 22
    _socket_dir: tempfile.TemporaryDirectory = field(init=False)
    _tunnels: list[tuple[int, str, int]] = field(default_factory=list, init=False)
    _control_path: str = field(init=False)

    def __post_init__(self) -> None:
        self._socket_dir = tempfile.TemporaryDirectory(prefix="ncli-e2e-ssh-")
        self._control_path = os.path.join(self._socket_dir.name, f"cm-{uuid.uuid4().hex[:8]}")

    @property
    def control_path(self) -> str:
        return self._control_path

    def base_args(self) -> list[str]:
        """Return the ssh argv prefix shared by every invocation against this master."""
        args = [
            "ssh",
            "-o", f"ControlPath={self._control_path}",
            "-o", "ControlMaster=auto",
            "-o", "ControlPersist=60s",
            "-o", "StrictHostKeyChecking=accept-new",
            "-p", str(self.port),
        ]
        if self.user:
            return [*args, f"{self.user}@{self.host}"]
        return [*args, self.host]

    def open(self) -> None:
        # Force the master open by running a no-op
        proc = subprocess.run([*self.base_args(), "true"], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ssh master open failed: {proc.stderr}")

    def run(self, remote_cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a command on the remote host. argv-style — no shell quoting needed."""
        argv = [*self.base_args(), "--", *remote_cmd]
        return subprocess.run(argv, capture_output=True, text=True)

    def run_with_stdin(self, remote_cmd: list[str], stdin: str) -> subprocess.CompletedProcess[str]:
        """Run a remote command with `stdin` piped in. Used to stage files via `cat > path`."""
        argv = [*self.base_args(), "--", *remote_cmd]
        return subprocess.run(argv, input=stdin, capture_output=True, text=True)

    def forward(self, local_port: int, remote_host: str, remote_port: int) -> None:
        """Open an L-style tunnel via the existing master."""
        argv = [*self.base_args(), "-O", "forward", "-L", f"{local_port}:{remote_host}:{remote_port}"]
        proc = subprocess.run(argv, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ssh forward failed ({local_port}->{remote_host}:{remote_port}): {proc.stderr}")
        self._tunnels.append((local_port, remote_host, remote_port))

    def close(self) -> None:
        argv = [*self.base_args(), "-O", "exit"]
        subprocess.run(argv, capture_output=True, text=True)
        self._socket_dir.cleanup()
