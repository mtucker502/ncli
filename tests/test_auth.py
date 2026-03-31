"""Tests for authentication plugins and registry."""

from __future__ import annotations

import pytest

from ncli.auth.base import Credentials
from ncli.auth.static import StaticAuth
from ncli.auth import registry as auth_registry


class TestStaticAuthPassword:
    def test_password_auth(self) -> None:
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "password",
                "username": "admin",
                "password": "secret",
                "enable_secret": "en_secret",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.username == "admin"
        assert creds.password == "secret"
        assert creds.enable_secret == "en_secret"
        assert creds.key_file is None
        assert creds.use_ssh_agent is False

    def test_password_auth_defaults(self) -> None:
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "password",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.username == ""
        assert creds.password is None

    def test_password_auth_fallback_username(self) -> None:
        auth = StaticAuth()
        config = {
            "username": "fallback_user",
            "auth": {
                "type": "password",
                "password": "pw",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.username == "fallback_user"

    def test_auth_block_username_overrides_top_level(self) -> None:
        auth = StaticAuth()
        config = {
            "username": "fallback_user",
            "auth": {
                "type": "password",
                "username": "auth_user",
                "password": "pw",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.username == "auth_user"


class TestStaticAuthSSHKey:
    def test_ssh_key_with_file(self) -> None:
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "ssh_key",
                "username": "keyuser",
                "key_file": "/home/user/.ssh/id_rsa",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.username == "keyuser"
        assert creds.key_file == "/home/user/.ssh/id_rsa"
        assert creds.use_ssh_agent is False
        assert creds.password is None

    def test_ssh_key_no_file_uses_agent(self) -> None:
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "ssh_key",
                "username": "agentuser",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.key_file is None
        assert creds.use_ssh_agent is True

    def test_ssh_key_with_enable_secret(self) -> None:
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "ssh_key",
                "username": "keyuser",
                "key_file": "/tmp/key",
                "enable_secret": "en123",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.enable_secret == "en123"


class TestStaticAuthUnknownType:
    def test_unknown_type_raises(self) -> None:
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "kerberos",
            },
        }
        with pytest.raises(ValueError, match="unknown auth type 'kerberos'"):
            auth.resolve("dev1", config)


class TestStaticAuthEnvOverrides:
    def test_env_username_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NCLI_USERNAME", "env_user")
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "password",
                "username": "config_user",
                "password": "pw",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.username == "env_user"

    def test_env_password_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NCLI_PASSWORD", "env_pass")
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "password",
                "username": "user",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.password == "env_pass"

    def test_env_enable_secret_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NCLI_ENABLE_SECRET", "env_enable")
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "password",
                "username": "user",
                "enable_secret": "config_enable",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.enable_secret == "env_enable"

    def test_no_env_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NCLI_USERNAME", raising=False)
        monkeypatch.delenv("NCLI_PASSWORD", raising=False)
        monkeypatch.delenv("NCLI_ENABLE_SECRET", raising=False)
        auth = StaticAuth()
        config = {
            "auth": {
                "type": "password",
                "username": "normal",
                "password": "normal_pw",
            },
        }
        creds = auth.resolve("dev1", config)
        assert creds.username == "normal"
        assert creds.password == "normal_pw"

    def test_empty_auth_block(self) -> None:
        auth = StaticAuth()
        config: dict = {}
        creds = auth.resolve("dev1", config)
        assert creds.username == ""
        assert creds.password is None


class TestAuthRegistry:
    def test_static_registered_by_default(self) -> None:
        cls = auth_registry.get("static")
        assert cls is StaticAuth

    def test_get_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            auth_registry.get("nonexistent")

    def test_register_custom(self) -> None:
        from ncli.auth.base import AuthPlugin

        class DummyAuth(AuthPlugin):
            def resolve(self, device_name: str, device_config: dict) -> Credentials:
                return Credentials(username="dummy")

        auth_registry.register("dummy_test", DummyAuth)
        assert auth_registry.get("dummy_test") is DummyAuth
