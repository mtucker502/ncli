"""Netmiko-based device connection management."""

from __future__ import annotations

import logging
import os
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
_SRL_PLATFORMS = frozenset({"nokia_srl"})
# Cisco-style CLIs that respond to `show running-config [| section <name>]`.
_CISCO_LIKE_PLATFORMS = frozenset(
    {
        "cisco_ios",
        "cisco_xe",
        "cisco_nxos",
        "cisco_asa",
        "cisco_xr",
        "cisco_iosxr",
        "arista_eos",
    }
)


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

        # cEOS's Netmiko driver matches the post-config-mode prompt with
        # `read_until_pattern`, whose default 10s budget is too tight on
        # SSH-forwarded sessions to a busy clab host: `configure terminal`
        # echoes back, but the new `(config)#` prompt arrives later than 10s
        # and config_mode() raises ReadTimeout. Bump the per-call read budget.
        if self.device_config["device_type"] == "arista_eos":
            params.setdefault("read_timeout_override", 60.0)

        # Optional Netmiko session log path (raw on-the-wire capture). Useful
        # for diagnosing prompt-detection / read-pattern failures. Set via
        # device_config["session_log"] or env var NCLI_SESSION_LOG_DIR (a per-
        # device file `<dir>/<device_name>.log` is written).
        log_dir = os.environ.get("NCLI_SESSION_LOG_DIR")
        if "session_log" in self.device_config:
            params["session_log"] = self.device_config["session_log"]
        elif log_dir:
            params["session_log"] = os.path.join(log_dir, f"{self.device_name}.log")

        logger.info("Connecting to %s (%s)", self.device_name, params["host"])
        self.net_connect = ConnectHandler(**params)
        # Cisco-style platforms (incl. cEOS) land in user mode `>` even with
        # `username admin privilege 15`; without enable(), `show running-config`
        # returns "% Invalid input (privileged mode required)" and `configure
        # terminal` is rejected. enable() is a no-op when already in enable
        # mode, so it's safe to run unconditionally on connect.
        if self.device_config["device_type"] in _CISCO_LIKE_PLATFORMS:
            self.net_connect.enable()
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
            becomes ``show configuration system services``. SR Linux:
            ``"system"`` becomes ``info system``.

        Raises
        ------
        NotImplementedError
            If the device's ``device_type`` has no known config-dump command.
        """
        conn = self._ensure_connected()

        device_type = self.device_config.get("device_type", "")

        if device_type in _JUNOS_PLATFORMS:
            base = "show configuration"
            if section:
                base = f"{base} {section}"
            cmd = f"{base} | display set | no-more"
        elif device_type in _SRL_PLATFORMS:
            cmd = f"info {section}" if section else "info"
        elif device_type in _CISCO_LIKE_PLATFORMS:
            cmd = "show running-config"
            if section:
                cmd = f"{cmd} | section {section}"
        else:
            raise NotImplementedError(
                f"get_config is not implemented for device_type "
                f"'{device_type}'. Add it to _JUNOS_PLATFORMS, "
                f"_SRL_PLATFORMS, or _CISCO_LIKE_PLATFORMS in "
                f"ncli.device.connection."
            )

        output: str = conn.send_command(cmd)
        return output
