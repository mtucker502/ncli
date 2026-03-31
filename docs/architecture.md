# Architecture

## Module Layout

```
src/ncli/
  __init__.py              # __version__
  cli/
    main.py                # Click group, CliContext, global options
    commands/
      device.py            # device list|info|add|remove|reload
      command.py           # command run|multi|batch
      config.py            # config show|diff|push|template
  inventory/
    base.py                # InventoryPlugin ABC
    yaml_inventory.py      # YAML file inventory
    registry.py            # Plugin registry
  auth/
    base.py                # AuthPlugin ABC + Credentials dataclass
    static.py              # Inventory + env var credential resolution
    registry.py            # Plugin registry
  device/
    connection.py          # NetmikoConnection wrapper
    validation.py          # Device config validation
    config_ops.py          # config_push, config_diff
  safety/
    blocklist.py           # Command/config regex blocklists
  template/
    renderer.py            # Jinja2 template rendering
  output/
    formatter.py           # TEXT/JSON/XML formatting + credential sanitization
```

## Request Flow

A typical command execution flows through these layers:

```
CLI (Click)
  -> CliContext (loads inventory, resolves output format)
    -> Inventory plugin (loads devices from YAML)
    -> Auth plugin (resolves credentials)
    -> Safety check (command/config blocklist)
    -> NetmikoConnection (SSH session)
      -> Netmiko ConnectHandler (actual SSH)
    -> Output formatter (TEXT/JSON/XML + sanitization)
```

## Connection Model

NCLI uses **ephemeral sessions** -- a new SSH connection is established per CLI invocation and torn down when the command completes. There is no persistent session daemon.

`NetmikoConnection` is a context manager:

```python
with NetmikoConnection(name, config, creds) as conn:
    output = conn.send_command("show version")
# connection closed automatically
```

Netmiko handles low-level details:
- Terminal pager disable (`terminal pager 0`, `terminal length 0`)
- Enable mode entry (when `secret` is provided)
- Prompt detection
- Platform-specific command syntax

### Parallel Execution

`command batch` supports parallel connections via `--parallel N`. This uses a `ThreadPoolExecutor` with N workers, each opening its own SSH session.

## Plugin System

Both inventory and auth use the same registry pattern:

```python
# Module-level singleton dict
_registry: dict[str, type[PluginClass]] = {}

def register(name: str, cls: type[PluginClass]) -> None:
    _registry[name] = cls

def get(name: str) -> type[PluginClass]:
    if name not in _registry:
        raise KeyError(...)
    return _registry[name]

# Default plugin registered at import time
register("yaml", YamlInventory)
register("static", StaticAuth)
```

This is intentionally simple for v1. Future versions may use entry points for auto-discovery of third-party plugins.

## Config Push Abstraction

`config_ops.py` adds a thin layer over Netmiko's `send_config_set()`:

- **Dry-run**: returns the candidate config without touching the device
- **Auto-commit**: calls `conn.commit()` on platforms that need it (`junos`, `arista_eos`, `cisco_xr`)
- **Commit comment**: passed through to `commit(comment=...)` on supported platforms

For platforms without explicit commit (Cisco IOS, ASA, NX-OS), config is applied immediately by `send_config_set()`.

## Output Sanitization

The output formatter recursively walks device data structures and replaces values of sensitive keys with `"***"`. Sensitive key detection is substring-based against:

```
password, secret, key, private_key, token, auth_key, community, passphrase
```

This ensures credentials never appear in `device list`, `device info`, or any JSON/XML output.

## Design Decisions

1. **Netmiko device_type as-is** -- no abstraction layer. Users specify raw Netmiko strings, validated against `CLASS_MAPPER_BASE` at inventory load time.

2. **Ephemeral sessions** -- connect per command. Simple, stateless, no daemon. Matches the jcli model.

3. **TextFSM optional** -- `pip install ncli[textfsm]` adds ntc-templates. The `--textfsm` flag gracefully falls back to raw output if templates aren't installed.

4. **Shallow defaults merging** -- `{**defaults, **device_config}`. No deep merge of nested dicts. Device values always win.

5. **Regex blocklists** -- simple, auditable, file-based. No complex rule engine.
