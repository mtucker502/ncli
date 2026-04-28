"""Tests for high-level configuration operations."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ncli.device.config_ops import config_push, config_diff
from ncli.device.connection import NetmikoConnection


@pytest.fixture()
def mock_connection() -> MagicMock:
    """Return a mock NetmikoConnection with common attributes."""
    conn = MagicMock(spec=NetmikoConnection)
    conn.device_name = "testdev"
    conn.device_config = {"device_type": "cisco_ios", "host": "10.0.0.1"}
    return conn


class TestConfigPush:
    def test_dry_run_returns_config_text(self, mock_connection: MagicMock) -> None:
        lines = ["interface lo0", "ip address 1.1.1.1 255.255.255.255"]
        result = config_push(mock_connection, lines, dry_run=True)
        assert result == "interface lo0\nip address 1.1.1.1 255.255.255.255"
        mock_connection.send_config.assert_not_called()

    def test_push_calls_send_config(self, mock_connection: MagicMock) -> None:
        mock_connection.send_config.return_value = "config applied"
        lines = ["hostname R1"]
        result = config_push(mock_connection, lines)
        mock_connection.send_config.assert_called_once_with(lines)
        assert "config applied" in result

    def test_push_commits_on_supported_platforms(self, mock_connection: MagicMock) -> None:
        mock_connection.device_config = {"device_type": "junos", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "config applied"
        mock_inner = MagicMock()
        mock_inner.commit.return_value = "committed"
        mock_connection._ensure_connected.return_value = mock_inner

        lines = ["set system hostname R1"]
        result = config_push(mock_connection, lines)
        mock_inner.commit.assert_called_once_with()
        assert "committed" in result

    def test_push_commits_with_comment(self, mock_connection: MagicMock) -> None:
        mock_connection.device_config = {"device_type": "arista_eos", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "ok"
        mock_inner = MagicMock()
        mock_inner.commit.return_value = "committed"
        mock_connection._ensure_connected.return_value = mock_inner

        lines = ["hostname SW1"]
        config_push(mock_connection, lines, comment="test change")
        mock_inner.commit.assert_called_once_with(comment="test change")

    def test_push_no_commit_on_ios(self, mock_connection: MagicMock) -> None:
        mock_connection.device_config = {"device_type": "cisco_ios", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "ok"

        lines = ["hostname R1"]
        config_push(mock_connection, lines)
        mock_connection._ensure_connected.assert_not_called()

    def test_push_commits_on_juniper_junos(self, mock_connection: MagicMock) -> None:
        mock_connection.device_config = {"device_type": "juniper_junos", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "config applied"
        mock_inner = MagicMock()
        mock_inner.commit.return_value = "committed"
        mock_connection._ensure_connected.return_value = mock_inner

        lines = ["set system host-name R1"]
        result = config_push(mock_connection, lines)
        mock_inner.commit.assert_called_once_with()
        assert "committed" in result


class TestConfigDiff:
    def test_diff_no_candidate_returns_empty(self, mock_connection: MagicMock) -> None:
        result = config_diff(mock_connection, candidate=None)
        assert result == ""

    def test_diff_with_candidate(self, mock_connection: MagicMock) -> None:
        mock_connection.get_config.return_value = "hostname R1\ninterface lo0\n"
        candidate = "hostname R2\ninterface lo0\n"

        result = config_diff(mock_connection, candidate=candidate)
        assert "---" in result
        assert "+++" in result
        assert "hostname R1" in result
        assert "hostname R2" in result

    def test_diff_identical_config(self, mock_connection: MagicMock) -> None:
        running = "hostname R1\ninterface lo0\n"
        mock_connection.get_config.return_value = running

        result = config_diff(mock_connection, candidate=running)
        assert result == ""
