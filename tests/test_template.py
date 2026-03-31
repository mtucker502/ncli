"""Tests for Jinja2 template renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ncli.template.renderer import render_template, load_variables, render_config


@pytest.fixture()
def template_file(tmp_path: Path) -> Path:
    tmpl = tmp_path / "config.j2"
    tmpl.write_text(
        "hostname {{ hostname }}\n"
        "interface {{ interface }}\n"
        " ip address {{ ip }} {{ mask }}\n"
    )
    return tmpl


@pytest.fixture()
def variables_file(tmp_path: Path) -> Path:
    data = {
        "hostname": "R1",
        "interface": "Loopback0",
        "ip": "1.1.1.1",
        "mask": "255.255.255.255",
    }
    vf = tmp_path / "vars.yaml"
    vf.write_text(yaml.dump(data))
    return vf


class TestRenderTemplate:
    def test_render_basic(self, template_file: Path) -> None:
        variables = {
            "hostname": "R1",
            "interface": "Loopback0",
            "ip": "1.1.1.1",
            "mask": "255.255.255.255",
        }
        result = render_template(template_file, variables)
        assert "hostname R1" in result
        assert "interface Loopback0" in result
        assert "ip address 1.1.1.1 255.255.255.255" in result

    def test_render_missing_var_raises(self, template_file: Path) -> None:
        from jinja2 import UndefinedError

        variables = {"hostname": "R1"}  # missing interface, ip, mask
        with pytest.raises(UndefinedError):
            render_template(template_file, variables)

    def test_render_preserves_newlines(self, tmp_path: Path) -> None:
        tmpl = tmp_path / "simple.j2"
        tmpl.write_text("line1\nline2\n")
        result = render_template(tmpl, {})
        assert result == "line1\nline2\n"


class TestLoadVariables:
    def test_load_from_yaml(self, variables_file: Path) -> None:
        v = load_variables(variables_file)
        assert v["hostname"] == "R1"
        assert v["ip"] == "1.1.1.1"

    def test_load_empty_file(self, tmp_path: Path) -> None:
        vf = tmp_path / "empty.yaml"
        vf.write_text("")
        v = load_variables(vf)
        assert v == {}

    def test_load_nested_variables(self, tmp_path: Path) -> None:
        data = {
            "interfaces": [
                {"name": "lo0", "ip": "1.1.1.1"},
                {"name": "lo1", "ip": "2.2.2.2"},
            ],
        }
        vf = tmp_path / "nested.yaml"
        vf.write_text(yaml.dump(data))
        v = load_variables(vf)
        assert len(v["interfaces"]) == 2


class TestRenderConfig:
    def test_render_config_end_to_end(self, template_file: Path, variables_file: Path) -> None:
        result = render_config(template_file, variables_file)
        assert "hostname R1" in result
        assert "interface Loopback0" in result
        assert "ip address 1.1.1.1 255.255.255.255" in result

    def test_render_config_with_loop(self, tmp_path: Path) -> None:
        tmpl = tmp_path / "loop.j2"
        tmpl.write_text(
            "{% for iface in interfaces %}\n"
            "interface {{ iface.name }}\n"
            " ip address {{ iface.ip }}\n"
            "{% endfor %}\n"
        )
        data = {
            "interfaces": [
                {"name": "lo0", "ip": "1.1.1.1"},
                {"name": "lo1", "ip": "2.2.2.2"},
            ],
        }
        vf = tmp_path / "loopvars.yaml"
        vf.write_text(yaml.dump(data))

        result = render_config(tmpl, vf)
        assert "interface lo0" in result
        assert "interface lo1" in result
        assert "ip address 1.1.1.1" in result
        assert "ip address 2.2.2.2" in result
