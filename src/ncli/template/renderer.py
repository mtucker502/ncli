from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


def render_template(template_path: Path, variables: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(template_path.name)
    return template.render(variables)


def load_variables(variables_path: Path) -> dict:
    return yaml.safe_load(variables_path.read_text()) or {}


def render_config(template_path: Path, variables_path: Path) -> str:
    variables = load_variables(variables_path)
    return render_template(template_path, variables)
