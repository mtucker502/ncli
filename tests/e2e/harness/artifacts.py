"""Dump diagnostic info on test failure under -m clab."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tests.e2e.harness.endpoint import Lab
from tests.e2e.harness.executor import Executor


def dump_failure(executor: Executor, lab: Lab, dest: Path) -> None:
    """Write clab inspect, docker logs, and topology YAML into `dest/`."""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "lab.json").write_text(json.dumps(lab.inspect_raw, indent=2))

    # Topology YAML — local executor's path is on this host; remote needs a fetch.
    yaml_path = Path(lab.topology_yaml_path)
    if yaml_path.is_file():
        shutil.copy2(yaml_path, dest / yaml_path.name)

    # Per-container docker logs (best-effort, last 200 lines).
    containers = lab.inspect_raw.get("containers") or []
    if not containers and lab.name in lab.inspect_raw:
        containers = lab.inspect_raw[lab.name]
    for c in containers:
        cname = c.get("name") or c.get("Name", "")
        if not cname:
            continue
        try:
            logs = executor.container_logs(cname)
        except Exception as exc:  # noqa: BLE001
            logs = f"<container_logs failed: {exc!r}>"
        (dest / f"{cname}.log").write_text(logs)

    # Executor-level diagnostics (RemoteExecutor: SSH master state + tunnels).
    # Distinguishes a dead control master from other failures (issue #5).
    dump_diag = getattr(executor, "dump_diagnostics", None)
    if callable(dump_diag):
        try:
            dump_diag(dest)
        except Exception as exc:  # noqa: BLE001
            (dest / "diagnostics-error.txt").write_text(repr(exc))
