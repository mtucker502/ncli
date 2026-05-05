"""Probe whether a Docker image exists on the executor host.

`ImageProbe.local()` shells out to `docker image inspect` on the test host.
The remote variant is added in Phase 6.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tests.e2e.harness.ssh import SshMaster


@dataclass
class ImageProbe:
    """Returns whether a docker image exists on a host. Stateless."""
    _runner: Callable[[list[str]], int]

    def has_image(self, image_ref: str) -> bool:
        return self._runner(["docker", "image", "inspect", image_ref]) == 0

    @classmethod
    def local(cls) -> ImageProbe:
        def run(argv: list[str]) -> int:
            return subprocess.run(argv, capture_output=True).returncode
        return cls(_runner=run)

    @classmethod
    def over_ssh(cls, master: SshMaster) -> ImageProbe:
        def run(argv: list[str]) -> int:
            return master.run(argv).returncode
        return cls(_runner=run)
