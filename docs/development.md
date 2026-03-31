# Development

## Setup

```bash
git clone https://github.com/mtucker502/ncli.git
cd ncli
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

This installs NCLI in editable mode with pytest and ruff.

## Running Tests

```bash
python -m pytest tests/ -v
```

All tests mock Netmiko connections -- no real SSH sessions are created. Tests run in under 1 second.

### Test Structure

```
tests/
  conftest.py          # Shared fixtures (tmp inventory, sample configs, mock creds)
  test_inventory.py    # Inventory loading, saving, defaults, groups, validation
  test_auth.py         # StaticAuth, env var overrides, SSH key auth
  test_connection.py   # NetmikoConnection (mocked ConnectHandler)
  test_config_ops.py   # config_push, config_diff
  test_blocklist.py    # Blocklist loading, command/config checking
  test_formatter.py    # TEXT/JSON/XML output, credential sanitization
  test_template.py     # Jinja2 rendering, variable loading
  test_cli.py          # CLI commands via Click's CliRunner
```

### Key Fixtures

- `tmp_inventory_path` -- creates a temp YAML inventory with sample devices. Uses valid Netmiko device types.
- `sample_device_config` -- returns a typical device config dict
- `mock_credentials` -- returns a `Credentials` instance for testing

## Linting

```bash
ruff check src/ tests/
```

NCLI uses ruff with Python 3.12 target and 120-char line length (configured in `pyproject.toml`).

Fix auto-fixable issues:

```bash
ruff check --fix src/ tests/
```

## Project Structure

```
ncli/
  pyproject.toml           # Build config (hatchling), deps, tool config
  .python-version          # 3.12
  src/ncli/                # Source code
  tests/                   # Unit tests
  examples/                # Sample inventory, blocklists
  skills/                  # Claude Code skill
  docs/                    # Documentation
```

## Adding a CLI Command

1. Create or edit a file in `src/ncli/cli/commands/`
2. Define a Click command or group
3. Register it in `src/ncli/cli/main.py` via `cli.add_command()`
4. Use `@pass_context` to access `CliContext` (inventory, auth, output format)
5. Add tests using Click's `CliRunner`

Example:

```python
# src/ncli/cli/commands/mycommand.py
import click
from ncli.cli.main import CliContext, pass_context

@click.command()
@click.argument("name")
@pass_context
def mycommand(ctx: CliContext, name: str) -> None:
    """Do something."""
    device = ctx.get_device(name)
    click.echo(f"Device: {name}, Host: {device['host']}")
```

```python
# src/ncli/cli/main.py
from ncli.cli.commands.mycommand import mycommand
cli.add_command(mycommand)
```

## Adding a New Module

1. Create a package under `src/ncli/`
2. Export public API from `__init__.py`
3. Add tests in `tests/test_<module>.py`
4. Wire it into the CLI commands if needed

## Dependencies

| Package | Required | Purpose |
|---------|----------|---------|
| click >=8.1.0 | Yes | CLI framework |
| netmiko >=4.3.0 | Yes | Multi-vendor SSH |
| jinja2 >=3.1.0 | Yes | Template rendering |
| pyyaml >=6.0 | Yes | YAML inventory |
| ntc-templates >=6.0.0 | Optional | TextFSM structured parsing |
| pytest >=9.0.0 | Dev | Testing |
| ruff >=0.14.0 | Dev | Linting |

## Release Checklist

1. Update `__version__` in `src/ncli/__init__.py`
2. Run full test suite: `python -m pytest tests/ -v`
3. Run linter: `ruff check src/ tests/`
4. Update CHANGELOG if maintained
5. Tag and push: `git tag v0.x.0 && git push --tags`
