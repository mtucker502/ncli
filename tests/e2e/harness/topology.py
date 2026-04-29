"""Topology builder for clab YAML emission.

`Topology.to_clab_yaml()` produces a containerlab v0.50+ topology document.
Each topology gets a UUID-suffixed name so parallel pytest runs against the
same clab host don't collide.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field

import yaml

from tests.e2e.harness.vendor import Vendor


def _new_lab_name() -> str:
    return f"ncli-e2e-{uuid.uuid4().hex[:8]}"


@dataclass
class Node:
    name: str
    vendor: Vendor


@dataclass
class Topology:
    nodes: list[Node]
    name: str = field(default_factory=_new_lab_name)

    def required_kinds(self) -> set[str]:
        return {n.vendor.kind for n in self.nodes}

    def without_kinds(self, kinds: list[str]) -> Topology:
        drop = set(kinds)
        return Topology(
            nodes=[copy.deepcopy(n) for n in self.nodes if n.vendor.kind not in drop],
            name=self.name + "-sub",
        )

    def to_clab_yaml(self) -> str:
        nodes_doc: dict[str, dict] = {}
        for node in self.nodes:
            cfg: dict = {
                "kind": node.vendor.kind,
                "image": node.vendor.image,
            }
            if node.vendor.startup_config is not None:
                cfg["startup-config"] = str(node.vendor.startup_config)
            nodes_doc[node.name] = cfg

        doc = {
            "name": self.name,
            "topology": {"nodes": nodes_doc},
        }
        return yaml.safe_dump(doc, sort_keys=False)
