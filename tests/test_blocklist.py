"""Tests for safety blocklist module."""

from __future__ import annotations

from pathlib import Path

import pytest

from ncli.safety.blocklist import (
    load_blocklist,
    check_command,
    check_config,
    get_command_blocklist,
    get_config_blocklist,
)


@pytest.fixture()
def blocklist_file(tmp_path: Path) -> Path:
    content = """\
# Comment line
reload
write erase
^no shutdown$
"""
    p = tmp_path / "blocklist.txt"
    p.write_text(content)
    return p


class TestLoadBlocklist:
    def test_load_from_file(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        assert len(patterns) == 3

    def test_load_none_path(self) -> None:
        patterns = load_blocklist(None)
        assert patterns == []

    def test_load_missing_file(self, tmp_path: Path) -> None:
        patterns = load_blocklist(tmp_path / "nonexistent.txt")
        assert patterns == []

    def test_skips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        content = "# comment\n\n  \nactual_pattern\n"
        p = tmp_path / "bl.txt"
        p.write_text(content)
        patterns = load_blocklist(p)
        assert len(patterns) == 1

    def test_patterns_are_case_insensitive(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        # "reload" pattern should match "RELOAD"
        assert any(p.search("RELOAD") for p in patterns)


class TestCheckCommand:
    def test_blocked_command(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        assert check_command("reload", patterns) is True

    def test_blocked_partial_match(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        assert check_command("write erase all", patterns) is True

    def test_allowed_command(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        assert check_command("show version", patterns) is False

    def test_empty_blocklist_allows_everything(self) -> None:
        assert check_command("reload", []) is False
        assert check_command("write erase", []) is False

    def test_anchored_pattern(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        # "^no shutdown$" should match exactly "no shutdown"
        assert check_command("no shutdown", patterns) is True
        # But not "configure no shutdown please"
        assert check_command("configure no shutdown please", patterns) is False


class TestCheckConfig:
    def test_returns_blocked_lines(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        lines = ["hostname R1", "reload", "interface lo0", "write erase"]
        blocked = check_config(lines, patterns)
        assert "reload" in blocked
        assert "write erase" in blocked
        assert "hostname R1" not in blocked

    def test_empty_blocklist_returns_nothing(self) -> None:
        lines = ["reload", "write erase"]
        blocked = check_config(lines, [])
        assert blocked == []

    def test_no_blocked_lines(self, blocklist_file: Path) -> None:
        patterns = load_blocklist(blocklist_file)
        lines = ["hostname R1", "interface lo0"]
        blocked = check_config(lines, patterns)
        assert blocked == []


class TestGetBlocklistEnvVars:
    def test_get_command_blocklist_with_env(
        self, monkeypatch: pytest.MonkeyPatch, blocklist_file: Path
    ) -> None:
        monkeypatch.setenv("NCLI_BLOCK_CMD", str(blocklist_file))
        patterns = get_command_blocklist()
        assert len(patterns) == 3

    def test_get_command_blocklist_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NCLI_BLOCK_CMD", raising=False)
        patterns = get_command_blocklist()
        assert patterns == []

    def test_get_config_blocklist_with_env(
        self, monkeypatch: pytest.MonkeyPatch, blocklist_file: Path
    ) -> None:
        monkeypatch.setenv("NCLI_BLOCK_CFG", str(blocklist_file))
        patterns = get_config_blocklist()
        assert len(patterns) == 3

    def test_get_config_blocklist_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NCLI_BLOCK_CFG", raising=False)
        patterns = get_config_blocklist()
        assert patterns == []
