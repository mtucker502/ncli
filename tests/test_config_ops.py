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
        mock_connection.device_config = {"device_type": "cisco_xr", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "ok"
        mock_inner = MagicMock()
        mock_inner.commit.return_value = "committed"
        mock_connection._ensure_connected.return_value = mock_inner

        lines = ["hostname R1"]
        config_push(mock_connection, lines, comment="test change")
        mock_inner.commit.assert_called_once_with(comment="test change")

    def test_push_no_commit_on_ios(self, mock_connection: MagicMock) -> None:
        mock_connection.device_config = {"device_type": "cisco_ios", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "ok"

        lines = ["hostname R1"]
        config_push(mock_connection, lines)
        mock_connection._ensure_connected.assert_not_called()

    def test_push_no_commit_on_arista_eos(self, mock_connection: MagicMock) -> None:
        # Netmiko's arista driver inherits BaseConnection.commit(), which
        # raises AttributeError. The default `configure terminal` is immediate,
        # so no commit step is needed.
        mock_connection.device_config = {"device_type": "arista_eos", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "ok"

        lines = ["hostname SW1"]
        config_push(mock_connection, lines)
        mock_connection._ensure_connected.assert_not_called()

    def test_push_commits_on_nokia_srl(self, mock_connection: MagicMock) -> None:
        # Netmiko's NokiaSrlSSH.send_config_set leaves the session in
        # `candidate private` and does not auto-commit; without an explicit
        # commit() call the candidate is discarded on disconnect.
        mock_connection.device_config = {"device_type": "nokia_srl", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "config applied"
        mock_inner = MagicMock()
        mock_inner.commit.return_value = "committed"
        mock_connection._ensure_connected.return_value = mock_inner

        lines = ['set / system banner login-banner "hello"']
        result = config_push(mock_connection, lines)
        mock_inner.commit.assert_called_once_with()
        assert "committed" in result

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

    def test_push_junos_with_comment_bypasses_netmiko_commit(
        self, mock_connection: MagicMock
    ) -> None:
        # Netmiko's juniper commit(comment=) and send_command both use regex
        # paths that misfire on # or > in the comment. Drop to write_channel +
        # read_until_pattern for marker-based completion.
        mock_connection.device_config = {"device_type": "juniper_junos", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "config applied"
        mock_inner = MagicMock()
        mock_inner.read_until_pattern.return_value = "commit complete\n[edit]\nroot@r1# "
        mock_connection._ensure_connected.return_value = mock_inner

        result = config_push(
            mock_connection, ["set foo"], comment="fixes #1 >see ref"
        )

        mock_inner.commit.assert_not_called()
        mock_inner.send_command.assert_not_called()
        mock_inner.config_mode.assert_called_once()
        sent_cmd = mock_inner.write_channel.call_args.args[0]
        assert sent_cmd == 'commit comment "fixes #1 >see ref"\n'
        assert "commit complete" in result

    def test_push_junos_with_comment_raises_on_failure(self, mock_connection: MagicMock) -> None:
        mock_connection.device_config = {"device_type": "juniper_junos", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "ok"
        mock_inner = MagicMock()
        mock_inner.read_until_pattern.return_value = "error: configuration check-out failed"
        mock_connection._ensure_connected.return_value = mock_inner

        with pytest.raises(RuntimeError, match="commit failed"):
            config_push(mock_connection, ["set foo"], comment="hello")

    def test_push_junos_rejects_double_quote_in_comment(
        self, mock_connection: MagicMock
    ) -> None:
        mock_connection.device_config = {"device_type": "juniper_junos", "host": "10.0.0.1"}
        mock_connection.send_config.return_value = "ok"

        with pytest.raises(ValueError, match="double quote"):
            config_push(mock_connection, ["set foo"], comment='bad "quote" here')


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

    def test_diff_candidate_with_extra_trailing_newline_is_empty(
        self, mock_connection: MagicMock
    ) -> None:
        # Reproduces the scenario where `ncli config show > file` writes
        # running-config plus an extra trailing newline (added by click.echo),
        # then the file is fed back via `--candidate`. The candidate file has
        # one more trailing '\n' than the internal running config.
        running = "hostname R1\ninterface lo0\n"
        mock_connection.get_config.return_value = running

        candidate = running + "\n"

        result = config_diff(mock_connection, candidate=candidate)
        assert result == ""

    def test_diff_candidate_missing_trailing_newline_is_empty(
        self, mock_connection: MagicMock
    ) -> None:
        running = "hostname R1\ninterface lo0\n"
        mock_connection.get_config.return_value = running

        candidate = running.rstrip("\n")

        result = config_diff(mock_connection, candidate=candidate)
        assert result == ""
