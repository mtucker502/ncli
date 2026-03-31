from __future__ import annotations

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
        ...
