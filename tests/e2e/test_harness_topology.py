"""Unit tests for the in-process topology / vendor model.

These tests do NOT need Docker or containerlab — they exercise pure data
structures and YAML emission. Hence: no @pytest.mark.clab.
"""

from __future__ import annotations

import socket
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from tests.e2e.harness.connect import smoke_test_connect
from tests.e2e.harness.health import wait_ssh_open
from tests.e2e.harness.images import ImageProbe
from tests.e2e.harness.inspect import HEALTH_DEADLINE_S, SMOKE_RETRIES
from tests.e2e.harness.ssh import SshMaster
from tests.e2e.harness.topology import Node, Topology
from tests.e2e.harness.vendor import VENDORS, Vendor
from tests.e2e.topologies import isolated, session_three_vendor


class TestVendorRegistry:
    def test_three_vendors_registered(self) -> None:
        assert set(VENDORS) == {"crpd", "ceos", "nokia_srlinux"}

    def test_vendor_fields(self) -> None:
        crpd = VENDORS["crpd"]
        assert crpd.kind == "crpd"
        assert crpd.netmiko_type == "juniper_junos"
        assert crpd.username == "root"
        assert crpd.password == "clab123"

    def test_arista_credentials(self) -> None:
        ceos = VENDORS["ceos"]
        assert ceos.kind == "ceos"
        assert ceos.netmiko_type == "arista_eos"
        assert ceos.username == "admin"
        assert ceos.password == "admin"

    def test_srl_credentials(self) -> None:
        srl = VENDORS["nokia_srlinux"]
        assert srl.kind == "nokia_srlinux"
        assert srl.netmiko_type == "nokia_srl"
        assert srl.username == "admin"
        assert srl.password == "NokiaSrl1!"


class TestTopologyEmission:
    def test_session_three_vendor_has_three_nodes(self) -> None:
        topo = session_three_vendor()
        assert len(topo.nodes) == 3
        kinds = {n.vendor.kind for n in topo.nodes}
        assert kinds == {"crpd", "ceos", "nokia_srlinux"}

    def test_session_topology_name_is_uuid_suffixed(self) -> None:
        a = session_three_vendor()
        b = session_three_vendor()
        assert a.name != b.name
        assert a.name.startswith("ncli-e2e-")

    def test_isolated_one_vendor(self) -> None:
        topo = isolated("crpd")
        assert len(topo.nodes) == 1
        assert topo.nodes[0].vendor.kind == "crpd"

    def test_isolated_unknown_vendor_raises(self) -> None:
        with pytest.raises(KeyError):
            isolated("not-a-vendor")

    def test_to_clab_yaml_is_valid_yaml(self) -> None:
        topo = session_three_vendor()
        doc = yaml.safe_load(topo.to_clab_yaml())
        assert doc["name"] == topo.name
        assert "topology" in doc
        nodes = doc["topology"]["nodes"]
        assert len(nodes) == 3
        for cfg in nodes.values():
            assert "kind" in cfg
            assert "image" in cfg

    def test_to_clab_yaml_includes_startup_for_known_vendors(self) -> None:
        topo = isolated("crpd")
        doc = yaml.safe_load(topo.to_clab_yaml())
        node_cfg = next(iter(doc["topology"]["nodes"].values()))
        assert "startup-config" in node_cfg

    def test_required_kinds(self) -> None:
        topo = session_three_vendor()
        assert topo.required_kinds() == {"crpd", "ceos", "nokia_srlinux"}

    def test_without_kinds_drops_named_kinds(self) -> None:
        topo = session_three_vendor()
        smaller = topo.without_kinds(["ceos"])
        assert smaller.required_kinds() == {"crpd", "nokia_srlinux"}
        # original is unchanged
        assert topo.required_kinds() == {"crpd", "ceos", "nokia_srlinux"}

    def test_to_clab_yaml_omits_startup_when_none(self) -> None:
        custom = Vendor(
            kind="custom",
            image="custom:latest",
            netmiko_type="cisco_ios",
            username="u",
            password="p",
            startup_config=None,
        )
        topo = Topology(nodes=[Node(name="x", vendor=custom)])
        doc = yaml.safe_load(topo.to_clab_yaml())
        node_cfg = next(iter(doc["topology"]["nodes"].values()))
        assert "startup-config" not in node_cfg

    def test_without_kinds_empty_list_returns_all_nodes(self) -> None:
        topo = session_three_vendor()
        same = topo.without_kinds([])
        assert same.required_kinds() == topo.required_kinds()
        assert len(same.nodes) == 3

    def test_without_kinds_all_returns_empty_topology(self) -> None:
        topo = session_three_vendor()
        empty = topo.without_kinds(["crpd", "ceos", "nokia_srlinux"])
        assert empty.nodes == []
        assert empty.required_kinds() == set()


