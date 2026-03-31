# Writing Auth Plugins

NCLI's authentication is pluggable. The built-in `StaticAuth` reads credentials from the inventory and environment variables. You can implement custom auth plugins for secrets managers, vaults, or other credential stores.

## The AuthPlugin Interface

All auth plugins extend `ncli.auth.base.AuthPlugin` and return a `Credentials` dataclass:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Credentials:
    username: str
    password: str | None = None
    key_file: str | None = None
    use_ssh_agent: bool = False
    enable_secret: str | None = None


class AuthPlugin(ABC):
    @abstractmethod
    def resolve(self, device_name: str, device_config: dict) -> Credentials:
        """Resolve credentials for a device.

        Parameters:
            device_name: Human-friendly device identifier
            device_config: Full device config dict from inventory

        Returns:
            Credentials instance used to establish the SSH connection
        """
        ...
```

## Credentials Fields

| Field | Type | Used For |
|-------|------|----------|
| `username` | str | SSH username (required) |
| `password` | str \| None | SSH password |
| `key_file` | str \| None | Path to SSH private key file |
| `use_ssh_agent` | bool | Use SSH agent for key authentication |
| `enable_secret` | str \| None | Enable/secret password (Cisco), passed as Netmiko `secret` |

The `NetmikoConnection` maps these to Netmiko's `ConnectHandler` arguments:

- `username` -> `username`
- `password` -> `password`
- `enable_secret` -> `secret`
- `key_file` -> `key_file`
- `use_ssh_agent=True` -> `use_keys=True, allow_agent=True`

## Example: HashiCorp Vault Plugin

```python
import hvac

from ncli.auth.base import AuthPlugin, Credentials


class VaultAuth(AuthPlugin):
    def __init__(self, vault_url: str, vault_token: str, mount: str = "secret") -> None:
        self._client = hvac.Client(url=vault_url, token=vault_token)
        self._mount = mount

    def resolve(self, device_name: str, device_config: dict) -> Credentials:
        # Read from Vault at secret/data/ncli/{device_name}
        secret = self._client.secrets.kv.v2.read_secret_version(
            path=f"ncli/{device_name}",
            mount_point=self._mount,
        )
        data = secret["data"]["data"]

        return Credentials(
            username=data["username"],
            password=data.get("password"),
            key_file=data.get("key_file"),
            enable_secret=data.get("enable_secret"),
        )
```

## Example: AWS Secrets Manager Plugin

```python
import json

import boto3

from ncli.auth.base import AuthPlugin, Credentials


class AWSSecretsAuth(AuthPlugin):
    def __init__(self, prefix: str = "ncli/") -> None:
        self._client = boto3.client("secretsmanager")
        self._prefix = prefix

    def resolve(self, device_name: str, device_config: dict) -> Credentials:
        secret_id = f"{self._prefix}{device_name}"
        response = self._client.get_secret_value(SecretId=secret_id)
        data = json.loads(response["SecretString"])

        return Credentials(
            username=data["username"],
            password=data.get("password"),
            enable_secret=data.get("enable_secret"),
        )
```

## Registering Your Plugin

```python
from ncli.auth.registry import register
from my_plugins.vault import VaultAuth

register("vault", VaultAuth)
```

Retrieve it later:

```python
from ncli.auth.registry import get

plugin_class = get("vault")
auth = plugin_class(vault_url="https://vault.example.com", vault_token="s.xxxxx")
creds = auth.resolve("asa-01", device_config)
```

The built-in `StaticAuth` is registered as `"static"` by default.

## How StaticAuth Works

For reference, the built-in `StaticAuth` resolves credentials in this order:

1. Read `auth.type` from device config (`"password"` or `"ssh_key"`, defaults to `"password"`)
2. Extract username from auth block, falling back to device-level `username`
3. For `password` type: extract `password` and `enable_secret` from auth block
4. For `ssh_key` type: extract `key_file` (if absent, enable SSH agent)
5. Apply environment variable overrides: `NCLI_USERNAME`, `NCLI_PASSWORD`, `NCLI_ENABLE_SECRET`

Environment variable overrides always win, regardless of auth plugin.

## Tips

- Keep `resolve()` fast -- it's called per-device, per-command
- Cache credentials if your backend has high latency
- Raise clear exceptions with the device name when resolution fails
- Consider fallback behavior: you can check the inventory first, then the external source
