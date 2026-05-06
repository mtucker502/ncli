"""Integration test for LocalExecutor — only runs when local docker + clab + crpd image present.

This test is opt-in via `pytest -m clab` AND only runs against a local executor
(`--clab-host` unset / NCLI_E2E_HOST unset). It deploys a single-cRPD topology
and asserts the harness can resolve to a working SSH endpoint.
"""

from __future__ import annotations

import socket

import pytest

from tests.e2e.harness.local_executor import LocalExecutor
from tests.e2e.topologies import isolated


@pytest.mark.clab
def test_local_executor_deploys_and_resolves(clab_host: str | None) -> None:
    if clab_host is not None:
        pytest.skip("LocalExecutor test runs only when --clab-host is unset")

    ex = LocalExecutor()
    try:
        ex.preflight()
    except RuntimeError as exc:
        pytest.skip(f"local prereqs missing: {exc}")
    if not ex.image_probe.has_image("crpd:latest"):
        pytest.skip("crpd:latest image not present locally")

    topo = isolated("crpd")
    lab = ex.deploy(topo)
    try:
        endpoint = ex.resolve(lab, "crpd")
        assert endpoint.username == "root"
        assert endpoint.device_type == "juniper_junos"
        # SSH socket should be open
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            assert s.connect_ex((endpoint.host, endpoint.port)) == 0
    finally:
        ex.destroy(lab)
        ex.close()
