# NCLI

Multi-vendor network device CLI built on [Netmiko](https://github.com/ktbyers/netmiko). One tool for 150+ device types — Cisco, Arista, Juniper, and more.

Designed for both human operators and agentic AI (Claude Code).

## Install

Requires Python 3.12+.

```bash
git clone https://github.com/mtucker502/ncli.git && cd ncli
uv venv && source .venv/bin/activate
uv pip install -e .

# optional
uv pip install -e ".[textfsm]"   # structured parsing via ntc-templates
uv pip install -e ".[dev]"       # pytest + ruff
```

## Quick Start

Create `inventory.yaml`:

```yaml
defaults:
  username: admin
  timeout: 60

devices:
  asa-01:
    host: 10.0.3.1
    device_type: cisco_asa
    auth:
      type: password
      password: "cisco123"
      enable_secret: "en4bl3"
```

Run commands:

```bash
ncli device list                              # list all devices
ncli command run asa-01 "show version"        # single command
ncli command multi asa-01 "show clock" "show ip route"  # multiple commands
ncli command batch "show version" --group firewalls -p4  # parallel batch
ncli config push asa-01 config.txt --dry-run  # preview config push
ncli config template -t acl.j2 -V vars.yaml --apply -r asa-01  # templated config
```

Output as JSON or XML with `--json` / `--xml`.

## CLI Reference

```
ncli [--json|-j] [--xml|-x] [-f INVENTORY] [-t TIMEOUT] [-v]

  device list   [--group GROUP] [--tag TAG]
  device info   DEVICE
  device add    NAME --host HOST --device-type TYPE
  device remove NAME [--force]
  device reload [PATH]

  command run   DEVICE CMD [--textfsm]
  command multi DEVICE CMD [CMD...] [--stop-on-error]
  command batch CMD [DEVICE...] [--group GROUP] [--parallel N]

  config show     DEVICE [SECTION]
  config diff     DEVICE [--candidate FILE]
  config push     DEVICE CONFIG [--stdin] [--dry-run] [--comment TEXT]
  config template -t FILE -V FILE [-r DEVICE...] [--apply] [--dry-run]
```

Exit codes: `0` success, `1` error, `2` blocked by safety.

## Inventory Format

```yaml
defaults:          # merged into every device (device values win)
  username: admin
  timeout: 60
  port: 22

groups:            # named collections for --group targeting
  firewalls:
    - asa-01
    - fw-01

devices:
  asa-01:
    host: 10.0.3.1
    device_type: cisco_asa          # any netmiko device_type
    auth:
      type: password                # or ssh_key
      password: "cisco123"
      enable_secret: "en4bl3"
    tags: [role:firewall]           # for --tag filtering
```

`device_type` is validated against Netmiko's supported types at load time.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `NCLI_USERNAME` | Override username for all devices |
| `NCLI_PASSWORD` | Override password for all devices |
| `NCLI_ENABLE_SECRET` | Override enable secret |
| `NCLI_BLOCK_CMD` | Path to command blocklist file |
| `NCLI_BLOCK_CFG` | Path to config blocklist file |

## Safety

Command and config blocklists prevent dangerous operations. Blocklist files contain one regex per line (`#` comments). Blocked actions exit with code `2`.

```bash
# examples/block.cmd
^reload$
^write erase
^delete
```

Set via env var: `NCLI_BLOCK_CMD=block.cmd ncli command run asa-01 "reload"` — blocked.

## Plugins

**Inventory** — implement `InventoryPlugin` ABC (`load`, `save`, `get_groups`, `get_defaults`) for custom sources (NetBox, Ansible, etc).

**Auth** — implement `AuthPlugin` ABC (`resolve -> Credentials`) for custom credential backends (Vault, AWS Secrets Manager, etc).

## Development

```bash
python -m pytest tests/ -v    # 110 tests
ruff check src/ tests/        # lint
```

## License

MIT
