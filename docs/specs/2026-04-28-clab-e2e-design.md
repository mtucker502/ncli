# Containerlab end-to-end test harness — design

Status: approved
Date: 2026-04-28

## Goal

Stand up a real Junos / Arista / Nokia network on every test run and exercise the ncli CLI surface against it. Catches vendor-dispatch and CLI-surface regressions of the kind found in issue #1.

## Scope

### In scope

- Three vendors: Juniper cRPD, Arista cEOS, Nokia SR Linux. Three Netmiko `device_type`s: `juniper_junos`, `arista_eos`, `nokia_srl`.
- The full ncli CLI surface: `device list/info/add/remove`, `command run/multi/batch`, `config show/diff/push/template`, output formats (`-j`, `-x`), safety blocklists, exit codes.
- Two run targets:
  - **Local** — pytest runs on a host that itself has Docker + containerlab + the three images (e.g. self-hosted Actions runner, Linux contributor).
  - **Remote** — pytest runs anywhere with SSH to a host that has the prereqs (e.g. macOS contributor → `clab01`).
- Opt-in via `pytest -m clab`. Default `pytest` runs unit tests only.

### Out of scope

- BGP / OSPF / multi-node protocol scenarios. Topology is three isolated nodes; ncli is a CLI wrapper, not a network-state validator.
- TextFSM / structured-output coverage — `ntc-templates` is an optional dependency; gate separately if it grows real coverage needs.
- Cross-platform contributor-laptop docker support. macOS contributors target a remote clab host.

## Run-mode selection

Mode is chosen by `--clab-host=<host>` pytest CLI option (preferred) or `NCLI_E2E_HOST` environment variable.

| Setting | Mode | Behaviour |
|---|---|---|
| unset / `local` | local | clab subprocess on the test host |
| any hostname | remote | SSH to host, run clab there, port-forward each node into the test process |

Tests are mode-agnostic — they only ever consume `(host, port, username, password, device_type)` tuples resolved by the executor.

## Architecture

```
tests/
  e2e/
    __init__.py
    conftest.py                       # marker, --clab-host option, fixtures, skip logic
    harness/
      __init__.py
      executor.py                     # Executor ABC, LocalExecutor, RemoteExecutor
      topology.py                     # Topology builder, generates clab YAML
      endpoint.py                     # DeviceEndpoint dataclass
      images.py                       # ImageProbe (docker image inspect, local + remote)
    topologies/
      __init__.py
      session_three_vendor.py
      isolated.py
      configs/
        crpd.startup.conf             # minimal Junos startup so SSH is reachable
        ceos.startup.cfg              # minimal cEOS startup with admin/admin
        srl.startup.cfg               # minimal SRL startup with admin/NokiaSrl1!
    test_command_run.py
    test_config_show.py
    test_config_push.py
    test_config_diff.py
    test_config_template.py
    test_safety_blocklist.py
    test_device_inventory.py
    README.md
```

Tests touch `harness` only through pytest fixtures — never `subprocess.run("clab ...")` directly. The harness owns all clab/SSH/Docker mechanics, which keeps the local-vs-remote split out of test bodies.

## Components

### `Executor` ABC

```python
class Executor(ABC):
    def preflight(self) -> bool: ...                       # docker + clab present, SSH reachable
    def has_image(self, image_ref: str) -> bool: ...       # docker image inspect
    def deploy(self, topology: Topology) -> Lab: ...
    def destroy(self, lab: Lab) -> None: ...
    def resolve(self, lab: Lab, node_name: str) -> DeviceEndpoint: ...
    def close(self) -> None: ...                           # idempotent; tears down tunnels / SSH masters
```

`LocalExecutor` shells out to `clab deploy/destroy` directly and parses `clab inspect --format json` for the docker-bridge IPv4 of each node. `DeviceEndpoint.host` is the bridge IP, `port` is 22.

`RemoteExecutor` does the same over SSH. After deploy, it opens one SSH local-port-forward per node using a multiplexed `ControlMaster` connection (single TCP round trip per tunnel, single `ssh -O exit` to clean them all up). Local ports are allocated via `socket.bind(('', 0))` to avoid collisions with parallel pytest runs. `DeviceEndpoint.host` is `127.0.0.1`, `port` is the allocated localhost port.

