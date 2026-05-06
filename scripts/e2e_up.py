"""Deploy the session topology and write a sample inventory.yaml.

Used by `make e2e-up` for interactive debugging.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make `tests` importable when running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.e2e.harness.inventory import write_inventory
from tests.e2e.harness.local_executor import LocalExecutor
from tests.e2e.harness.remote_executor import RemoteExecutor
from tests.e2e.topologies import session_three_vendor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("NCLI_E2E_HOST"))
    parser.add_argument("--out", default="tests/e2e/_scratch/inventory.yaml")
    args = parser.parse_args()

    if args.host:
        ex = RemoteExecutor(host=args.host)
    else:
        ex = LocalExecutor()
    ex.preflight()

    topo = session_three_vendor()
    lab = ex.deploy(topo)
    try:
        endpoints = {n.name: ex.resolve(lab, n.name) for n in topo.nodes}
    except Exception:
        # If any node fails to come up, don't leave the lab running.
        ex.destroy(lab)
        raise

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_inventory(out_path, endpoints)
    print(f"Lab deployed: {lab.name}")
    print(f"Inventory:    {out_path}")
    print(f"Topology:     {lab.topology_yaml_path}")
    print()
    print("Tear down with: make e2e-down")
    # Persist the lab name so e2e-down can find it
    state = out_path.parent / "lab.txt"
    state.write_text(f"{lab.name}\n{lab.topology_yaml_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
