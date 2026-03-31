from __future__ import annotations

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


pass_context = click.make_pass_decorator(CliContext, ensure=True)

DEFAULT_INVENTORY = Path("inventory.yaml")


@click.group()
@click.version_option(__version__, prog_name="ncli")
@click.option("--json", "-j", "use_json", is_flag=True, help="Output as JSON")
@click.option("--xml", "-x", "use_xml", is_flag=True, help="Output as XML")
@click.option("--inventory", "-f", type=click.Path(exists=True, path_type=Path), default=None, help="Inventory file")
@click.option("--timeout", "-t", type=int, default=None, help="Connection timeout")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@pass_context
def cli(ctx: CliContext, use_json: bool, use_xml: bool, inventory: Path | None, timeout: int | None, verbose: bool) -> None:
    """NCLI — Multi-vendor network device CLI."""
    if use_json:
        ctx.output_format = OutputFormat.JSON
    elif use_xml:
        ctx.output_format = OutputFormat.XML

    ctx.verbose = verbose
    ctx.timeout = timeout

    inv_path = inventory or DEFAULT_INVENTORY
    if inv_path.exists():
        ctx.load_inventory(inv_path)


from ncli.cli.commands.device import device  # noqa: E402
from ncli.cli.commands.command import command  # noqa: E402
from ncli.cli.commands.config import config  # noqa: E402

cli.add_command(device)
cli.add_command(command)
cli.add_command(config)
