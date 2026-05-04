# Configuration Management

NCLI provides tools for viewing, comparing, and pushing device configurations, including Jinja2 template support.

## Viewing Config

```bash
ncli config show asa-01
ncli config show asa-01 interface    # section filter (IOS-style)
```

Under the hood the command sent depends on the device's `device_type`:

- Cisco-style platforms (`cisco_ios`, `cisco_xe`, `cisco_nxos`, `cisco_asa`, `cisco_xr`/`cisco_iosxr`, `arista_eos`): `show running-config` (or `show running-config | section <filter>`).
- Junos (`juniper_junos`): `show configuration [<filter>] | display set | no-more`.
- Nokia SR Linux (`nokia_srl`): `info` (or `info <filter>`).

Other vendors raise `NotImplementedError` until explicit support is added.

## Config Diff

Compare running config against a candidate file:

```bash
ncli config diff asa-01 --candidate proposed.cfg
```

Output is a unified diff. No output means no differences.

## Pushing Config

### From a File

```bash
# Always dry-run first
ncli config push asa-01 changes.cfg --dry-run

# Then apply
ncli config push asa-01 changes.cfg
```

### From Stdin

```bash
echo "logging host 10.0.0.5" | ncli config push asa-01 --stdin
```

### With a Commit Comment

Platforms that support commit (Junos, EOS, IOS-XR) accept a comment:

```bash
ncli config push eos-01 changes.cfg --comment "Add monitoring ACL"
```

### How Config Push Works

1. Config text is read from file or stdin
2. Blank lines are stripped
3. Lines are checked against the config blocklist -- blocked lines cause exit code 2
4. Lines are sent via Netmiko's `send_config_set()`
5. On commit-capable platforms (`junos`, `arista_eos`, `cisco_xr`), a `commit()` is issued

## Jinja2 Templates

Templates let you generate config from reusable templates and variable files.

### Template File (Jinja2)

```jinja
{# acl.j2 #}
ip access-list extended {{ acl_name }}
{% for rule in rules %}
 {{ rule.action }} {{ rule.protocol }} {{ rule.source }} {{ rule.destination }}
{% endfor %}
```

### Variables File (YAML)

```yaml
# vars.yaml
acl_name: MONITORING
rules:
  - action: permit
    protocol: tcp
    source: 10.0.0.0/24
    destination: any eq 514
  - action: deny
    protocol: ip
    source: any
    destination: any
```

### Render Only

```bash
ncli config template -t acl.j2 -V vars.yaml
```

Prints the rendered config to stdout. Useful for review.

### Render and Apply

```bash
# Dry-run on one device
ncli config template -t acl.j2 -V vars.yaml --apply -r asa-01 --dry-run

# Apply to multiple devices
ncli config template -t acl.j2 -V vars.yaml --apply -r asa-01 -r fw-01
```

Templates use `StrictUndefined` -- a missing variable raises an error instead of silently rendering empty.

## Workflow

A safe config push workflow:

```bash
# 1. Render template, review output
ncli config template -t change.j2 -V vars.yaml

# 2. Dry-run against target device
ncli config template -t change.j2 -V vars.yaml --apply -r asa-01 --dry-run

# 3. Apply
ncli config template -t change.j2 -V vars.yaml --apply -r asa-01

# 4. Verify
ncli command run asa-01 "show running-config | include logging"
```
