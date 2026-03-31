# Getting Started

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
git clone https://github.com/mtucker502/ncli.git
cd ncli
uv venv && source .venv/bin/activate
uv pip install -e .
```

Optional extras:

```bash
uv pip install -e ".[textfsm]"   # ntc-templates for structured parsing
uv pip install -e ".[dev]"       # pytest + ruff
```

Verify:

```bash
ncli --version
# ncli, version 0.1.0
```

## Create an Inventory

Create `inventory.yaml` in your working directory:

```yaml
defaults:
  username: admin
  timeout: 60
  port: 22

devices:
  asa-01:
    host: 10.0.3.1
    device_type: cisco_asa
    auth:
      type: password
      password: "cisco123"
      enable_secret: "en4bl3"

  sw-01:
    host: 10.0.1.1
    device_type: arista_eos
    auth:
      type: ssh_key
      key_file: ~/.ssh/id_ed25519
```

See [Inventory Schema](inventory-schema.md) for the full format reference.

## Run Your First Command

```bash
# List devices in the inventory
ncli device list

# Show details for a specific device
ncli device info asa-01

# Run a show command
ncli command run asa-01 "show version"

# JSON output
ncli --json device list
```

## Use a Different Inventory File

```bash
ncli -f /path/to/other/inventory.yaml device list
```

## Override Credentials via Environment

```bash
export NCLI_USERNAME=operator
export NCLI_PASSWORD=secret
ncli command run asa-01 "show clock"
```

Environment variables override whatever is in the inventory file. See the full list in [CLI Reference](cli-reference.md#environment-variables).

## Next Steps

- [CLI Reference](cli-reference.md) -- all commands and options
- [Configuration Management](configuration.md) -- pushing config, templates
- [Safety & Blocklists](safety.md) -- preventing dangerous commands
