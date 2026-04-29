"""Topology builder functions used by fixtures.

Each builder returns a fresh `Topology` with a UUID-suffixed lab name.
"""

from __future__ import annotations

from tests.e2e.harness.topology import Node, Topology
from tests.e2e.harness.vendor import VENDORS


def session_three_vendor() -> Topology:
    """Three nodes, one per vendor, no links — for read-only suite."""
    return Topology(
        nodes=[
            Node(name="crpd1", vendor=VENDORS["crpd"]),
            Node(name="ceos1", vendor=VENDORS["ceos"]),
            Node(name="srl1", vendor=VENDORS["nokia_srlinux"]),
        ]
    )


def isolated(vendor_key: str) -> Topology:
    """Single node of one vendor — for write-test parameterization."""
    vendor = VENDORS[vendor_key]
    short = {"crpd": "crpd", "ceos": "ceos", "nokia_srlinux": "srl"}[vendor_key]
    return Topology(nodes=[Node(name=short, vendor=vendor)])
