"""Shared helpers for parsing `containerlab inspect` JSON and per-vendor SSH-up budgets.

Both LocalExecutor and RemoteExecutor consume the same JSON shape and need the
same health deadlines; this module is the single owner.
"""

from __future__ import annotations


# Per-vendor SSH-up budget; cEOS notoriously takes the longest.
HEALTH_DEADLINE_S: dict[str, int] = {
    "crpd": 60,
    "nokia_srlinux": 60,
    "ceos": 180,
}


def find_node(inspect_doc: dict, lab_name: str, node_name: str) -> dict:
    """clab's inspect JSON shape: {"containers": [{name, lab_name, kind, ipv4_address, ...}]}.
    Some clab versions nest under {lab_name: [...]}.
    """
    candidates: list[dict] = []
    if isinstance(inspect_doc, dict):
        if "containers" in inspect_doc:
            candidates = inspect_doc["containers"]
        elif lab_name in inspect_doc:
            candidates = inspect_doc[lab_name]
        else:
            for v in inspect_doc.values():
                if isinstance(v, list):
                    candidates.extend(v)
    for c in candidates:
        # node names are prefixed with `clab-<lab>-` in clab; match suffix.
        cname = c.get("name") or c.get("Name", "")
        if cname.endswith(f"-{node_name}") or cname == node_name:
            return c
    raise KeyError(f"node {node_name!r} not found in inspect output for lab {lab_name!r}")


def extract_ipv4(node_doc: dict) -> str:
    for k in ("ipv4_address", "ipv4Address", "IPv4Address"):
        v = node_doc.get(k, "")
        if isinstance(v, str) and v:
            return v.split("/")[0]
    raise RuntimeError(f"No IPv4 address in node doc: {node_doc!r}")
