"""Tests for inventory loading, saving, defaults merging, groups, and registry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ncli.inventory.yaml_inventory import YamlInventory
from ncli.inventory import registry as inv_registry


class TestYamlInventoryLoad:
    def test_load_returns_devices(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        devices = inv.load()
        assert "firewall1" in devices
        assert "switch1" in devices
        assert "router1" in devices

    def test_defaults_merging(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        devices = inv.load()
        # firewall1 should inherit device_type from defaults
        assert devices["firewall1"]["device_type"] == "cisco_asa"
        # switch1 overrides defaults
        assert devices["switch1"]["device_type"] == "arista_eos"

    def test_defaults_auth_merged(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        devices = inv.load()
        assert devices["firewall1"]["auth"]["username"] == "admin"

    def test_get_groups(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        inv.load()
        groups = inv.get_groups()
        assert "datacenter" in groups
        assert "firewall1" in groups["datacenter"]
        assert "switch1" in groups["datacenter"]

    def test_get_defaults(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        inv.load()
        defaults = inv.get_defaults()
        assert defaults["device_type"] == "cisco_asa"

    def test_tags_present(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        devices = inv.load()
        assert "core" in devices["switch1"]["tags"]
        assert "edge" in devices["router1"]["tags"]


class TestYamlInventorySave:
    def test_save_writes_yaml(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        devices = inv.load()
        devices["newdev"] = {"host": "10.10.10.10", "device_type": "cisco_ios"}
        inv.save(devices)

        # Reload and verify
        raw = yaml.safe_load(tmp_inventory_path.read_text())
        assert "newdev" in raw["devices"]
        assert raw["devices"]["newdev"]["host"] == "10.10.10.10"

    def test_save_preserves_groups(self, tmp_inventory_path: Path) -> None:
        inv = YamlInventory(tmp_inventory_path)
        devices = inv.load()
        inv.save(devices)

        raw = yaml.safe_load(tmp_inventory_path.read_text())
        assert "groups" in raw
        assert "datacenter" in raw["groups"]


class TestYamlInventoryValidation:
    def test_invalid_device_type_raises(self, tmp_path: Path) -> None:
        inv_data = {
            "devices": {
                "bad_device": {
                    "host": "1.2.3.4",
                    "device_type": "not_a_real_type",
                },
            },
        }
        inv_file = tmp_path / "bad.yaml"
        inv_file.write_text(yaml.dump(inv_data))

        inv = YamlInventory(inv_file)
        with pytest.raises(ValueError, match="invalid device_type"):
            inv.load()

    def test_missing_host_raises(self, tmp_path: Path) -> None:
        inv_data = {
            "devices": {
                "no_host": {
                    "device_type": "cisco_ios",
                },
            },
        }
        inv_file = tmp_path / "nohost.yaml"
        inv_file.write_text(yaml.dump(inv_data))

        inv = YamlInventory(inv_file)
        with pytest.raises(ValueError, match="missing required field 'host'"):
            inv.load()

    def test_missing_device_type_raises(self, tmp_path: Path) -> None:
        inv_data = {
            "devices": {
                "no_type": {
                    "host": "1.2.3.4",
                },
            },
        }
        inv_file = tmp_path / "notype.yaml"
        inv_file.write_text(yaml.dump(inv_data))

        inv = YamlInventory(inv_file)
        with pytest.raises(ValueError, match="missing required field 'device_type'"):
            inv.load()

    def test_empty_inventory_file(self, tmp_path: Path) -> None:
        inv_file = tmp_path / "empty.yaml"
        inv_file.write_text("")

        inv = YamlInventory(inv_file)
        devices = inv.load()
        assert devices == {}


class TestInventoryRegistry:
    def test_yaml_registered_by_default(self) -> None:
        cls = inv_registry.get("yaml")
        assert cls is YamlInventory

    def test_get_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            inv_registry.get("nonexistent_plugin")

    def test_register_custom(self) -> None:
        from ncli.inventory.base import InventoryPlugin

        class DummyInventory(InventoryPlugin):
            def load(self) -> dict[str, dict]:
                return {}
            def save(self, devices: dict[str, dict]) -> None:
                pass

        inv_registry.register("dummy", DummyInventory)
        assert inv_registry.get("dummy") is DummyInventory
