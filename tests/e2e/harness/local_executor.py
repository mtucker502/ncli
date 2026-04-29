"""Run containerlab on the local host."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.e2e.harness.endpoint import DeviceEndpoint, Lab
from tests.e2e.harness.executor import Executor
from tests.e2e.harness.health import wait_ssh_open
from tests.e2e.harness.images import ImageProbe
from tests.e2e.harness.topology import Topology

logger = logging.getLogger(__name__)

# Per-vendor SSH-up budget; cEOS notoriously takes the longest.
_HEALTH_DEADLINE_S = {
    "crpd": 60,
    "nokia_srlinux": 60,
    "ceos": 180,
}


class LocalExecutor(Executor):
    def __init__(self) -> None:
        self._tmpdirs: list[tempfile.TemporaryDirectory] = []

    def preflight(self) -> None:
        for tool in ("docker", "containerlab"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"`{tool}` not found in PATH")
        if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
            raise RuntimeError("docker daemon not reachable")

    @property
    def image_probe(self) -> ImageProbe:
        return ImageProbe.local()

    def deploy(self, topology: Topology) -> Lab:
        tmp = tempfile.TemporaryDirectory(prefix=f"{topology.name}-")
        self._tmpdirs.append(tmp)
        topo_path = Path(tmp.name) / f"{topology.name}.clab.yaml"
        topo_path.write_text(topology.to_clab_yaml())

        logger.info("Deploying clab topology %s", topology.name)
        proc = subprocess.run(
            ["containerlab", "deploy", "-t", str(topo_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"clab deploy failed:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")

        inspect = subprocess.run(
            ["containerlab", "inspect", "-t", str(topo_path), "--format", "json"],
            capture_output=True,
            text=True,
        )
        if inspect.returncode != 0:
            raise RuntimeError(
                f"clab inspect failed:\nstdout:\n{inspect.stdout}\nstderr:\n{inspect.stderr}"
            )
        inspect_doc = json.loads(inspect.stdout)
        return Lab(name=topology.name, topology_yaml_path=str(topo_path), inspect_raw=inspect_doc)

    def destroy(self, lab: Lab) -> None:
        logger.info("Destroying clab topology %s", lab.name)
        proc = subprocess.run(
            ["containerlab", "destroy", "-t", lab.topology_yaml_path, "--cleanup"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.warning(
                "clab destroy exited %d for %s: %s",
                proc.returncode, lab.name, proc.stderr.strip(),
            )

    def resolve(self, lab: Lab, node_name: str) -> DeviceEndpoint:
        node_doc = _find_node(lab.inspect_raw, lab.name, node_name)
        host = _extract_ipv4(node_doc)
        from tests.e2e.harness.vendor import VENDORS

        # Match node back to its Vendor by clab kind.
        kind = node_doc.get("kind") or node_doc.get("Kind", "")
        vendor = next((v for v in VENDORS.values() if v.kind == kind), None)
        if vendor is None:
            raise RuntimeError(f"Cannot map clab kind {kind!r} to a Vendor")

        deadline = _HEALTH_DEADLINE_S.get(kind, 60)
        if not wait_ssh_open(host, 22, deadline_s=deadline):
            raise RuntimeError(f"SSH on {node_name} ({host}:22) did not come up within {deadline}s")

        from tests.e2e.harness.connect import smoke_test_connect

        smoke_test_connect(host, 22, vendor.username, vendor.password, vendor.netmiko_type)

        return DeviceEndpoint(
            name=node_name,
            host=host,
            port=22,
            username=vendor.username,
            password=vendor.password,
            device_type=vendor.netmiko_type,
        )

    def close(self) -> None:
        for tmp in self._tmpdirs:
            tmp.cleanup()
        self._tmpdirs.clear()


def _find_node(inspect_doc: dict, lab_name: str, node_name: str) -> dict:
    """clab's inspect JSON shape: {"containers": [{name, lab_name, kind, ipv4_address, ...}]}.
    Some clab versions nest under {lab_name: [...]}.
    """
    candidates: list[dict] = []
    if isinstance(inspect_doc, dict):
        if "containers" in inspect_doc:
            candidates = inspect_doc["containers"]
        elif lab_name in inspect_doc:
            candidates = inspect_doc[lab_name]
        else:
            for v in inspect_doc.values():
                if isinstance(v, list):
                    candidates.extend(v)
    for c in candidates:
        # node names are prefixed with `clab-<lab>-` in clab; match suffix.
        cname = c.get("name") or c.get("Name", "")
        if cname.endswith(f"-{node_name}") or cname == node_name:
            return c
    raise KeyError(f"node {node_name!r} not found in inspect output for lab {lab_name!r}")


def _extract_ipv4(node_doc: dict) -> str:
    for k in ("ipv4_address", "ipv4Address", "IPv4Address"):
        v = node_doc.get(k, "")
        if isinstance(v, str) and v:
            return v.split("/")[0]
    raise RuntimeError(f"No IPv4 address in node doc: {node_doc!r}")
