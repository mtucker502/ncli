"""Tests for output formatting module."""

from __future__ import annotations

import json

from ncli.output.formatter import (
    OutputFormat,
    format_output,
    format_device_list,
    format_error,
)


class TestFormatOutput:
    def test_text_string(self) -> None:
        result = format_output("hello world", OutputFormat.TEXT)
        assert result == "hello world"

    def test_text_dict(self) -> None:
        result = format_output({"key": "value"}, OutputFormat.TEXT)
        assert "key" in result
        assert "value" in result

    def test_json(self) -> None:
        data = {"hostname": "R1", "uptime": 3600}
        result = format_output(data, OutputFormat.JSON)
        parsed = json.loads(result)
        assert parsed["hostname"] == "R1"
        assert parsed["uptime"] == 3600

    def test_json_with_non_serializable(self) -> None:
        from pathlib import Path
        data = {"path": Path("/tmp/test")}
        result = format_output(data, OutputFormat.JSON)
        parsed = json.loads(result)
        assert parsed["path"] == "/tmp/test"

    def test_xml(self) -> None:
        data = {"hostname": "R1"}
        result = format_output(data, OutputFormat.XML)
        assert "<hostname>R1</hostname>" in result
        assert "<root>" in result

    def test_xml_list(self) -> None:
        data = ["item1", "item2"]
        result = format_output(data, OutputFormat.XML)
        assert "<item>" in result

    def test_default_format_is_text(self) -> None:
        result = format_output("test")
        assert result == "test"


class TestFormatDeviceList:
    def test_sanitizes_passwords(self) -> None:
        devices = {
            "dev1": {
                "host": "10.0.0.1",
                "auth": {
                    "password": "supersecret",
                    "username": "admin",
                },
            },
        }
        result = format_device_list(devices, OutputFormat.TEXT)
        assert "supersecret" not in result
        assert "***" in result
        assert "admin" in result

    def test_sanitizes_nested_secrets(self) -> None:
        devices = {
            "dev1": {
                "host": "10.0.0.1",
                "secret": "enable_pw",
                "token": "api_tok",
            },
        }
        result = format_device_list(devices, OutputFormat.TEXT)
        assert "enable_pw" not in result
        assert "api_tok" not in result

    def test_json_format(self) -> None:
        devices = {
            "dev1": {
                "host": "10.0.0.1",
                "device_type": "cisco_ios",
                "auth": {"password": "secret"},
            },
        }
        result = format_device_list(devices, OutputFormat.JSON)
        parsed = json.loads(result)
        assert parsed["dev1"]["auth"]["password"] == "***"
        assert parsed["dev1"]["host"] == "10.0.0.1"

    def test_xml_format(self) -> None:
        devices = {
            "dev1": {
                "host": "10.0.0.1",
            },
        }
        result = format_device_list(devices, OutputFormat.XML)
        assert "<host>10.0.0.1</host>" in result

    def test_sanitizes_list_values(self) -> None:
        devices = {
            "dev1": {
                "host": "10.0.0.1",
                "credentials": [{"password": "secret", "user": "admin"}],
            },
        }
        result = format_device_list(devices, OutputFormat.JSON)
        parsed = json.loads(result)
        assert parsed["dev1"]["credentials"][0]["password"] == "***"
        assert parsed["dev1"]["credentials"][0]["user"] == "admin"


class TestFormatError:
    def test_text_error(self) -> None:
        result = format_error("something went wrong", OutputFormat.TEXT)
        assert result == "ERROR: something went wrong"

    def test_json_error(self) -> None:
        result = format_error("something went wrong", OutputFormat.JSON)
        parsed = json.loads(result)
        assert parsed["error"] == "something went wrong"

    def test_xml_error(self) -> None:
        result = format_error("something went wrong", OutputFormat.XML)
        assert "<error>something went wrong</error>" in result
