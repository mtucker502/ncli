"""Vendor metadata for the e2e harness.

Each `Vendor` couples a containerlab `kind` to a Netmiko `device_type` plus the
default credentials from each platform's clab quickstart:

  crpd  → juniper_junos  (root / clab123)
  ceos  → arista_eos     (admin / admin)
  nokia_srlinux → nokia_srl (admin / NokiaSrl1!)

Image refs are intentionally generic (`:latest`) — the harness probes for them
on the executor host and skips per-vendor when missing. CI may pin via env
vars later if needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_CONFIGS_DIR = Path(__file__).resolve().parents[1] / "topologies" / "configs"


@dataclass(frozen=True)
class Vendor:
    kind: str           # containerlab kind: crpd / ceos / nokia_srlinux
    image: str          # docker image ref (probed via `docker image inspect`)
    netmiko_type: str   # juniper_junos / arista_eos / nokia_srl
    username: str
    password: str
    startup_config: Path | None  # path to a startup-config file, or None


VENDORS: dict[str, Vendor] = {
    "crpd": Vendor(
        kind="crpd",
        image="crpd:latest",
        netmiko_type="juniper_junos",
        username="root",
        password="clab123",
        startup_config=_CONFIGS_DIR / "crpd.startup.conf",
    ),
    "ceos": Vendor(
        kind="ceos",
        image="ceos:latest",
        netmiko_type="arista_eos",
        username="admin",
        password="admin",
        startup_config=_CONFIGS_DIR / "ceos.startup.cfg",
    ),
    "nokia_srlinux": Vendor(
        kind="nokia_srlinux",
        image="ghcr.io/nokia/srlinux:latest",
        netmiko_type="nokia_srl",
        username="admin",
        password="NokiaSrl1!",
        startup_config=_CONFIGS_DIR / "srl.startup.cfg",
    ),
}
