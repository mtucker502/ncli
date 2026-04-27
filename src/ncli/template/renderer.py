from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

ALLOWED_TEMPLATE_EXTENSIONS = {".j2", ".jinja", ".jinja2", ".txt", ".conf", ".cfg"}
ALLOWED_VARS_EXTENSIONS = {".yaml", ".yml", ".json"}


def _validate_file_path(file_path: Path, allowed_extensions: set[str], label: str) -> Path:
    """Resolve and validate a file path. Raises FileNotFoundError or ValueError."""
    resolved = file_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} not found: {file_path}")
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file: {file_path}")
    if resolved.suffix.lower() not in allowed_extensions:
        raise ValueError(
            f"{label} has unsupported extension '{resolved.suffix}'"
            f" (allowed: {', '.join(sorted(allowed_extensions))})"
        )
    return resolved


def render_template(template_path: Path, variables: dict) -> str:
    env = SandboxedEnvironment(
        loader=FileSystemLoader(str(template_path.parent)),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(template_path.name)
    return template.render(variables)


def load_variables(variables_path: Path) -> dict:
    return yaml.safe_load(variables_path.read_text()) or {}


def render_config(template_path: Path, variables_path: Path) -> str:
    template_path = _validate_file_path(
        Path(template_path), ALLOWED_TEMPLATE_EXTENSIONS, "Template file"
    )
    variables_path = _validate_file_path(
        Path(variables_path), ALLOWED_VARS_EXTENSIONS, "Variables file"
    )
    variables = load_variables(variables_path)
    return render_template(template_path, variables)
