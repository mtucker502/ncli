"""End-to-end tests for `ncli config diff`."""

from __future__ import annotations

import pytest

from tests.e2e.harness.env import run_ncli


@pytest.mark.clab
def test_diff_against_modified_candidate_shows_change(session_inventory, clab_session, tmp_path) -> None:
    target = next((n for n in clab_session if "crpd" in n), None)
    if target is None:
        pytest.skip("no crpd device in session")

    show = run_ncli(
        ["ncli", "-f", str(session_inventory), "config", "show", target],
        capture_output=True, text=True, timeout=120,
    )
    assert show.returncode == 0, show.stderr

    candidate = tmp_path / "candidate.conf"
    candidate.write_text(show.stdout + "\n# inserted line that should diff\n")

    diff = run_ncli(
        ["ncli", "-f", str(session_inventory), "config", "diff", target, "--candidate", str(candidate)],
        capture_output=True, text=True, timeout=120,
    )
    assert diff.returncode == 0
    assert "+# inserted line" in diff.stdout


@pytest.mark.clab
def test_diff_identical_candidate_is_empty(session_inventory, clab_session, tmp_path) -> None:
    target = next((n for n in clab_session if "crpd" in n), None)
    if target is None:
        pytest.skip("no crpd device in session")

    show = run_ncli(
        ["ncli", "-f", str(session_inventory), "config", "show", target],
        capture_output=True, text=True, timeout=120,
    )
    assert show.returncode == 0

    candidate = tmp_path / "same.conf"
    candidate.write_text(show.stdout)

    diff = run_ncli(
        ["ncli", "-f", str(session_inventory), "config", "diff", target, "--candidate", str(candidate)],
        capture_output=True, text=True, timeout=120,
    )
    assert diff.returncode == 0
    assert "No differences" in diff.stdout or diff.stdout.strip() == ""