### `Topology`

Topologies are generated programmatically — not checked-in YAML — so the harness can stamp out variants per test:

```python
@dataclass
class Vendor:
    kind: str            # clab kind: crpd / ceos / nokia_srlinux
    image: str
    netmiko_type: str    # juniper_junos / arista_eos / nokia_srl
    username: str
    password: str
    startup_config: Path | None

VENDORS = { "crpd": Vendor(...), "ceos": Vendor(...), "nokia_srlinux": Vendor(...) }

class Topology:
    name: str            # "ncli-e2e-{uuid8}"
    nodes: list[Node]
    def to_clab_yaml(self) -> str: ...
    def required_kinds(self) -> set[str]: ...
    def without_kinds(self, kinds: list[str]) -> Topology: ...

def session_three_vendor() -> Topology   # one of each, no links
def isolated(vendor: str) -> Topology    # single node of one vendor
```

Each topology gets a UUID-suffixed `name` so parallel pytest runs against the same clab host don't collide.

### Vendor defaults

| Vendor | clab kind | username | password | netmiko `device_type` |
|---|---|---|---|---|
| Juniper cRPD | `crpd` | `root` | `clab123` | `juniper_junos` |
| Arista cEOS | `ceos` | `admin` | `admin` | `arista_eos` |
| Nokia SR Linux | `nokia_srlinux` | `admin` | `NokiaSrl1!` | `nokia_srl` |

Startup configs in `tests/e2e/topologies/configs/` set just enough for SSH to be reachable with these defaults.

## Lifecycle

Hybrid:

- **Read-only tests** share a `clab_session` fixture (3-vendor topology). One deploy per pytest run, ~57s.
- **Write tests** use `isolated_device` (parameterized over vendors) — fresh single-vendor topology per test. cRPD ~38s, cEOS ~99s, SRL ~29s per deploy.

clab destroys are ~1–2s; cost is entirely in deploy.

Measured on clab01 (containerlab 0.73, clean Docker):

| Topology | Deploy | Destroy |
|---|---|---|
| cRPD only | 37.8s | ~1s |
| cEOS only | 98.8s | ~1s |
| SRL only | 28.6s | ~1s |
| All three | 57.1s | 1.8s |

Realistic ~25-test suite budget: ~57s session + 2 cRPD-write × 38s + 2 cEOS-write × 99s + 2 SRL-write × 29s ≈ 6 minutes wall clock.

## Pytest integration

```python
def pytest_addoption(parser):
    parser.addoption("--clab-host", default=None,
                     help="Remote SSH host running clab; unset = local")

def pytest_configure(config):
    config.addinivalue_line("markers", "clab: end-to-end test requiring containerlab")
```

`pyproject.toml` adds `addopts = -m "not clab"` so default `pytest` skips e2e. CI / contributors run `pytest -m clab` explicitly.

### Fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `executor` | session | Selects local vs remote, runs preflight, owns SSH masters and tunnels |
| `clab_session` | session | Three-vendor topology, deployed once |
| `isolated_device` | function (parameterized) | Fresh single-vendor topology per test |
| `inventory_path(tmp_path, ...)` | function | Writes a temp ncli inventory.yaml pointing at resolved endpoints |

Tests invoke ncli as a subprocess — `subprocess.run(["ncli", "-f", str(inv_path), ...])` — so the actual CLI surface (argparse, exit codes, formatted output) is what gets covered.

### Skip logic

Per-vendor: `isolated_device[ceos]` skips with reason if `executor.has_image("ceos:latest")` is False. The session topology subsets to only the vendors whose images are present.

`NCLI_E2E_STRICT=1` upgrades every skip-on-missing to a hard fail. Self-hosted runner runs in strict mode; contributors don't.

## Test matrix

