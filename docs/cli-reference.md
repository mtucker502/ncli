# CLI Reference

## Global Options

```
ncli [OPTIONS] COMMAND [ARGS]...
```

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | `-j` | Output as JSON |
| `--xml` | `-x` | Output as XML |
| `--inventory PATH` | `-f` | Inventory file (default: `inventory.yaml`) |
| `--timeout INT` | `-t` | Connection timeout in seconds |
| `--verbose` | `-v` | Verbose output |
| `--version` | | Show version and exit |
| `--help` | | Show help and exit |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (device not found, connection failure, etc.) |
| 2 | Blocked by safety blocklist |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `NCLI_USERNAME` | Override username for all devices |
| `NCLI_PASSWORD` | Override password for all devices |
| `NCLI_ENABLE_SECRET` | Override enable secret for all devices |
| `NCLI_BLOCK_CMD` | Path to command blocklist file |
| `NCLI_BLOCK_CFG` | Path to config blocklist file |

---

## `device` -- Inventory Management

### `device list`

List devices in the inventory. Credentials are sanitized in output.

```bash
ncli device list
ncli device list --group firewalls
ncli device list --tag role:firewall
ncli --json device list
```

| Option | Description |
|--------|-------------|
| `--group GROUP` / `-g` | Filter by group name |
| `--tag TAG` / `-t` | Filter by tag |

### `device info`

Show details for a single device (credentials sanitized).

```bash
ncli device info asa-01
```

### `device add`

Add a device to the inventory file.

```bash
ncli device add rtr-01 --host 10.0.2.1 --device-type cisco_ios
ncli device add rtr-01 --host 10.0.2.1 --device-type cisco_ios --username admin --password secret --port 2222
```

| Option | Required | Description |
|--------|----------|-------------|
| `--host` | Yes | Hostname or IP |
| `--device-type` | Yes | Netmiko device type |
| `--username` | No | Username |
| `--password` | No | Password |
| `--port` | No | SSH port |

The `device_type` is validated against Netmiko's supported types. Invalid types are rejected.

### `device remove`

Remove a device from the inventory file.

```bash
ncli device remove rtr-01
ncli device remove rtr-01 --force   # skip confirmation prompt
```

| Option | Description |
|--------|-------------|
| `--force` | Skip confirmation prompt |

### `device reload`

Reload the inventory from disk. Optionally specify a new path.

```bash
ncli device reload
ncli device reload /path/to/new/inventory.yaml
```

---

## `command` -- Run Commands

### `command run`

Run a single command on a device.

```bash
ncli command run asa-01 "show version"
ncli command run asa-01 "show ip route" --textfsm
ncli --json command run asa-01 "show version"
```

| Option | Description |
|--------|-------------|
| `--textfsm` | Parse output with TextFSM/ntc-templates. Falls back to raw if templates unavailable. |

### `command multi`

Run multiple commands on a single device in one SSH session.

```bash
ncli command multi asa-01 "show clock" "show version" "show ip route"
ncli command multi asa-01 "show clock" "show version" --stop-on-error
```

| Option | Description |
|--------|-------------|
| `--stop-on-error` | Stop executing remaining commands if an error is detected in output |

Error patterns detected: `% Invalid input`, `% Ambiguous command`, `% Incomplete command`, `Error:`.

### `command batch`

Run one command on multiple devices.

```bash
ncli command batch "show version" asa-01 sw-01
ncli command batch "show version" --group firewalls
ncli command batch "show version" --group firewalls --parallel 4
```

| Option | Description |
|--------|-------------|
| `--group GROUP` / `-g` | Target a device group |
| `--parallel N` / `-p` | Max parallel SSH connections (default: 1) |

---

## `config` -- Configuration Management

### `config show`

Show the running configuration.

```bash
ncli config show asa-01
ncli config show asa-01 interface    # IOS-style section filter
```

### `config diff`

Show a unified diff between running config and a candidate file.

```bash
ncli config diff asa-01 --candidate candidate.cfg
```

| Option | Description |
|--------|-------------|
| `--candidate FILE` | Path to candidate config file |

### `config push`

Push configuration to a device.

```bash
ncli config push asa-01 config.txt
ncli config push asa-01 config.txt --dry-run        # preview only
ncli config push asa-01 config.txt --comment "ACL update"
cat config.txt | ncli config push asa-01 --stdin
```

| Option | Description |
|--------|-------------|
| `--stdin` | Read config from stdin |
| `--dry-run` | Preview config without applying |
| `--comment TEXT` | Commit comment (for platforms that support it: Junos, EOS, IOS-XR) |

Blank lines in config are stripped. Config lines are checked against the config blocklist before pushing.

### `config template`

Render a Jinja2 template and optionally apply it to devices.

```bash
# Render only (print to stdout)
ncli config template -t acl.j2 -V vars.yaml

# Render and apply
ncli config template -t acl.j2 -V vars.yaml --apply -r asa-01 -r fw-01

# Render and dry-run
ncli config template -t acl.j2 -V vars.yaml --apply -r asa-01 --dry-run
```

| Option | Required | Description |
|--------|----------|-------------|
| `-t` / `--template` | Yes | Jinja2 template file |
| `-V` / `--variables` | Yes | Variables YAML file |
| `-r` / `--device` | With `--apply` | Target device(s), repeatable |
| `--apply` | No | Push rendered config to devices |
| `--dry-run` | No | Preview without pushing (requires `--apply`) |

Templates use Jinja2 with `StrictUndefined` -- undefined variables raise an error rather than rendering as empty strings.
