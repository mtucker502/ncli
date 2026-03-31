from __future__ import annotations

import sys
from pathlib import Path

import click

from ncli.cli.main import CliContext, pass_context
from ncli.device.config_ops import config_diff as do_config_diff
from ncli.device.config_ops import config_push as do_config_push
from ncli.device.connection import NetmikoConnection
from ncli.output.formatter import format_output
from ncli.safety.blocklist import check_config, get_config_blocklist
from ncli.template.renderer import render_config


@click.group()
def config() -> None:
    """Manage device configurations."""


@config.command("show")
@click.argument("device_name")
@click.argument("section", required=False, default=None)
@pass_context
def config_show(ctx: CliContext, device_name: str, section: str | None) -> None:
    """Show running configuration."""
    device_config = ctx.get_device(device_name)
    creds = ctx.auth.resolve(device_name, device_config)

    with NetmikoConnection(device_name, device_config, creds) as conn:
        output = conn.get_config(section=section)

    click.echo(format_output(output, ctx.output_format))


@config.command("diff")
@click.argument("device_name")
@click.option("--candidate", type=click.Path(exists=True, path_type=Path), default=None, help="Candidate config file")
@pass_context
def config_diff(ctx: CliContext, device_name: str, candidate: Path | None) -> None:
    """Show config diff."""
    device_config = ctx.get_device(device_name)
    creds = ctx.auth.resolve(device_name, device_config)

    candidate_text = candidate.read_text() if candidate else None

    with NetmikoConnection(device_name, device_config, creds) as conn:
        output = do_config_diff(conn, candidate=candidate_text)

    if output:
        click.echo(output)
    else:
        click.echo("No differences found")


@config.command("push")
@click.argument("device_name")
@click.argument("config_source", required=False, default=None)
@click.option("--stdin", "use_stdin", is_flag=True, help="Read config from stdin")
@click.option("--dry-run", is_flag=True, help="Preview without applying")
@click.option("--comment", default=None, help="Commit comment")
@pass_context
def config_push(
    ctx: CliContext,
    device_name: str,
    config_source: str | None,
    use_stdin: bool,
    dry_run: bool,
    comment: str | None,
) -> None:
    """Push configuration to a device."""
    if use_stdin:
        config_text = click.get_text_stream("stdin").read()
    elif config_source:
        config_text = Path(config_source).read_text()
    else:
        click.echo("Error: provide config file or --stdin", err=True)
        sys.exit(1)

    config_lines = [line for line in config_text.splitlines() if line.strip()]

    blocklist = get_config_blocklist()
    blocked = check_config(config_lines, blocklist)
    if blocked:
        click.echo("Blocked config lines:", err=True)
        for line in blocked:
            click.echo(f"  {line}", err=True)
        sys.exit(2)

    device_config = ctx.get_device(device_name)
    creds = ctx.auth.resolve(device_name, device_config)

    with NetmikoConnection(device_name, device_config, creds) as conn:
        output = do_config_push(conn, config_lines, dry_run=dry_run, comment=comment)

    if dry_run:
        click.echo("Dry-run — would push:")
    click.echo(output)


@config.command("template")
@click.option("-t", "--template", "template_path", required=True, type=click.Path(exists=True, path_type=Path), help="Jinja2 template file")
@click.option("-V", "--variables", "variables_path", required=True, type=click.Path(exists=True, path_type=Path), help="Variables YAML file")
@click.option("-r", "--device", "device_names", multiple=True, help="Target device(s)")
@click.option("--apply", "do_apply", is_flag=True, help="Apply rendered config")
@click.option("--dry-run", is_flag=True, help="Preview without applying")
@pass_context
def config_template(
    ctx: CliContext,
    template_path: Path,
    variables_path: Path,
    device_names: tuple[str, ...],
    do_apply: bool,
    dry_run: bool,
) -> None:
    """Render and optionally apply a Jinja2 config template."""
    rendered = render_config(template_path, variables_path)

    if not do_apply:
        click.echo(rendered)
        return

    config_lines = [line for line in rendered.splitlines() if line.strip()]

    blocklist = get_config_blocklist()
    blocked = check_config(config_lines, blocklist)
    if blocked:
        click.echo("Blocked config lines:", err=True)
        for line in blocked:
            click.echo(f"  {line}", err=True)
        sys.exit(2)

    if not device_names:
        click.echo("Error: --device required when using --apply", err=True)
        sys.exit(1)

    for name in device_names:
        device_config = ctx.get_device(name)
        creds = ctx.auth.resolve(name, device_config)

        with NetmikoConnection(name, device_config, creds) as conn:
            output = do_config_push(conn, config_lines, dry_run=dry_run)

        click.echo(f"--- {name} ---")
        if dry_run:
            click.echo("Dry-run — would push:")
        click.echo(output)
