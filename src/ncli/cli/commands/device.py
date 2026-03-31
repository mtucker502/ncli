from __future__ import annotations

import sys
from pathlib import Path

import click

from ncli.cli.main import CliContext, pass_context
from ncli.device.validation import validate_device_config
from ncli.output.formatter import format_device_list


@click.group()
def device() -> None:
    """Manage network devices in the inventory."""


@device.command("list")
@click.option("--group", "-g", default=None, help="Filter by group")
@click.option("--tag", "-t", default=None, help="Filter by tag")
@pass_context
def device_list(ctx: CliContext, group: str | None, tag: str | None) -> None:
    """List devices in the inventory."""
    devices = ctx.resolve_devices(group=group, tag=tag)
    click.echo(format_device_list(devices, ctx.output_format))


@device.command("info")
@click.argument("name")
@pass_context
def device_info(ctx: CliContext, name: str) -> None:
    """Show device details."""
    config = ctx.get_device(name)
    click.echo(format_device_list({name: config}, ctx.output_format))


@device.command("add")
@click.argument("name")
@click.option("--host", required=True, help="Device hostname or IP")
@click.option("--device-type", required=True, help="Netmiko device type")
@click.option("--username", default=None, help="Username")
@click.option("--password", default=None, help="Password")
@click.option("--port", type=int, default=None, help="SSH port")
@pass_context
def device_add(
    ctx: CliContext,
    name: str,
    host: str,
    device_type: str,
    username: str | None,
    password: str | None,
    port: int | None,
) -> None:
    """Add a device to the inventory."""
    if ctx.inventory is None:
        click.echo("Error: no inventory loaded", err=True)
        sys.exit(1)

    config: dict = {"host": host, "device_type": device_type}
    if username:
        config["username"] = username
    if password:
        config["auth"] = {"type": "password", "password": password}
    if port:
        config["port"] = port

    validate_device_config(name, config)
    ctx.devices[name] = config
    ctx.inventory.save(ctx.devices)
    click.echo(f"Added device '{name}'")


@device.command("remove")
@click.argument("name")
@click.option("--force", is_flag=True, help="Skip confirmation")
@pass_context
def device_remove(ctx: CliContext, name: str, force: bool) -> None:
    """Remove a device from the inventory."""
    if ctx.inventory is None:
        click.echo("Error: no inventory loaded", err=True)
        sys.exit(1)

    ctx.get_device(name)  # ensures it exists

    if not force:
        click.confirm(f"Remove device '{name}'?", abort=True)

    del ctx.devices[name]
    ctx.inventory.save(ctx.devices)
    click.echo(f"Removed device '{name}'")


@device.command("reload")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
@pass_context
def device_reload(ctx: CliContext, path: Path | None) -> None:
    """Reload the inventory."""
    if path:
        ctx.load_inventory(path)
    elif ctx.inventory:
        ctx.devices = ctx.inventory.load()
        ctx.groups = ctx.inventory.get_groups()
    else:
        click.echo("Error: no inventory to reload", err=True)
        sys.exit(1)

    click.echo(f"Reloaded inventory: {len(ctx.devices)} device(s)")
