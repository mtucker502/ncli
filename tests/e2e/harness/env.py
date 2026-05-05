"""Environment helpers for e2e test subprocesses.

Tests shell out to `ncli` and inherit the contributor's environment by default.
A stray `NCLI_BLOCK_CMD` / `NCLI_USERNAME` / etc. would silently change behavior
and surface as a flaky test. Use `clean_env()` to build a sanitized env (the
parent process's `os.environ` minus every `NCLI_*` key, plus optional
overrides) or `run_ncli()` to invoke a subprocess with that env automatically.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any


# Diagnostic NCLI_* env vars that subprocesses should inherit. Behavior knobs
# (NCLI_BLOCK_CMD, NCLI_USERNAME, ...) are still stripped to guard against
# contributor-shell leakage; pure-diagnostic capture vars are kept.
_NCLI_PASSTHROUGH = frozenset({"NCLI_SESSION_LOG_DIR"})


def clean_env(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Return os.environ with behavior-affecting NCLI_* stripped, then `overrides` merged in."""
    base = {
        k: v for k, v in os.environ.items()
        if not k.startswith("NCLI_") or k in _NCLI_PASSTHROUGH
    }
    if overrides:
        base.update(overrides)
    return base


def run_ncli(
    args: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """subprocess.run with NCLI_* scrubbed from env. Pass `env_overrides` for per-test additions."""
    return subprocess.run(args, env=clean_env(env_overrides), **kwargs)
