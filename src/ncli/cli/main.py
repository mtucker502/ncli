from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

from ncli import __version__
from ncli.auth.static import StaticAuth
from ncli.inventory.yaml_inventory import YamlInventory
from ncli.output.formatter import OutputFormat


class CliContext:
    def __init__(self) -> None:
        self.inventory: YamlInventory | None = None
        self.devices: dict[str, dict] = {}
        self.groups: dict[str, list[str]] = {}
        self.auth = StaticAuth()
        self.output_format = OutputFormat.TEXT
        self.verbose = False
        self.timeout: int | None = None

    def load_inventory(self, path: Path) -> None:
        self.inventory = YamlInventory(path)
        self.devices = self.inventory.load()
        self.groups = self.inventory.get_groups()

    def get_device(self, name: str) -> dict:
        if name not in self.devices:
            click.echo(f"Error: device '{name}' not found in inventory", err=True)
            sys.exit(1)
        return self.devices[name]

    def resolve_devices(
        self,
        names: tuple[str, ...] = (),
        group: str | None = None,
        tag: str | None = None,
    ) -> dict[str, dict]:
        result: dict[str, dict] = {}

        if group:
            group_members = self.groups.get(group, [])
            if not group_members:
                click.echo(f"Error: group '{group}' not found", err=True)
                sys.exit(1)
            for name in group_members:
                if name in self.devices:
                    result[name] = self.devices[name]

        if tag:
            for name, config in self.devices.items():
                if tag in config.get("tags", []):
                    result[name] = config

        for name in names:
            result[name] = self.get_device(name)

        return result if result else self.devices


def _find_skill_source() -> Path | None:
    # parents: main.py -> cli/ -> ncli/ -> src/ -> repo root
    src = Path(__file__).resolve().parents[3] / "skills" / "SKILL.md"
    if src.exists():
        return src
    try:
        import importlib.resources

        ref = importlib.resources.files("ncli").joinpath("skills/SKILL.md")
        p = Path(str(ref))
        if p.exists():
            return p
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    return None


def _install_skill(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    src = _find_skill_source()
    if src is None:
        click.echo("Error: skill file not found.", err=True)
        ctx.exit(1)
    dest_dir = Path.home() / ".claude" / "skills" / "ncli"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "SKILL.md"
    shutil.copy2(src, dest)
    click.echo(f"Installed ncli skill to {dest}")
    ctx.exit(0)


def _uninstall_skill(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    skill_dir = Path.home() / ".claude" / "skills" / "ncli"
    if not skill_dir.exists():
        click.echo("ncli skill is not installed.", err=True)
        ctx.exit(1)
    shutil.rmtree(skill_dir)
    click.echo(f"Uninstalled ncli skill from {skill_dir}")
    ctx.exit(0)


pass_context = click.make_pass_decorator(CliContext, ensure=True)

DEFAULT_INVENTORY = Path("inventory.yaml")


@click.group()
@click.version_option(__version__, prog_name="ncli")
@click.option("--json", "-j", "use_json", is_flag=True, help="Output as JSON")
@click.option("--xml", "-x", "use_xml", is_flag=True, help="Output as XML")
@click.option("--inventory", "-f", type=click.Path(exists=True, path_type=Path), default=None, help="Inventory file")
@click.option("--timeout", "-t", type=int, default=None, help="Connection timeout")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option(
    "--install-skill",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_install_skill,
    help="Install the ncli Claude Code skill to ~/.claude/skills/.",
)
@click.option(
    "--uninstall-skill",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_uninstall_skill,
    help="Uninstall the ncli Claude Code skill from ~/.claude/skills/.",
)
@pass_context
def cli(ctx: CliContext, use_json: bool, use_xml: bool, inventory: Path | None, timeout: int | None, verbose: bool) -> None:
    """NCLI — Multi-vendor network device CLI."""
    if use_json:
        ctx.output_format = OutputFormat.JSON
    elif use_xml:
        ctx.output_format = OutputFormat.XML

    ctx.verbose = verbose
    ctx.timeout = timeout

    if inventory is not None:
        inv_path = inventory
    elif DEFAULT_INVENTORY.exists():
        inv_path = DEFAULT_INVENTORY
    else:
        inv_path = Path.home() / ".config" / "ncli" / "inventory.yaml"
    if inv_path.exists():
        ctx.load_inventory(inv_path)


from ncli.cli.commands.device import device  # noqa: E402
from ncli.cli.commands.command import command  # noqa: E402
from ncli.cli.commands.config import config  # noqa: E402

cli.add_command(device)
cli.add_command(command)
cli.add_command(config)
