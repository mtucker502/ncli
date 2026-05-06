"""End-to-end tests for `ncli config template`."""

from __future__ import annotations

import pytest
import yaml

from tests.e2e.harness.env import run_ncli


def _template_for(device_type: str) -> tuple[str, dict]:
    if device_type == "juniper_junos":
        return "set system login message {{ banner }}\n", {"banner": "tmpl-junos"}
    if device_type == "arista_eos":
        return "banner login\n{{ banner }}\nEOF\n", {"banner": "tmpl-eos"}
    if device_type == "nokia_srl":
        return 'set / system banner login-banner "{{ banner }}"\n', {"banner": "tmpl-srl"}
    raise ValueError(device_type)


@pytest.mark.clab
def test_template_render_no_apply_prints(tmp_path, session_inventory, clab_session) -> None:
    tmpl = tmp_path / "t.j2"
    tmpl.write_text("set system login message {{ banner }}\n")
    vars_path = tmp_path / "v.yaml"
    vars_path.write_text("banner: render-only\n")

    proc = run_ncli(
        ["ncli", "-f", str(session_inventory), "config", "template",
         "-t", str(tmpl), "-V", str(vars_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0
    assert "render-only" in proc.stdout


@pytest.mark.clab
def test_template_apply_pushes(tmp_path, isolated_inventory, isolated_device) -> None:
    body, vars_doc = _template_for(isolated_device.device_type)
    tmpl = tmp_path / "t.j2"
    tmpl.write_text(body)
    vars_path = tmp_path / "v.yaml"
    vars_path.write_text(yaml.safe_dump(vars_doc))

    proc = run_ncli(
        ["ncli", "-f", str(isolated_inventory), "config", "template",
         "-t", str(tmpl), "-V", str(vars_path),
         "--apply", "-r", isolated_device.name],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr

    show = run_ncli(
        ["ncli", "-f", str(isolated_inventory), "config", "show", isolated_device.name],
        capture_output=True, text=True, timeout=120,
    )
    assert show.returncode == 0
    assert vars_doc["banner"] in show.stdout
