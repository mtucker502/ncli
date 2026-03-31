"""High-level configuration operations for network devices."""

from __future__ import annotations

import difflib
import logging

from ncli.device.connection import NetmikoConnection

logger = logging.getLogger(__name__)

# Platforms whose Netmiko drivers expose a commit() method.
_COMMIT_PLATFORMS = frozenset({"junos", "arista_eos", "cisco_xr"})


def config_push(
    connection: NetmikoConnection,
    config_lines: list[str],
    *,
    dry_run: bool = False,
    comment: str | None = None,
) -> str:
    """Push configuration lines to a device.

    Parameters
    ----------
    connection:
        An active :class:`NetmikoConnection`.
    config_lines:
        Ordered configuration statements to apply.
    dry_run:
        When *True*, return the would-be config without touching the device.
    comment:
        Optional commit comment for platforms that support it.

    Returns
    -------
    str
        The device output (or the candidate config in dry-run mode).
    """
    if dry_run:
        logger.info(
            "Dry-run mode: returning candidate config for %s",
            connection.device_name,
        )
        return "\n".join(config_lines)

    output = connection.send_config(config_lines)

    device_type: str = connection.device_config.get("device_type", "")
    if device_type in _COMMIT_PLATFORMS:
        conn = connection._ensure_connected()  # noqa: SLF001
        logger.info("Committing configuration on %s", connection.device_name)
        commit_kwargs: dict = {}
        if comment:
            commit_kwargs["comment"] = comment
        output += "\n" + conn.commit(**commit_kwargs)

    return output


def config_diff(
    connection: NetmikoConnection,
    candidate: str | None = None,
) -> str:
    """Return a unified diff between the running config and a candidate.

    Parameters
    ----------
    connection:
        An active :class:`NetmikoConnection`.
    candidate:
        Candidate configuration text to compare against the running config.
        When *None*, an empty string is returned (nothing to compare).

    Returns
    -------
    str
        A unified-diff string, or an empty string when no candidate is given.
    """
    running = connection.get_config()

    if candidate is None:
        return ""

    running_lines = running.splitlines(keepends=True)
    candidate_lines = candidate.splitlines(keepends=True)

    diff = difflib.unified_diff(
        running_lines,
        candidate_lines,
        fromfile="running-config",
        tofile="candidate-config",
    )
    return "".join(diff)
