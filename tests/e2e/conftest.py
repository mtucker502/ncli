"""End-to-end (containerlab) test harness fixtures.

This conftest is intentionally isolated from `tests/conftest.py` — the unit
suite must remain runnable without Docker / containerlab / SSH dependencies.
"""

from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--clab-host",
        default=None,
        help="Remote SSH host running containerlab; unset = local executor.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "clab: end-to-end test requiring containerlab (opt in with `-m clab`)",
    )


@pytest.fixture(scope="session")
def clab_host(request: pytest.FixtureRequest) -> str | None:
    """Resolve the target clab host: --clab-host wins, then NCLI_E2E_HOST."""
    return request.config.getoption("--clab-host") or os.environ.get("NCLI_E2E_HOST")


@pytest.fixture(scope="session")
def clab_strict() -> bool:
    """When NCLI_E2E_STRICT=1, missing-image skips become hard fails."""
    return os.environ.get("NCLI_E2E_STRICT") == "1"
