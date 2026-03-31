# Inventory Schema

NCLI uses a YAML inventory file to define devices, groups, and defaults. By default it looks for `inventory.yaml` in the current directory. Override with `ncli -f PATH`.

## Full Schema

```yaml
defaults:
  username: admin
  timeout: 60
  port: 22
  # Any key here is merged into every device.
  # Device-level values take precedence.

groups:
  firewalls:
    - asa-01
    - fw-01
  dc1-switches:
    - sw-dc1-01
    - sw-dc1-02

devices:
  asa-01:
    host: 10.0.3.1                  # required
    device_type: cisco_asa          # required, validated against Netmiko
    port: 22                        # optional, overrides default
    timeout: 30                     # optional, overrides default
    username: localadmin             # optional, overrides default
    auth:
      type: password                # "password" or "ssh_key"
      username: admin               # optional, overrides device-level username
      password: "cisco123"
      enable_secret: "en4bl3"       # optional, passed as Netmiko `secret`
    tags:
      - role:firewall
      - site:hq
```

## Top-Level Sections

### `defaults`

Optional. A flat dict of key-value pairs merged into every device entry. Device-level values always win.

```yaml
defaults:
  username: admin
  timeout: 60
  port: 22
```

If a device defines `timeout: 30`, it keeps 30. If it doesn't define `timeout`, it inherits 60 from defaults.

### `groups`

Optional. Named lists of device names. Used for batch targeting with `--group`.

```yaml
groups:
  firewalls:
    - asa-01
    - fw-01
```

```bash
ncli command batch "show version" --group firewalls
```

### `devices`

Required. Each key is a device name. Each value is a device configuration dict.

## Device Fields

| Field | Required | Description |
|-------|----------|-------------|
| `host` | Yes | Hostname or IP address |
| `device_type` | Yes | Netmiko device type string |
| `port` | No | SSH/Telnet port (default: 22) |
| `timeout` | No | Connection timeout in seconds |
| `username` | No | Username (can also come from defaults or auth block) |
| `auth` | No | Authentication block (see below) |
| `tags` | No | List of strings for `--tag` filtering |

### `device_type`

Must be a valid Netmiko device type. Validated at inventory load time against `netmiko.ssh_dispatcher.CLASS_MAPPER_BASE`. Common values:

| Value | Platform |
|-------|----------|
| `cisco_asa` | Cisco ASA |
| `cisco_ios` | Cisco IOS |
| `cisco_nxos` | Cisco NX-OS |
| `cisco_xr` | Cisco IOS-XR |
| `arista_eos` | Arista EOS |
| `juniper_junos` | Juniper Junos |
| `paloalto_panos` | Palo Alto PAN-OS |
| `linux` | Generic Linux |

Run `python -c "from netmiko.ssh_dispatcher import CLASS_MAPPER_BASE; print('\n'.join(sorted(CLASS_MAPPER_BASE)))"` to see all supported types.

## Auth Block

The `auth` block defines how NCLI authenticates to the device.

### Password Authentication

```yaml
auth:
  type: password
  username: admin          # optional, overrides device/default username
  password: "cisco123"
  enable_secret: "en4bl3"  # optional
```

### SSH Key Authentication

```yaml
auth:
  type: ssh_key
  username: admin
  key_file: ~/.ssh/id_ed25519    # path to private key
  enable_secret: "en4bl3"        # optional
```

If `key_file` is omitted, NCLI uses the SSH agent (`use_ssh_agent: true`).

### Environment Variable Overrides

These always take precedence over inventory values:

| Variable | Overrides |
|----------|-----------|
| `NCLI_USERNAME` | Username for all devices |
| `NCLI_PASSWORD` | Password for all devices |
| `NCLI_ENABLE_SECRET` | Enable secret for all devices |

## Tags

Tags are arbitrary strings on each device, used for filtering:

```yaml
devices:
  asa-01:
    host: 10.0.3.1
    device_type: cisco_asa
    tags:
      - role:firewall
      - site:hq
      - env:production
```

```bash
ncli device list --tag role:firewall
```

## Defaults Merging

Defaults are merged shallowly. Given:

```yaml
defaults:
  username: admin
  timeout: 60

devices:
  sw-01:
    host: 10.0.1.1
    device_type: arista_eos
    timeout: 30
```

The effective config for `sw-01` is:

```yaml
host: 10.0.1.1
device_type: arista_eos
username: admin      # from defaults
timeout: 30          # device value wins
```

## Modifying the Inventory

```bash
# Add a device
ncli device add rtr-01 --host 10.0.2.1 --device-type cisco_ios

# Remove a device
ncli device remove rtr-01 --force

# Reload from disk
ncli device reload
```

Changes from `device add` and `device remove` are persisted back to the YAML file.
