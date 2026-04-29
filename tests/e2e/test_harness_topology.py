"""Unit tests for the in-process topology / vendor model.

These tests do NOT need Docker or containerlab — they exercise pure data
structures and YAML emission. Hence: no @pytest.mark.clab.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

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
        from tests.e2e.harness.topology import Node, Topology
        from tests.e2e.harness.vendor import Vendor

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


from unittest.mock import patch

from tests.e2e.harness.images import ImageProbe


class TestImageProbe:
    def test_local_probe_present(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            probe = ImageProbe.local()
            assert probe.has_image("ceos:latest") is True
            args = mock_run.call_args.args[0]
            assert args[:3] == ["docker", "image", "inspect"]
            assert "ceos:latest" in args

    def test_local_probe_missing(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            probe = ImageProbe.local()
            assert probe.has_image("nonexistent:tag") is False
