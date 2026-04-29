# ncli end-to-end harness

The e2e suite stands up a real Junos / Arista / Nokia network with
[containerlab][clab] and exercises the ncli CLI surface against it.

## Run modes

| Setting | Mode | Behavior |
|---|---|---|
| (default) | local | clab subprocess on the test host |
| `--clab-host=<host>` or `NCLI_E2E_HOST=<host>` | remote | SSH to host, port-forward each node into the test process |

## Prerequisites

**Local mode** (Linux only):

- Docker (daemon reachable as the test user)
- containerlab >= 0.50
- Vendor images:
  - `crpd:latest` — Juniper, requires a J-Net account
  - `ceos:latest` — Arista, requires an arista.com account
  - `ghcr.io/nokia/srlinux:latest` — Nokia, public

**Remote mode** (any OS that can SSH):

- A reachable host meeting all local-mode prereqs
- SSH key-based auth into that host (the harness uses `ControlMaster`)

## Running

```bash
# Unit tests only (default — no clab dependencies)
pytest

# Full e2e suite, local mode
pytest -m clab

# Full e2e suite, remote mode
NCLI_E2E_HOST=clab01 pytest -m clab

# Hard-fail on missing images instead of skipping (CI mode)
NCLI_E2E_STRICT=1 pytest -m clab
```

## Interactive debugging

```bash
# Deploy session topology + write a sample inventory.yaml
make e2e-up                 # local
make e2e-up HOST=clab01     # remote

# Now use ncli interactively against the deployed lab
ncli -f tests/e2e/_scratch/inventory.yaml command run crpd1 "show version"

# Tear down
make e2e-down
```

## CI integration shape

Two stages:

1. `pytest` (unit only) — any Linux/macOS runner.
2. `pytest -m clab` — self-hosted runner with `NCLI_E2E_STRICT=1` and the
   three images preloaded. ~6 minutes wall clock.

[clab]: https://containerlab.dev
