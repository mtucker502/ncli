# NCLI - Network Device Management Skill

You can manage network devices using the `ncli` CLI tool. NCLI wraps Netmiko to provide multi-vendor SSH access to routers, switches, firewalls, and other network equipment.

## Setup

Before using ncli, activate the virtual environment:

```bash
source /home/spider/ncli/.venv/bin/activate
```

## Listing and Querying Devices

List all devices in the inventory:

```bash
ncli device list
```

Filter by group or tag:

```bash
ncli device list --group firewalls
ncli device list --tag role:firewall
```

Get detailed info for a specific device (credentials are masked):

```bash
ncli device info asa-01
```

Use `--json` or `-j` for machine-readable JSON output on any command:

```bash
ncli --json device list
```

## Running Show Commands

Run a single show command on a device:

```bash
ncli command run asa-01 "show version"
```

Run multiple commands in one session (reuses the SSH connection):

```bash
ncli command multi asa-01 "show version" "show interface" "show running-config"
```

Use `--stop-on-error` to abort on the first failure:

```bash
ncli command multi asa-01 "show version" "show ip route" --stop-on-error
```

Run one command across many devices (batch mode):

```bash
ncli command batch "show version" asa-01 sw-dc1-01
ncli command batch "show version" --group firewalls
ncli command batch "show version" --group firewalls --parallel 5
```

## Pushing Configuration Safely

Always use `--dry-run` first to preview what will be sent:

```bash
ncli config push asa-01 "logging host 10.0.0.5" --dry-run
```

Push configuration lines to a device:

```bash
ncli config push asa-01 "logging host 10.0.0.5"
```

Push multi-line config from stdin:

```bash
echo -e "logging host 10.0.0.5\nlogging trap informational" | ncli config push asa-01 --stdin
```

Add a comment for audit purposes:

```bash
ncli config push asa-01 "logging host 10.0.0.5" --comment "Add syslog server"
```

## Using Templates

Render a Jinja2 template with variables and optionally apply it:

```bash
ncli config template -t templates/syslog.j2 -V vars/dc1.yaml
ncli config template -t templates/syslog.j2 -V vars/dc1.yaml -r asa-01 --apply --dry-run
ncli config template -t templates/syslog.j2 -V vars/dc1.yaml -r asa-01 --apply
```

## Viewing Running Config

Show the full running config:

```bash
ncli config show asa-01
```

Show a specific section:

```bash
ncli config show asa-01 interface
```

## Safety and Blocklists

NCLI enforces command and config blocklists. If a command matches a blocked pattern, it is rejected with exit code 2.

Set blocklist files via environment variables:

```bash
export NCLI_BLOCK_CMD=/home/spider/ncli/examples/block.cmd
export NCLI_BLOCK_CFG=/home/spider/ncli/examples/block.cfg
```

Or pass them via CLI options (if supported).

Blocked commands include dangerous operations like `reload`, `write erase`, `delete`, `format`, and `erase`. Blocked config commands include `no shutdown`, `crypto key zeroize`, and `license boot`.

## Important Notes

- NCLI uses ephemeral SSH sessions: each command opens a new connection and closes it when done.
- Credentials can be overridden with environment variables: `NCLI_USERNAME`, `NCLI_PASSWORD`, `NCLI_ENABLE_SECRET`.
- Exit codes: 0 = success, 1 = error, 2 = blocked by safety.
- Always use `--dry-run` before pushing config to production devices.
- Use `--json` output when you need to parse results programmatically.
