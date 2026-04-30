"""Executor abstractions: local vs remote clab control plane.

A test invokes the harness only through fixtures, which call into one of:

  - LocalExecutor (Phase 4) — clab on this host, direct docker bridge IPs
  - RemoteExecutor (Phase 6) — clab over SSH, port-forwarded into pytest

Both expose the same interface: preflight, image probe, deploy, resolve to
endpoint, destroy, close.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from tests.e2e.harness.endpoint import DeviceEndpoint, Lab
from tests.e2e.harness.images import ImageProbe
from tests.e2e.harness.topology import Topology


class Executor(ABC):
    @abstractmethod
    def preflight(self) -> None:
        """Verify docker + clab + (for remote) SSH reachability. Raise on failure."""

    @property
    @abstractmethod
    def image_probe(self) -> ImageProbe:
        """An ImageProbe rooted at the executor host."""

    @abstractmethod
    def deploy(self, topology: Topology) -> Lab:
        """Materialize the topology on the executor host, return a Lab handle."""

    @abstractmethod
    def destroy(self, lab: Lab) -> None:
        """Tear down a previously deployed Lab. Idempotent."""

    @abstractmethod
    def resolve(self, lab: Lab, node_name: str) -> DeviceEndpoint:
        """Resolve a node name to an SSH-reachable DeviceEndpoint."""

    @abstractmethod
    def container_logs(self, container_name: str, tail: int = 200) -> str:
        """Best-effort `docker logs --tail <n>` against the executor host."""

    @abstractmethod
    def close(self) -> None:
        """Tear down per-executor resources (SSH masters, tunnels). Idempotent."""
