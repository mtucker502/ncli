"""End-to-end (containerlab) test harness fixtures.

This conftest is intentionally isolated from `tests/conftest.py` — the unit
suite must remain runnable without Docker / containerlab / SSH dependencies.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

from tests.e2e.harness.endpoint import DeviceEndpoint
from tests.e2e.harness.executor import Executor
from tests.e2e.harness.inventory import write_inventory
from tests.e2e.harness.local_executor import LocalExecutor
from tests.e2e.harness.vendor import VENDORS
from tests.e2e.topologies import isolated, session_three_vendor


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


def _build_executor(clab_host: str | None) -> Executor:
    if clab_host is None:
        return LocalExecutor()
    # RemoteExecutor lands in Phase 6.
    from tests.e2e.harness.remote_executor import RemoteExecutor  # noqa: PLC0415

    return RemoteExecutor(host=clab_host)


@pytest.fixture(scope="session")
def executor(clab_host: str | None) -> Iterator[Executor]:
    ex = _build_executor(clab_host)
    try:
        ex.preflight()
    except RuntimeError as exc:
        pytest.skip(f"e2e prereqs missing on {'local' if clab_host is None else clab_host}: {exc}")
    yield ex
    ex.close()


def _vendors_with_images(executor: Executor, clab_strict: bool) -> set[str]:
    """Return the set of vendor keys whose images are present on the executor host."""
    available: set[str] = set()
    missing: list[str] = []
    for key, vendor in VENDORS.items():
        if executor.image_probe.has_image(vendor.image):
            available.add(key)
        else:
            missing.append(f"{key} ({vendor.image})")
    if clab_strict and missing:
        pytest.fail(f"NCLI_E2E_STRICT=1 and missing images: {', '.join(missing)}")
    return available


@pytest.fixture(scope="session")
def clab_session(executor: Executor, clab_strict: bool) -> Iterator[dict[str, DeviceEndpoint]]:
    available = _vendors_with_images(executor, clab_strict)
    if not available:
        pytest.skip("no vendor images available on executor host")

    topology = session_three_vendor()
    if available != topology.required_kinds():
        topology = topology.without_kinds([k for k in topology.required_kinds() if k not in available])

    lab = executor.deploy(topology)
    try:
        endpoints = {n.name: executor.resolve(lab, n.name) for n in topology.nodes}
        yield endpoints
    finally:
        executor.destroy(lab)


@pytest.fixture(params=["crpd", "ceos", "nokia_srlinux"])
def isolated_device(
    request: pytest.FixtureRequest,
    executor: Executor,
    clab_strict: bool,
) -> Iterator[DeviceEndpoint]:
    vendor_key: str = request.param
    vendor = VENDORS[vendor_key]
    if not executor.image_probe.has_image(vendor.image):
        if clab_strict:
            pytest.fail(f"NCLI_E2E_STRICT=1 and missing image {vendor.image}")
        pytest.skip(f"image {vendor.image} not available")

    topology = isolated(vendor_key)
    lab = executor.deploy(topology)
    try:
        endpoint = executor.resolve(lab, topology.nodes[0].name)
        yield endpoint
    finally:
        executor.destroy(lab)


@pytest.fixture()
def inventory_path(tmp_path: Path) -> Path:
    """A fresh empty inventory.yaml the test populates via session_inventory / isolated_inventory."""
    return tmp_path / "inventory.yaml"


@pytest.fixture()
def session_inventory(inventory_path: Path, clab_session: dict[str, DeviceEndpoint]) -> Path:
    return write_inventory(inventory_path, clab_session)


@pytest.fixture()
def isolated_inventory(inventory_path: Path, isolated_device: DeviceEndpoint) -> Path:
    return write_inventory(inventory_path, {isolated_device.name: isolated_device})


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> object:
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call" or rep.passed:
        return None
    if "clab" not in {m.name for m in item.iter_markers()}:
        return None
    artifacts_root = Path(item.config.rootpath) / "tests" / "e2e" / "_artifacts" / item.name
    try:
        artifacts_root.mkdir(parents=True, exist_ok=True)
        (artifacts_root / "stderr.txt").write_text(str(rep.longrepr))
        executor = item.funcargs.get("executor")
        if executor is not None:
            (artifacts_root / "executor.txt").write_text(type(executor).__name__)
    except Exception as exc:  # noqa: BLE001
        # Never let artifact collection fail a test.
        artifacts_root.mkdir(parents=True, exist_ok=True)
        (artifacts_root / "artifact-error.txt").write_text(repr(exc))
    return None
