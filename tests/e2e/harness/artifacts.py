"""Dump diagnostic info on test failure under -m clab."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from tests.e2e.harness.endpoint import Lab


def dump_failure(lab: Lab, dest: Path) -> None:
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
        logs = subprocess.run(
            ["docker", "logs", "--tail", "200", cname],
            capture_output=True, text=True,
        )
        (dest / f"{cname}.log").write_text(logs.stdout + "\n--- stderr ---\n" + logs.stderr)
