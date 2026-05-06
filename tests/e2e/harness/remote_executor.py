"""Run containerlab on a remote host over SSH, with one local-forwarded port per node."""

from __future__ import annotations

import json
import logging
import shlex
import uuid
from pathlib import Path, PurePosixPath

from tests.e2e.harness.endpoint import DeviceEndpoint, Lab
from tests.e2e.harness.executor import Executor
from tests.e2e.harness.health import wait_ssh_open
from tests.e2e.harness.images import ImageProbe
from tests.e2e.harness.inspect import (
    HEALTH_DEADLINE_S,
    SMOKE_BACKOFF_S,
    SMOKE_RETRIES,
    extract_ipv4,
    find_node,
)
from tests.e2e.harness.ssh import SshMaster, alloc_local_port
from tests.e2e.harness.topology import Topology
from tests.e2e.harness.vendor import VENDORS

logger = logging.getLogger(__name__)


class RemoteExecutor(Executor):
    def __init__(self, host: str, *, user: str | None = None, port: int = 22) -> None:
        self._master = SshMaster(host=host, user=user, port=port)
        # (lab_name, node_name) -> (local_port, remote_host, remote_port).
        # Storing the full tuple lets destroy() issue `ssh -O cancel -L ...`
        # without re-resolving the remote IP from inspect_raw at teardown.
        self._tunnels: dict[tuple[str, str], tuple[int, str, int]] = {}

    def preflight(self) -> None:
        self._master.open()
        for tool in ("docker", "containerlab"):
            r = self._master.run(["which", tool])
            if r.returncode != 0:
                raise RuntimeError(f"`{tool}` not found on {self._master.host}")
        r = self._master.run(["docker", "info"])
        if r.returncode != 0:
            raise RuntimeError(f"docker daemon not reachable on {self._master.host}: {r.stderr}")

    @property
    def image_probe(self) -> ImageProbe:
        return ImageProbe.over_ssh(self._master)

    def deploy(self, topology: Topology) -> Lab:
        # Stage the topology YAML into /tmp on the remote.
        remote_dir = PurePosixPath(f"/tmp/{topology.name}-{uuid.uuid4().hex[:6]}")
        remote_yaml = remote_dir / f"{topology.name}.clab.yaml"
        mk = self._master.run(["mkdir", "-p", str(remote_dir)])
        if mk.returncode != 0:
            raise RuntimeError(
                f"creating remote staging dir {remote_dir} failed: {mk.stderr}"
            )
        write_cmd = f"cat > {shlex.quote(str(remote_yaml))}"
        proc = self._master.run_with_stdin(["sh", "-c", write_cmd], topology.to_clab_yaml())
        if proc.returncode != 0:
            raise RuntimeError(f"writing remote topology failed: {proc.stderr}")

        # Stage startup-configs alongside the YAML so clab resolves them by basename.
        for basename, source in topology.startup_files():
            remote_cfg = remote_dir / basename
            cfg_cmd = f"cat > {shlex.quote(str(remote_cfg))}"
            cfg_proc = self._master.run_with_stdin(["sh", "-c", cfg_cmd], source.read_text())
            if cfg_proc.returncode != 0:
                raise RuntimeError(f"writing remote startup-config {basename} failed: {cfg_proc.stderr}")

        r = self._master.run(
            ["containerlab", "deploy", "-t", str(remote_yaml)], timeout=600
        )
        if r.returncode != 0:
            raise RuntimeError(f"remote clab deploy failed:\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}")

        inspect = self._master.run(
            ["containerlab", "inspect", "-t", str(remote_yaml), "--format", "json"],
            timeout=30,
        )
        if inspect.returncode != 0:
            raise RuntimeError(f"remote clab inspect failed: {inspect.stderr}")
        return Lab(name=topology.name, topology_yaml_path=str(remote_yaml), inspect_raw=json.loads(inspect.stdout))

    def destroy(self, lab: Lab) -> None:
        # Drain any local-forwards we opened for this lab. Listeners survive
        # past clab destroy until master exit otherwise, leaking local ports
        # across parameterized lab runs. Best-effort — log and move on.
        for key in [k for k in self._tunnels if k[0] == lab.name]:
            local_port, remote_host, remote_port = self._tunnels[key]
            try:
                cancel = self._master.cancel_forward(local_port, remote_host, remote_port)
                if cancel.returncode != 0:
                    logger.warning(
                        "ssh cancel-forward exited %d for %s/%s (%d->%s:%d): %s",
                        cancel.returncode, key[0], key[1],
                        local_port, remote_host, remote_port,
                        cancel.stderr.strip(),
                    )
            except Exception as exc:  # noqa: BLE001 - cleanup is best-effort
                logger.warning(
                    "ssh cancel-forward raised for %s/%s (%d->%s:%d): %s",
                    key[0], key[1], local_port, remote_host, remote_port, exc,
                )
            self._tunnels.pop(key, None)

        proc = self._master.run(["containerlab", "destroy", "-t", lab.topology_yaml_path, "--cleanup"])
        if proc.returncode != 0:
            logger.warning(
                "remote clab destroy exited %d for %s: %s",
                proc.returncode, lab.name, proc.stderr.strip(),
            )

        # Clean up the remote staging dir we created in deploy(). Guard against
        # accidental wider deletion if a hand-rolled Lab points elsewhere.
        parent = PurePosixPath(lab.topology_yaml_path).parent
        parent_str = str(parent)
        if not parent_str.startswith("/tmp/"):
            logger.warning(
                "skipping remote staging cleanup for %s: parent %r outside /tmp/",
                lab.name, parent_str,
            )
            return
        try:
            rm = self._master.run(["rm", "-rf", parent_str])
            if rm.returncode != 0:
                logger.warning(
                    "remote staging cleanup failed for %s: %s",
                    parent_str, rm.stderr.strip(),
                )
        except Exception as exc:  # noqa: BLE001 - cleanup is best-effort
            logger.warning(
                "remote staging cleanup raised for %s: %s", parent_str, exc,
            )

    def resolve(self, lab: Lab, node_name: str) -> DeviceEndpoint:
        node_doc = find_node(lab.inspect_raw, lab.name, node_name)
        remote_ip = extract_ipv4(node_doc)

        # alloc_local_port closes its probe socket before forward() binds, so a
        # parallel pytest run can grab the port in between — retry once on bind clash.
        local_port = alloc_local_port()
        try:
            self._master.forward(local_port, remote_ip, 22)
        except RuntimeError as exc:
            if "Address already in use" not in str(exc):
                raise
            local_port = alloc_local_port()
            self._master.forward(local_port, remote_ip, 22)
        self._tunnels[(lab.name, node_name)] = (local_port, remote_ip, 22)

        kind = node_doc.get("kind") or node_doc.get("Kind", "")
        vendor = next((v for v in VENDORS.values() if v.kind == kind), None)
        if vendor is None:
            raise RuntimeError(f"Cannot map clab kind {kind!r} to Vendor")

        deadline = HEALTH_DEADLINE_S.get(kind, 60)
        if not wait_ssh_open("127.0.0.1", local_port, deadline_s=deadline):
            raise RuntimeError(f"tunneled SSH on {node_name} did not come up within {deadline}s")

        from tests.e2e.harness.connect import smoke_test_connect

        smoke_test_connect(
            "127.0.0.1", local_port, vendor.username, vendor.password, vendor.netmiko_type,
            retries=SMOKE_RETRIES.get(kind, 3), backoff_s=SMOKE_BACKOFF_S,
        )

        return DeviceEndpoint(
            name=node_name,
            host="127.0.0.1",
            port=local_port,
            username=vendor.username,
            password=vendor.password,
            device_type=vendor.netmiko_type,
        )

    def container_logs(self, container_name: str, tail: int = 200) -> str:
        proc = self._master.run(
            ["docker", "logs", "--tail", str(tail), container_name], timeout=30
        )
        return proc.stdout + "\n--- stderr ---\n" + proc.stderr

    def dump_diagnostics(self, dest: Path) -> None:
        """Write executor-level diagnostics (ssh master state, tunnels) for failure artifacts."""
        self._master.dump_state(dest)

    def close(self) -> None:
        self._master.close()
