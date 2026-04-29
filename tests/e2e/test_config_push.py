"""End-to-end tests for `ncli config push`."""

from __future__ import annotations

import subprocess

import pytest


def _push_change_for(device_type: str) -> str:
    """A vendor-appropriate harmless config snippet."""
    if device_type == "juniper_junos":
        return "set system login message ncli-e2e-test"
    if device_type == "arista_eos":
        return "banner login\nncli-e2e-test\nEOF"
    if device_type == "nokia_srl":
        return 'set / system banner login-banner "ncli-e2e-test"'
    raise ValueError(f"unknown device_type {device_type}")


@pytest.mark.clab
def test_config_push_dry_run_no_device_touch(isolated_inventory, isolated_device, tmp_path) -> None:
    cfg = tmp_path / "candidate.conf"
    cfg.write_text(_push_change_for(isolated_device.device_type) + "\n")
    proc = subprocess.run(
        ["ncli", "-f", str(isolated_inventory), "config", "push",
         isolated_device.name, str(cfg), "--dry-run"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Dry-run" in proc.stdout
    assert "ncli-e2e-test" in proc.stdout


@pytest.mark.clab
def test_config_push_lands_then_visible_in_show(isolated_inventory, isolated_device, tmp_path) -> None:
    snippet = _push_change_for(isolated_device.device_type)
    cfg = tmp_path / "candidate.conf"
    cfg.write_text(snippet + "\n")

    push = subprocess.run(
        ["ncli", "-f", str(isolated_inventory), "config", "push",
         isolated_device.name, str(cfg)],
        capture_output=True, text=True, timeout=180,
    )
    assert push.returncode == 0, push.stderr

    show = subprocess.run(
        ["ncli", "-f", str(isolated_inventory), "config", "show", isolated_device.name],
        capture_output=True, text=True, timeout=180,
    )
    assert show.returncode == 0
    assert "ncli-e2e-test" in show.stdout


@pytest.mark.clab
@pytest.mark.parametrize("comment", ["fixes #1 see >ref", 'plain hashtag # only', '> only'])
def test_junos_commit_comment_special_chars(isolated_inventory, isolated_device, tmp_path, comment) -> None:
    """Issue #1 regression: Junos commit comments with `#` and/or `>` must land cleanly."""
    if isolated_device.device_type != "juniper_junos":
        pytest.skip("Junos-specific regression test")
    cfg = tmp_path / "candidate.conf"
    cfg.write_text("set system login message regression-test\n")

    proc = subprocess.run(
        ["ncli", "-f", str(isolated_inventory), "config", "push",
         isolated_device.name, str(cfg), "--comment", comment],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert "commit complete" in proc.stdout


@pytest.mark.clab
def test_junos_commit_comment_with_double_quote_rejected(isolated_inventory, isolated_device, tmp_path) -> None:
    if isolated_device.device_type != "juniper_junos":
        pytest.skip("Junos-specific")
    cfg = tmp_path / "candidate.conf"
    cfg.write_text("set system login message qtest\n")

    proc = subprocess.run(
        ["ncli", "-f", str(isolated_inventory), "config", "push",
         isolated_device.name, str(cfg), "--comment", 'has "quote" inside'],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 1
    assert "double quote" in (proc.stderr + proc.stdout).lower()


@pytest.mark.clab
def test_bad_config_returns_nonzero_no_partial_state(isolated_inventory, isolated_device, tmp_path) -> None:
    if isolated_device.device_type != "juniper_junos":
        pytest.skip("Junos has the cleanest commit-or-rollback semantics")
    cfg = tmp_path / "bad.conf"
    cfg.write_text("set system bogus-knob nonsense-value\n")

    proc = subprocess.run(
        ["ncli", "-f", str(isolated_inventory), "config", "push",
         isolated_device.name, str(cfg)],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode != 0
