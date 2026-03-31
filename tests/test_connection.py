"""Tests for NetmikoConnection wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ncli.auth.base import Credentials
from ncli.device.connection import NetmikoConnection


@pytest.fixture()
def device_config() -> dict:
    return {
        "device_type": "cisco_ios",
        "host": "10.0.0.1",
        "port": 22,
        "timeout": 30,
    }


@pytest.fixture()
def credentials() -> Credentials:
    return Credentials(
        username="admin",
        password="secret",
        enable_secret="en_secret",
    )


@pytest.fixture()
def ssh_key_credentials() -> Credentials:
    return Credentials(
        username="keyuser",
        key_file="/path/to/key",
    )


@pytest.fixture()
def agent_credentials() -> Credentials:
    return Credentials(
        username="agentuser",
        use_ssh_agent=True,
    )


class TestNetmikoConnectionInit:
    def test_init_stores_attrs(self, device_config: dict, credentials: Credentials) -> None:
        conn = NetmikoConnection("dev1", device_config, credentials)
        assert conn.device_name == "dev1"
        assert conn.device_config is device_config
        assert conn.credentials is credentials
        assert conn.net_connect is None


class TestNetmikoConnectionContextManager:
    @patch("ncli.device.connection.ConnectHandler")
    def test_context_manager_connects_and_disconnects(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            assert conn.net_connect is mock_conn

        mock_handler.assert_called_once()
        mock_conn.disconnect.assert_called_once()

    @patch("ncli.device.connection.ConnectHandler")
    def test_connect_passes_password_params(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_handler.return_value = MagicMock()

        conn = NetmikoConnection("dev1", device_config, credentials)
        conn.connect()

        call_kwargs = mock_handler.call_args[1]
        assert call_kwargs["device_type"] == "cisco_ios"
        assert call_kwargs["host"] == "10.0.0.1"
        assert call_kwargs["username"] == "admin"
        assert call_kwargs["password"] == "secret"
        assert call_kwargs["secret"] == "en_secret"
        assert call_kwargs["port"] == 22
        assert call_kwargs["timeout"] == 30
        assert call_kwargs["conn_timeout"] == 30
        conn.disconnect()

    @patch("ncli.device.connection.ConnectHandler")
    def test_connect_with_ssh_key(
        self, mock_handler: MagicMock, device_config: dict, ssh_key_credentials: Credentials
    ) -> None:
        mock_handler.return_value = MagicMock()

        conn = NetmikoConnection("dev1", device_config, ssh_key_credentials)
        conn.connect()

        call_kwargs = mock_handler.call_args[1]
        assert call_kwargs["key_file"] == "/path/to/key"
        assert "use_keys" not in call_kwargs
        conn.disconnect()

    @patch("ncli.device.connection.ConnectHandler")
    def test_connect_with_ssh_agent(
        self, mock_handler: MagicMock, device_config: dict, agent_credentials: Credentials
    ) -> None:
        mock_handler.return_value = MagicMock()

        conn = NetmikoConnection("dev1", device_config, agent_credentials)
        conn.connect()

        call_kwargs = mock_handler.call_args[1]
        assert call_kwargs["use_keys"] is True
        assert call_kwargs["allow_agent"] is True
        conn.disconnect()

    @patch("ncli.device.connection.ConnectHandler")
    def test_disconnect_sets_none(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_handler.return_value = MagicMock()

        conn = NetmikoConnection("dev1", device_config, credentials)
        conn.connect()
        conn.disconnect()
        assert conn.net_connect is None

    @patch("ncli.device.connection.ConnectHandler")
    def test_disconnect_handles_exception(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.disconnect.side_effect = OSError("connection lost")
        mock_handler.return_value = mock_conn

        conn = NetmikoConnection("dev1", device_config, credentials)
        conn.connect()
        # Should not raise
        conn.disconnect()
        assert conn.net_connect is None


class TestNetmikoConnectionSendCommand:
    @patch("ncli.device.connection.ConnectHandler")
    def test_send_command(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.return_value = "output line 1\noutput line 2"
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            result = conn.send_command("show version")

        mock_conn.send_command.assert_called_once_with("show version")
        assert result == "output line 1\noutput line 2"

    @patch("ncli.device.connection.ConnectHandler")
    def test_send_command_textfsm(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.return_value = "structured output"
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            result = conn.send_command("show version", textfsm=True)

        mock_conn.send_command.assert_called_once_with("show version", use_textfsm=True)
        assert result == "structured output"

    @patch("ncli.device.connection.ConnectHandler")
    def test_send_command_textfsm_fallback(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.side_effect = [
            Exception("No template"),
            "raw output",
        ]
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            result = conn.send_command("show version", textfsm=True)

        assert result == "raw output"
        assert mock_conn.send_command.call_count == 2

    def test_send_command_not_connected_raises(self, device_config: dict, credentials: Credentials) -> None:
        conn = NetmikoConnection("dev1", device_config, credentials)
        with pytest.raises(RuntimeError, match="Not connected"):
            conn.send_command("show version")


class TestNetmikoConnectionSendCommands:
    @patch("ncli.device.connection.ConnectHandler")
    def test_send_commands_all(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.side_effect = ["out1", "out2", "out3"]
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            results = conn.send_commands(["cmd1", "cmd2", "cmd3"])

        assert results == ["out1", "out2", "out3"]

    @patch("ncli.device.connection.ConnectHandler")
    def test_send_commands_stop_on_error(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.side_effect = [
            "good output",
            "% Invalid input detected",
            "should not reach",
        ]
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            results = conn.send_commands(["cmd1", "cmd2", "cmd3"], stop_on_error=True)

        assert len(results) == 2
        assert "Invalid input" in results[1]

    @patch("ncli.device.connection.ConnectHandler")
    def test_send_commands_no_stop_on_error(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.side_effect = [
            "good output",
            "% Invalid input detected",
            "more output",
        ]
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            results = conn.send_commands(["cmd1", "cmd2", "cmd3"], stop_on_error=False)

        assert len(results) == 3


class TestNetmikoConnectionSendConfig:
    @patch("ncli.device.connection.ConnectHandler")
    def test_send_config(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_config_set.return_value = "config applied"
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            result = conn.send_config(["interface lo0", "ip address 1.1.1.1 255.255.255.255"])

        mock_conn.send_config_set.assert_called_once_with(
            ["interface lo0", "ip address 1.1.1.1 255.255.255.255"]
        )
        assert result == "config applied"

    @patch("ncli.device.connection.ConnectHandler")
    def test_get_config(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.return_value = "running config output"
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            result = conn.get_config()

        mock_conn.send_command.assert_called_once_with("show running-config")
        assert result == "running config output"

    @patch("ncli.device.connection.ConnectHandler")
    def test_get_config_with_section(
        self, mock_handler: MagicMock, device_config: dict, credentials: Credentials
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.send_command.return_value = "interface config"
        mock_handler.return_value = mock_conn

        with NetmikoConnection("dev1", device_config, credentials) as conn:
            result = conn.get_config(section="interface")

        mock_conn.send_command.assert_called_once_with("show running-config | section interface")
        assert result == "interface config"
