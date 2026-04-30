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
from tests.e2e.harness.inspect import HEALTH_DEADLINE_S, extract_ipv4, find_node
from tests.e2e.harness.topology import Topology

logger = logging.getLogger(__name__)


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
        node_doc = find_node(lab.inspect_raw, lab.name, node_name)
        host = extract_ipv4(node_doc)
        from tests.e2e.harness.vendor import VENDORS

        # Match node back to its Vendor by clab kind.
        kind = node_doc.get("kind") or node_doc.get("Kind", "")
        vendor = next((v for v in VENDORS.values() if v.kind == kind), None)
        if vendor is None:
            raise RuntimeError(f"Cannot map clab kind {kind!r} to a Vendor")

        deadline = HEALTH_DEADLINE_S.get(kind, 60)
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

    def container_logs(self, container_name: str, tail: int = 200) -> str:
        proc = subprocess.run(
            ["docker", "logs", "--tail", str(tail), container_name],
            capture_output=True, text=True,
        )
        return proc.stdout + "\n--- stderr ---\n" + proc.stderr

    def close(self) -> None:
        for tmp in self._tmpdirs:
            tmp.cleanup()
        self._tmpdirs.clear()
