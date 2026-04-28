"""Netmiko-based device connection management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from netmiko import ConnectHandler

from ncli.auth.base import Credentials

if TYPE_CHECKING:
    from netmiko import BaseConnection
    from typing_extensions import Self

logger = logging.getLogger(__name__)

# Patterns that typically indicate a command-level error on network devices.
_ERROR_PATTERNS = (
    "% Invalid input",
    "% Ambiguous command",
    "% Incomplete command",
    "Error:",
)

_JUNOS_PLATFORMS = frozenset({"junos", "juniper", "juniper_junos"})


class NetmikoConnection:
    """Wrapper around a Netmiko connection with context-manager support.

    Parameters
    ----------
    device_name:
        A human-friendly name used in log messages.
    device_config:
        Dictionary that **must** contain ``device_type`` and ``host``.
        May also contain ``port`` and ``timeout`` overrides.
    credentials:
        A :class:`~ncli.auth.base.Credentials` instance.
    """

    def __init__(
        self,
        device_name: str,
        device_config: dict,
        credentials: Credentials,
    ) -> None:
        self.device_name = device_name
        self.device_config = device_config
        self.credentials = credentials
        self.net_connect: BaseConnection | None = None

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.disconnect()

    # -- Lifecycle ----------------------------------------------------------

    def connect(self) -> None:
        """Establish the SSH/Telnet session via Netmiko."""
        params: dict = {
            "device_type": self.device_config["device_type"],
            "host": self.device_config["host"],
            "username": self.credentials.username,
        }

        if self.credentials.password:
            params["password"] = self.credentials.password

        if self.credentials.enable_secret:
            params["secret"] = self.credentials.enable_secret

        if self.credentials.key_file:
            params["key_file"] = self.credentials.key_file
            params["use_keys"] = True

        if self.credentials.use_ssh_agent:
            params["use_keys"] = True
            params["allow_agent"] = True

        if "port" in self.device_config:
            params["port"] = self.device_config["port"]

        if "timeout" in self.device_config:
            params["timeout"] = self.device_config["timeout"]
            params["conn_timeout"] = self.device_config["timeout"]

        if "disabled_algorithms" in self.device_config:
            params["disabled_algorithms"] = self.device_config["disabled_algorithms"]

        logger.info("Connecting to %s (%s)", self.device_name, params["host"])
        self.net_connect = ConnectHandler(**params)
        logger.info("Connected to %s", self.device_name)

    def disconnect(self) -> None:
        """Gracefully tear down the session."""
        if self.net_connect is not None:
            logger.info("Disconnecting from %s", self.device_name)
            try:
                self.net_connect.disconnect()
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Non-fatal error during disconnect from %s",
                    self.device_name,
                    exc_info=True,
                )
            finally:
                self.net_connect = None

    # -- Command helpers ----------------------------------------------------

    def _ensure_connected(self) -> BaseConnection:
        if self.net_connect is None:
            raise RuntimeError(
                f"Not connected to {self.device_name}. "
                "Call connect() or use as a context manager."
            )
        return self.net_connect

    def send_command(self, cmd: str, *, textfsm: bool = False) -> str:
        """Send a single show-style command and return its output.

        Parameters
        ----------
        cmd:
            The command string to execute.
        textfsm:
            If *True*, attempt structured parsing via TextFSM / ntc-templates.
            Falls back to raw output when the templates are unavailable.
        """
        conn = self._ensure_connected()

        if textfsm:
            try:
                output = conn.send_command(cmd, use_textfsm=True)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "TextFSM parsing failed for '%s' on %s; "
                    "falling back to raw output",
                    cmd,
                    self.device_name,
                    exc_info=True,
                )
                output = conn.send_command(cmd)
        else:
            output = conn.send_command(cmd)

        return output if isinstance(output, str) else str(output)

    def send_commands(
        self,
        cmds: list[str],
        *,
        stop_on_error: bool = False,
    ) -> list[str]:
        """Send multiple show-style commands sequentially.

        Parameters
        ----------
        cmds:
            Ordered list of commands.
        stop_on_error:
            When *True*, stop executing further commands if the output of
            any command matches a known error pattern.
        """
        conn = self._ensure_connected()
        results: list[str] = []

        for cmd in cmds:
            output: str = conn.send_command(cmd)
            results.append(output)

            if stop_on_error and any(pat in output for pat in _ERROR_PATTERNS):
                logger.warning(
                    "Error detected in output of '%s' on %s; "
                    "stopping remaining commands",
                    cmd,
                    self.device_name,
                )
                break

        return results

    def send_config(self, config_lines: list[str]) -> str:
        """Push configuration commands via ``send_config_set``."""
        conn = self._ensure_connected()
        output: str = conn.send_config_set(config_lines)
        return output

    def get_config(self, section: str | None = None) -> str:
        """Retrieve the running configuration.

        Parameters
        ----------
        section:
            Optional section filter. Cisco-style: ``"interface"`` becomes
            ``| section interface``. Junos-style: ``"system services"``
            becomes ``show configuration system services``.
        """
        conn = self._ensure_connected()

        device_type = self.device_config.get("device_type", "")

        if device_type in _JUNOS_PLATFORMS:
            base = "show configuration"
            if section:
                base = f"{base} {section}"
            cmd = f"{base} | display set | no-more"
        else:
            cmd = "show running-config"
            if section:
                cmd = f"{cmd} | section {section}"

        output: str = conn.send_command(cmd)
        return output
