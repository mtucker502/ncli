from __future__ import annotations

import os
import re
from pathlib import Path


def load_blocklist(path: Path | None = None) -> list[re.Pattern]:
    if path is None or not path.is_file():
        return []

    patterns: list[re.Pattern] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(re.compile(line, re.IGNORECASE))
    return patterns


def check_command(cmd: str, blocklist: list[re.Pattern]) -> bool:
    return any(pattern.search(cmd) for pattern in blocklist)


def check_config(config_lines: list[str], blocklist: list[re.Pattern]) -> list[str]:
    return [line for line in config_lines if any(p.search(line) for p in blocklist)]


def get_command_blocklist() -> list[re.Pattern]:
    env = os.environ.get("NCLI_BLOCK_CMD")
    if env:
        return load_blocklist(Path(env))
    return []


def get_config_blocklist() -> list[re.Pattern]:
    env = os.environ.get("NCLI_BLOCK_CFG")
    if env:
        return load_blocklist(Path(env))
    return []