class TestStartupConfigsPresent:
    def test_all_vendor_startup_configs_exist(self) -> None:
        configs_dir = Path(__file__).parent / "topologies" / "configs"
        assert (configs_dir / "crpd.startup.conf").is_file()
        assert (configs_dir / "ceos.startup.cfg").is_file()
        assert (configs_dir / "srl.startup.cfg").is_file()


class TestImageProbe:
    def test_local_probe_present(self) -> None:
        with patch("tests.e2e.harness.images.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            probe = ImageProbe.local()
            assert probe.has_image("ceos:latest") is True
            args = mock_run.call_args.args[0]
            assert args[:3] == ["docker", "image", "inspect"]
            assert "ceos:latest" in args
            assert mock_run.call_args.kwargs.get("capture_output") is True

    def test_local_probe_missing(self) -> None:
        with patch("tests.e2e.harness.images.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            probe = ImageProbe.local()
            assert probe.has_image("nonexistent:tag") is False


class TestHealthGate:
    def test_returns_true_when_port_open(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def accept_and_close() -> None:
            try:
                c, _ = srv.accept()
                c.close()
            except OSError:
                pass

        threading.Thread(target=accept_and_close, daemon=True).start()
        assert wait_ssh_open("127.0.0.1", port, deadline_s=5) is True
        srv.close()

    def test_returns_false_when_port_unreachable(self) -> None:
        # Pick a port nothing should be listening on.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        assert wait_ssh_open("127.0.0.1", port, deadline_s=2, delays=(1,)) is False


class TestSmokeConnect:
    def test_succeeds_on_first_attempt(self) -> None:
        with patch("netmiko.ConnectHandler") as mock_conn, \
             patch("tests.e2e.harness.connect.time.sleep") as mock_sleep:
            mock_conn.return_value.disconnect.return_value = None
            smoke_test_connect("h", 22, "u", "p", "ceos", retries=5, backoff_s=0)
            assert mock_conn.call_count == 1
            assert mock_sleep.call_count == 0

    def test_retries_then_succeeds(self) -> None:
        with patch("netmiko.ConnectHandler") as mock_conn, \
             patch("tests.e2e.harness.connect.time.sleep"):
            ok = type(
                "Ok", (),
                {"disconnect": lambda self: None,
                 "send_command": lambda self, *a, **kw: ""},
            )()
            mock_conn.side_effect = [RuntimeError("banner reset"), RuntimeError("prompt"), ok]
            smoke_test_connect("h", 22, "u", "p", "ceos", retries=5, backoff_s=0)
            assert mock_conn.call_count == 3

    def test_raises_after_exhausting_budget(self) -> None:
        with patch("netmiko.ConnectHandler") as mock_conn, \
             patch("tests.e2e.harness.connect.time.sleep"):
            mock_conn.side_effect = RuntimeError("nope")
            with pytest.raises(RuntimeError, match="after 4 attempts"):
                smoke_test_connect("h", 22, "u", "p", "ceos", retries=4, backoff_s=0)
            assert mock_conn.call_count == 4

    def test_arista_eos_runs_readiness_command(self) -> None:
        # cEOS sshd accepts connections during EOS Warmup Service startup but
        # the CLI lags briefly. Sending a real command ensures the session can
        # actually carry data, not just that prompt detection succeeded.
        from unittest.mock import MagicMock
        with patch("netmiko.ConnectHandler") as mock_conn, \
             patch("tests.e2e.harness.connect.time.sleep"):
            mock_inner = MagicMock()
            mock_conn.return_value = mock_inner
            smoke_test_connect("h", 22, "u", "p", "arista_eos", retries=3, backoff_s=0)
            mock_inner.send_command.assert_called_once_with("show version", read_timeout=30)
            mock_inner.disconnect.assert_called_once()

    def test_nokia_srl_runs_readiness_command(self) -> None:
        from unittest.mock import MagicMock
        with patch("netmiko.ConnectHandler") as mock_conn, \
             patch("tests.e2e.harness.connect.time.sleep"):
            mock_inner = MagicMock()
            mock_conn.return_value = mock_inner
            smoke_test_connect("h", 22, "u", "p", "nokia_srl", retries=3, backoff_s=0)
            mock_inner.send_command.assert_called_once_with(
                "info system information", read_timeout=30
            )
            mock_inner.disconnect.assert_called_once()

    def test_unknown_device_type_only_connects(self) -> None:
        # Vendors without an exercise hook fall back to connect-only.
        from unittest.mock import MagicMock
        with patch("netmiko.ConnectHandler") as mock_conn, \
             patch("tests.e2e.harness.connect.time.sleep"):
            mock_inner = MagicMock()
            mock_conn.return_value = mock_inner
            smoke_test_connect("h", 22, "u", "p", "ios_xe_unknown", retries=3, backoff_s=0)
            mock_inner.send_command.assert_not_called()
            mock_inner.disconnect.assert_called_once()

    def test_paramiko_logger_restored_after_smoke(self) -> None:
        # The retry loop temporarily silences paramiko.transport to suppress
        # the noisy banner-reset stack traces. The pre-loop level must be
        # restored even on success so unrelated paramiko errors aren't hidden
        # for the rest of the session.
        import logging as _logging
        from unittest.mock import MagicMock
        paramiko_log = _logging.getLogger("paramiko.transport")
        prev = paramiko_log.level
        paramiko_log.setLevel(_logging.WARNING)
        try:
            with patch("netmiko.ConnectHandler") as mock_conn, \
                 patch("tests.e2e.harness.connect.time.sleep"):
                mock_conn.return_value = MagicMock()
                smoke_test_connect("h", 22, "u", "p", "ceos", retries=3, backoff_s=0)
            assert paramiko_log.level == _logging.WARNING
        finally:
            paramiko_log.setLevel(prev)

    def test_paramiko_logger_restored_after_smoke_failure(self) -> None:
        import logging as _logging
        paramiko_log = _logging.getLogger("paramiko.transport")
        prev = paramiko_log.level
        paramiko_log.setLevel(_logging.INFO)
        try:
            with patch("netmiko.ConnectHandler") as mock_conn, \
                 patch("tests.e2e.harness.connect.time.sleep"):
                mock_conn.side_effect = RuntimeError("nope")
                with pytest.raises(RuntimeError):
                    smoke_test_connect("h", 22, "u", "p", "ceos", retries=2, backoff_s=0)
            assert paramiko_log.level == _logging.INFO
        finally:
            paramiko_log.setLevel(prev)


class TestSshMasterKeepalive:
    """Issue #5: long remote runs lose port-forwards mid-suite without keepalive."""

    def test_base_args_sets_server_alive_interval(self) -> None:
        m = SshMaster(host="example.invalid")
        args = m.base_args()
        assert "ServerAliveInterval=30" in args
        assert "ServerAliveCountMax=3" in args

    def test_base_args_sets_exit_on_forward_failure(self) -> None:
        m = SshMaster(host="example.invalid")
        assert "ExitOnForwardFailure=yes" in m.base_args()

    def test_base_args_keeps_control_persist(self) -> None:
        m = SshMaster(host="example.invalid")
        assert "ControlPersist=60s" in m.base_args()


class TestSshMasterDiagnostics:
    def test_check_returns_true_when_master_alive(self) -> None:
        m = SshMaster(host="example.invalid")
        with patch("tests.e2e.harness.ssh.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Master running (pid=12345)\n", stderr="",
            )
            alive, output = m.check()
            assert alive is True
            assert "Master running" in output
            argv = mock_run.call_args.args[0]
            assert argv[-2:] == ["-O", "check"]

    def test_check_returns_false_when_master_dead(self) -> None:
        m = SshMaster(host="example.invalid")
        with patch("tests.e2e.harness.ssh.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=255, stdout="", stderr="Control socket connect: No such file\n",
            )
            alive, output = m.check()
            assert alive is False
            assert "No such file" in output

    def test_dump_state_writes_artifact(self, tmp_path: Path) -> None:
        m = SshMaster(host="clab01", user="alice", port=2222)
        with patch("tests.e2e.harness.ssh.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Master running (pid=99)\n", stderr="",
            )
            m._tunnels.append((63327, "172.20.0.2", 22))
            m.dump_state(tmp_path)
        text = (tmp_path / "ssh_master.txt").read_text()
        assert "host: clab01" in text
        assert "user: alice" in text
        assert "port: 2222" in text
        assert "master_alive: True" in text
        assert "63327 -> 172.20.0.2:22" in text


class TestPerVendorBudgets:
    def test_ceos_deadline_covers_remote_clab(self) -> None:
        # Issue #4: 180s was insufficient on remote clab.
        assert HEALTH_DEADLINE_S["ceos"] >= 300

    def test_smoke_retries_cover_known_flaky_vendors(self) -> None:
        # Issues #4 (cEOS banner reset) and #7 (nokia_srl prompt detection)
        # both need a budget >3 to ride out the SSH-up race on remote clab.
        assert SMOKE_RETRIES["ceos"] > 3
        assert SMOKE_RETRIES["nokia_srlinux"] > 3
