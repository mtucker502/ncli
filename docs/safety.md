# Safety & Blocklists

NCLI includes a blocklist system to prevent accidental execution of dangerous commands or config changes. Blocked actions exit with code 2.

## How It Works

- **Command blocklist**: checked before every `command run`, `command multi`, and `command batch` invocation
- **Config blocklist**: checked before every `config push` and `config template --apply` invocation

If any command or config line matches a blocklist pattern, NCLI refuses to execute and exits with code 2.

## Blocklist File Format

Plain text, one regex pattern per line. Comments start with `#`. Blank lines are ignored. Patterns are case-insensitive.

### Command Blocklist (`block.cmd`)

```
# Reload and erase commands
^reload$
^write erase
^delete
^format
^erase

# Prevent firmware operations
^copy .* flash
^boot system
```

### Config Blocklist (`block.cfg`)

```
# Dangerous config commands
^no (shutdown|enable)
^crypto key zeroize
^license boot

# Prevent routing table wipes
^no router
```

## Enabling Blocklists

Set environment variables pointing to your blocklist files:

```bash
export NCLI_BLOCK_CMD=/path/to/block.cmd
export NCLI_BLOCK_CFG=/path/to/block.cfg
```

Sample blocklist files are in `examples/block.cmd` and `examples/block.cfg`.

## Behavior

### Blocked Command

```bash
$ NCLI_BLOCK_CMD=block.cmd ncli command run asa-01 "reload"
Blocked: command 'reload' matches blocklist
$ echo $?
2
```

### Blocked Config Line

```bash
$ NCLI_BLOCK_CFG=block.cfg ncli config push asa-01 bad.cfg
Blocked config lines:
  no shutdown
$ echo $?
2
```

All matching blocked lines are listed before aborting.

## Pattern Details

Patterns are Python regex, compiled with `re.IGNORECASE`. They match anywhere in the string unless anchored:

| Pattern | Matches | Doesn't Match |
|---------|---------|---------------|
| `^reload$` | `reload` | `show reload` |
| `^write erase` | `write erase`, `WRITE ERASE` | `show write` |
| `delete` | `delete flash:`, `no delete` | -- |
| `^no (shutdown\|enable)` | `no shutdown`, `no enable` | `shutdown` |

Use `^` and `$` anchors to match full commands. Without anchors, the pattern matches as a substring.

## Disabling Blocklists

Unset the environment variables:

```bash
unset NCLI_BLOCK_CMD
unset NCLI_BLOCK_CFG
```

When no env var is set, no blocklist is loaded and all commands/configs are allowed.