| File | Test | Fixture | Vendors |
|---|---|---|---|
| `test_device_inventory.py` | `device list` lists all session devices | `clab_session` | n/a |
| | `device info` returns expected fields, password masked | `clab_session` | one |
| | `device add` then list shows it; `device remove` undoes | `clab_session` | n/a |
| `test_command_run.py` | `command run "show version"` exit 0, output non-empty | `clab_session` | all 3 |
| | `command run -j` returns valid JSON envelope | `clab_session` | crpd |
| | `command multi` runs N commands over one connection | `clab_session` | crpd, ceos |
| | `command batch` runs across multiple devices | `clab_session` | all 3 |
| | unknown device → exit 1 with clear stderr | `clab_session` | n/a |
| `test_config_show.py` | full config returned, vendor-appropriate format | `clab_session` | all 3 |
| | `config show <dev> <section>` filters | `clab_session` | crpd, ceos |
| `test_config_diff.py` | diff vs candidate file shows real running side | `clab_session` | crpd |
| | identical candidate → empty diff | `clab_session` | crpd |
| `test_config_push.py` | `--dry-run` returns rendered text, no device touch | `clab_session` | all 3 |
| | push + commit lands; verify via fresh `config show` | `isolated_device` | all 3 |
| | **issue #1 regression**: Junos commit comment with `#` and `>` lands | `isolated_device` | crpd |
| | comment with `"` raises ValueError, exit 1 | `isolated_device` | crpd |
| | bad config → exit 1, no partial state | `isolated_device` | crpd |
| `test_config_template.py` | template render no-apply prints rendered text | `clab_session` | n/a |
| | template `--apply` pushes & commits | `isolated_device` | all 3 |
| `test_safety_blocklist.py` | blocked exec command → exit 2, no device contact | `clab_session` | crpd |
| | blocked config line → exit 2, no commit | `clab_session` | crpd |

## Error handling and flake mitigation

- **Health gating**: after `deploy()` returns, the harness probes each device's SSH port with `socket.connect_ex` and exponential backoff (1, 2, 4, 8s; cap 60s for cRPD/SRL, 180s for cEOS). clab reports "running" before SSH is reachable, especially for cEOS — clab status alone is not trustworthy.
- **Mandatory cleanup**: every fixture wraps deploy in `try/finally`; `destroy` runs even on KeyboardInterrupt or pytest collection errors. The session executor registers an `atexit` hook as a backstop.
- **Leaked-lab recovery**: lab names embed a UUID, so a leak from a previous run won't conflict by name. A `make e2e-clean` target lists and destroys any lab matching `ncli-e2e-*` on the target host.
- **Connection retries**: Netmiko connection establishment retries 3× with 2s backoff (Netmiko occasionally drops the first session right after deploy). Test commands themselves do not retry — flaky results are real bugs.
- **Failure artifacts**: on any test failure under `-m clab`, conftest dumps `clab inspect`, last 200 lines of `docker logs <node>` per node, and the rendered inventory to `tests/e2e/_artifacts/<test_id>/`. CI uploads as artifact.

## Runner integration

CI matrix has two stages:

1. `pytest` (unit only) — runs on any Linux/macOS runner, no special setup.
2. `pytest -m clab` — runs only on the self-hosted runner. `NCLI_E2E_STRICT=1` set.

Contributors:

- `pytest` — unit tests, no prereqs.
- `NCLI_E2E_HOST=clab01 pytest -m clab` — e2e against shared clab host.
- Linux contributors with local clab: `pytest -m clab` (uses local executor).

`tests/e2e/README.md` documents prereqs (Docker, containerlab, the three images, vendor-account requirement for cEOS) and `make e2e-up` / `make e2e-down` targets for interactive debugging — they call into the same harness module so what you see manually matches what tests see.

## Decisions deferred to the implementation plan

- Exact containerlab version pin: pin in CI runner setup, free-floating for contributors.
- Whether `make e2e-up` writes a sample `inventory.yaml` in addition to the in-memory one tests use, so `ncli` is drop-in usable for manual debugging without re-deploying.

`tests/conftest.py` and `tests/e2e/conftest.py` are isolated — no shared fixtures, no cross-imports. The unit suite must remain runnable on a host with no Docker / clab / SSH dependencies.
