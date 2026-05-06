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
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 600
CONTROL_OP_TIMEOUT_S = 30


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
        # UNIX socket path max is 104 on macOS / 108 on Linux. macOS $TMPDIR
        # under /var/folders/<2>/<long-random>/T/ leaves almost no headroom
        # once the prefix and `cm-<8hex>` socket name are appended, so anchor
        # under /tmp (present on both platforms).
        self._socket_dir = tempfile.TemporaryDirectory(prefix="ne-ssh-", dir="/tmp")
        self._control_path = os.path.join(self._socket_dir.name, f"cm-{uuid.uuid4().hex[:8]}")
        assert len(self._control_path) < 100, (
            f"ssh ControlPath too long ({len(self._control_path)} bytes): "
            f"{self._control_path}"
        )

    @property
    def control_path(self) -> str:
        return self._control_path

    def base_args(self) -> list[str]:
        """Return the ssh argv prefix shared by every invocation against this master."""
        # ServerAliveInterval keeps the multiplexed master TCP connection from being
        # pruned by an idle middle-box during long e2e runs (issue #5). Without it,
        # all `-L` listeners die mid-suite and later netmiko connects get refused.
        args = [
            "ssh",
            "-o", f"ControlPath={self._control_path}",
            "-o", "ControlMaster=auto",
            "-o", "ControlPersist=60s",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
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

    def run(
        self, remote_cmd: list[str], *, timeout: float = DEFAULT_TIMEOUT_S
    ) -> subprocess.CompletedProcess[str]:
        """Run a command on the remote host. argv-style — no shell quoting needed."""
        argv = [*self.base_args(), "--", *remote_cmd]
        started = time.monotonic()
        try:
            return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            raise RuntimeError(
                f"ssh run timed out on {self.host} after {elapsed:.1f}s: argv={argv} "
                f"stdout={exc.stdout!r} stderr={exc.stderr!r}"
            ) from exc

    def run_with_stdin(
        self, remote_cmd: list[str], stdin: str, *, timeout: float = DEFAULT_TIMEOUT_S
    ) -> subprocess.CompletedProcess[str]:
        """Run a remote command with `stdin` piped in. Used to stage files via `cat > path`."""
        argv = [*self.base_args(), "--", *remote_cmd]
        started = time.monotonic()
        try:
            return subprocess.run(
                argv, input=stdin, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            raise RuntimeError(
                f"ssh run_with_stdin timed out on {self.host} after {elapsed:.1f}s: argv={argv} "
                f"stdout={exc.stdout!r} stderr={exc.stderr!r}"
            ) from exc

    def forward(self, local_port: int, remote_host: str, remote_port: int) -> None:
        """Open an L-style tunnel via the existing master."""
        argv = [*self.base_args(), "-O", "forward", "-L", f"{local_port}:{remote_host}:{remote_port}"]
        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=CONTROL_OP_TIMEOUT_S
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            raise RuntimeError(
                f"ssh forward timed out on {self.host} after {elapsed:.1f}s "
                f"({local_port}->{remote_host}:{remote_port}): "
                f"stdout={exc.stdout!r} stderr={exc.stderr!r}"
            ) from exc
        if proc.returncode != 0:
            raise RuntimeError(f"ssh forward failed ({local_port}->{remote_host}:{remote_port}): {proc.stderr}")
        self._tunnels.append((local_port, remote_host, remote_port))

    def cancel_forward(
        self, local_port: int, remote_host: str, remote_port: int
    ) -> subprocess.CompletedProcess[str]:
        """Tear down an L-style tunnel via the existing master.

        Best-effort: returns the CompletedProcess (or a synthetic one on
        timeout) rather than raising, so callers in cleanup paths can log
        and move on. The matching tuple is removed from `self._tunnels`
        if present, regardless of returncode.
        """
        argv = [
            *self.base_args(),
            "-O", "cancel",
            "-L", f"{local_port}:{remote_host}:{remote_port}",
        ]
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=CONTROL_OP_TIMEOUT_S
            )
        except subprocess.TimeoutExpired as exc:
            proc = subprocess.CompletedProcess(
                args=argv,
                returncode=255,
                stdout=exc.stdout or "",
                stderr=f"timeout after {CONTROL_OP_TIMEOUT_S}s",
            )
        try:
            self._tunnels.remove((local_port, remote_host, remote_port))
        except ValueError:
            pass
        return proc

    def check(self) -> tuple[bool, str]:
        """Probe whether the master is still alive via `ssh -O check`.

        Returns (alive, combined_output). Used for diagnostics when a tunneled
        connect fails — distinguishes a dead master from other failures.
        """
        argv = [*self.base_args(), "-O", "check"]
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=CONTROL_OP_TIMEOUT_S
            )
        except subprocess.TimeoutExpired:
            return False, "timeout"
        return proc.returncode == 0, (proc.stdout + proc.stderr).strip()

    def dump_state(self, dest: Path) -> None:
        """Write master diagnostics into `dest/` for failure-artifact collection."""
        dest.mkdir(parents=True, exist_ok=True)
        alive, output = self.check()
        lines = [
            f"host: {self.host}",
            f"user: {self.user}",
            f"port: {self.port}",
            f"control_path: {self._control_path}",
            f"control_path_exists: {os.path.exists(self._control_path)}",
            f"master_alive: {alive}",
            f"check_output: {output}",
            "tunnels:",
            *(f"  {lp} -> {rh}:{rp}" for lp, rh, rp in self._tunnels),
        ]
        (dest / "ssh_master.txt").write_text("\n".join(lines) + "\n")

    def close(self) -> None:
        argv = [*self.base_args(), "-O", "exit"]
        try:
            subprocess.run(argv, capture_output=True, text=True, timeout=CONTROL_OP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            pass
        self._socket_dir.cleanup()
