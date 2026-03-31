from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import click

from ncli.cli.main import CliContext, pass_context
from ncli.device.connection import NetmikoConnection
from ncli.output.formatter import format_output
from ncli.safety.blocklist import check_command, get_command_blocklist


@click.group()
def command() -> None:
    """Run commands on network devices."""


@command.command("run")
@click.argument("device_name")
@click.argument("cmd")
@click.option("--textfsm", is_flag=True, help="Parse output with TextFSM")
@pass_context
def command_run(ctx: CliContext, device_name: str, cmd: str, textfsm: bool) -> None:
    """Run a single command on a device."""
    blocklist = get_command_blocklist()
    if check_command(cmd, blocklist):
        click.echo(f"Blocked: command '{cmd}' matches blocklist", err=True)
        sys.exit(2)

    device_config = ctx.get_device(device_name)
    creds = ctx.auth.resolve(device_name, device_config)

    with NetmikoConnection(device_name, device_config, creds) as conn:
        output = conn.send_command(cmd, textfsm=textfsm)

    click.echo(format_output(output, ctx.output_format))


@command.command("multi")
@click.argument("device_name")
@click.argument("cmds", nargs=-1, required=True)
@click.option("--stop-on-error", is_flag=True, help="Stop on first error")
@pass_context
def command_multi(ctx: CliContext, device_name: str, cmds: tuple[str, ...], stop_on_error: bool) -> None:
    """Run multiple commands on a single device."""
    blocklist = get_command_blocklist()
    for cmd in cmds:
        if check_command(cmd, blocklist):
            click.echo(f"Blocked: command '{cmd}' matches blocklist", err=True)
            sys.exit(2)

    device_config = ctx.get_device(device_name)
    creds = ctx.auth.resolve(device_name, device_config)

    with NetmikoConnection(device_name, device_config, creds) as conn:
        results = conn.send_commands(list(cmds), stop_on_error=stop_on_error)

    for cmd, output in zip(cmds, results):
        click.echo(f"--- {cmd} ---")
        click.echo(format_output(output, ctx.output_format))
        click.echo()


@command.command("batch")
@click.argument("cmd")
@click.argument("device_names", nargs=-1)
@click.option("--group", "-g", default=None, help="Target group")
@click.option("--parallel", "-p", type=int, default=1, help="Max parallel connections")
@pass_context
def command_batch(
    ctx: CliContext,
    cmd: str,
    device_names: tuple[str, ...],
    group: str | None,
    parallel: int,
) -> None:
    """Run one command on multiple devices."""
    blocklist = get_command_blocklist()
    if check_command(cmd, blocklist):
        click.echo(f"Blocked: command '{cmd}' matches blocklist", err=True)
        sys.exit(2)

    targets = ctx.resolve_devices(names=device_names, group=group)
    if not targets:
        click.echo("No devices matched", err=True)
        sys.exit(1)

    def run_on_device(name: str, config: dict) -> tuple[str, str]:
        creds = ctx.auth.resolve(name, config)
        with NetmikoConnection(name, config, creds) as conn:
            return name, conn.send_command(cmd)

    if parallel <= 1:
        for name, config in targets.items():
            device_name, output = run_on_device(name, config)
            click.echo(f"--- {device_name} ---")
            click.echo(format_output(output, ctx.output_format))
            click.echo()
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {pool.submit(run_on_device, n, c): n for n, c in targets.items()}
            for future in as_completed(futures):
                try:
                    device_name, output = future.result()
                    click.echo(f"--- {device_name} ---")
                    click.echo(format_output(output, ctx.output_format))
                    click.echo()
                except Exception as exc:
                    click.echo(f"--- {futures[future]} ---", err=True)
                    click.echo(f"Error: {exc}", err=True)
