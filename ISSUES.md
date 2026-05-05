# Issues

Tracking known e2e suite issues against `clab01`. Run baseline:

```
NCLI_E2E_STRICT=1 NCLI_E2E_HOST=clab01 uv run pytest -m clab -v
# 4 failed, 26 passed, 11 skipped, 158 deselected in 1163.74s
```

After the fixes below (2026-05-05):

```
# 30 passed, 11 skipped, 169 deselected in 1134.46s
```

---

## Issue 0: 2026-05-05 baseline failing tests (regression checklist)

Tracking the four e2e tests that were failing on `clab01` at baseline, separate from the per-root-cause issues below. Use this list as a regression check — if any of these regress, the linked root-cause section is the place to start.

| # | Test | Root cause | Status |
|---|------|------------|--------|
| 1 | `tests/e2e/test_config_push.py::test_config_push_lands_then_visible_in_show[nokia_srlinux]` | [Issue 1a](#issue-1a-nokia_srl-push-doesnt-commit-candidate-private-discarded-on-disconnect) — missing `commit()` call | resolved |
| 2 | `tests/e2e/test_config_template.py::test_template_apply_pushes[nokia_srlinux]` | [Issue 1a](#issue-1a-nokia_srl-push-doesnt-commit-candidate-private-discarded-on-disconnect) — missing `commit()` call | resolved |
| 3 | `tests/e2e/test_config_push.py::test_config_push_lands_then_visible_in_show[ceos]` | [Issue 1b](#issue-1b-ceos-push-fails-on-netmiko-config_mode-prompt-timeout) — missing `enable()` after connect | resolved |
| 4 | `tests/e2e/test_config_template.py::test_template_apply_pushes[ceos]` | [Issue 1b](#issue-1b-ceos-push-fails-on-netmiko-config_mode-prompt-timeout) — missing `enable()` after connect | resolved |

Plus one stale unit test:

| # | Test | Root cause | Status |
|---|------|------------|--------|
| 5 | `tests/test_connection.py::TestNetmikoConnectionContextManager::test_connect_with_ssh_key` | [Issue 3](#issue-3-stale-assertion-in-test_connect_with_ssh_key) — assertion didn't track impl change in `8776b40` | resolved |

Verification command (runs the four e2e tests as a focused regression):

```
NCLI_E2E_STRICT=1 NCLI_E2E_HOST=clab01 uv run pytest -m clab -v \
  'tests/e2e/test_config_push.py::test_config_push_lands_then_visible_in_show[ceos]' \
  'tests/e2e/test_config_push.py::test_config_push_lands_then_visible_in_show[nokia_srlinux]' \
  'tests/e2e/test_config_template.py::test_template_apply_pushes[ceos]' \
  'tests/e2e/test_config_template.py::test_template_apply_pushes[nokia_srlinux]'
# Expected: 4 passed in ~245s
```

## Issue 1a: nokia_srl push doesn't commit (candidate-private discarded on disconnect)

Failing tests (nokia_srlinux variants — confirmed passing against live `clab01` after the commit fix):

- [x] `tests/e2e/test_config_push.py::test_config_push_lands_then_visible_in_show[nokia_srlinux]`
- [x] `tests/e2e/test_config_template.py::test_template_apply_pushes[nokia_srlinux]`

Symptom: `ncli config push` returns 0, `ncli config show` returns 0, but the pushed banner string is absent from `info` output.

Root cause: `nokia_srl` is not in `_COMMIT_PLATFORMS` in `src/ncli/device/config_ops.py`. Netmiko's `NokiaSrlSSH.send_config_set` overrides the default to `exit_config_mode=False` (intentional — the driver expects the caller to invoke `commit()`). `config_mode()` enters `enter candidate private`. Because we never call `commit()`, the candidate is implicitly discarded when the SSH session ends, and running config is unchanged.

Progress:

- [x] Add `nokia_srl` to commit dispatch in `src/ncli/device/config_ops.py`
- [x] Drive-by: drop `arista_eos` from `_COMMIT_PLATFORMS` (Netmiko's arista driver inherits `BaseConnection.commit()` which raises `AttributeError`; `configure terminal` is immediate so no commit step is needed). cEOS push fails earlier today (see Issue 1b), masking this latent bug.
- [x] Unit tests in `tests/test_config_ops.py`: `test_push_commits_on_nokia_srl` (RED→GREEN), `test_push_no_commit_on_arista_eos`; updated `test_push_commits_with_comment` to use `cisco_xr` (real `commit(comment=...)` support).
- [x] Re-run e2e against live `clab01` confirmed both failing tests now pass (2 passed in 93.47s, 2026-05-05).
- [x] `info` returned the pushed banner cleanly after commit — no need to switch show-step subtree.

## Issue 1b: cEOS push fails on Netmiko `config_mode()` prompt timeout

Failing tests (cEOS variants — confirmed passing against live `clab01` after the connect-time enable() fix):

- [x] `tests/e2e/test_config_push.py::test_config_push_lands_then_visible_in_show[ceos]`
- [x] `tests/e2e/test_config_template.py::test_template_apply_pushes[ceos]`

Root cause (from Netmiko `session_log` capture, 2026-05-05): cEOS lands the SSH session in **user mode** (`ceos-clab>`), not privileged mode, despite the startup-config setting `username admin privilege 15 role network-admin`. From user mode, `configure terminal` is rejected with `% Invalid input (privileged mode required)` and the post-`(config)#` prompt never returns — the failure surfaces as a `read_until_pattern` ReadTimeout at the Netmiko config_mode layer, masking the underlying mode issue. The same root cause makes `show running-config` return `% Invalid input (privileged mode required)` in `ncli config show` once push is fixed.

Investigation log (preserved as a record of what was already ruled out):

- ~~Bump `read_timeout_override` for arista pushes (60s)~~ — did not help; not a timing issue.
- ~~Bump `SMOKE_RETRIES["ceos"]` from 10→20~~ — not a smoke retry issue.
- ~~Make smoke_test_connect drive `config_mode()` itself~~ — reproduces the same prompt failure but adds noise; reverted.
- Session_log capture (`NCLI_SESSION_LOG_DIR`) on a failing run revealed the actual bytes: `ceos-clab>configure terminal\n% Invalid input (privileged mode required)`.

Resolved:

- [x] `NetmikoConnection.connect()` calls `conn.enable()` for `_CISCO_LIKE_PLATFORMS` (`src/ncli/device/connection.py`). enable() is a no-op when already in enable mode, so the cost on healthy paths is one extra check.
- [x] `read_timeout_override=60` for arista_eos kept (defense-in-depth, harmless).
- [x] `tests/e2e/harness/connect.py` smoke_test_connect now sends a vendor-specific readiness command (`show version` / `info system information`) so SSH+CLI readiness — not just banner — is the gate; logs success on retry attempts.
- [x] `NCLI_SESSION_LOG_DIR` env var added (`src/ncli/device/connection.py`); diagnostic-only NCLI_* passthroughs whitelisted in `tests/e2e/harness/env.py::clean_env`.
- [x] Unit tests pin: enable() invoked on connect for arista_eos, skipped for juniper_junos.
- [x] Re-run e2e against live `clab01` confirmed both failing tests now pass (2 passed in 145.43s, 2026-05-05).

## Issue 2: Paramiko SSH banner / connection reset errors during smoke-connect

Logs contain repeated `paramiko.ssh_exception.SSHException: Error reading SSH protocol banner[Errno 54] Connection reset by peer` during the `tests.e2e.harness.connect` smoke-connect retry loop. Does not fail tests — the retry budget eventually succeeds — but the loud paramiko ERROR-level multi-frame stack trace pollutes logs.

Findings:

- The reset originates at the device side: cEOS sshd accepts TCP and starts the SSH banner exchange while `EOS Warmup Service` is still starting; paramiko's banner read sees a connection reset until warmup completes (~30-60s after TCP 22 opens). The `0b0dbd5` budgets (ceos=10×3s, nokia_srlinux=6×3s) ride out this gap; observed runs against `clab01` succeed within attempts 1–3 on healthy paths and hit double-digit attempts only when the host is loaded.
- It is not the SSH ControlMaster / port-forward layer (the keepalive + `dump_diagnostics` work in `aea04ea` rules that out — `ssh_master.txt` artifacts consistently show `master_alive: True` even when the test fails on something else).

Resolved:

- [x] `smoke_test_connect` now sends a vendor-specific readiness command (`show version` for arista_eos / juniper_junos, `info system information` for nokia_srl) instead of just connect-and-disconnect, so the retry budget covers SSH+CLI readiness — not just banner readiness — closing the gap that surfaced as Issue 1b.
- [x] `smoke_test_connect` temporarily lowers `paramiko.transport`'s log level to CRITICAL during the retry loop, suppressing the multi-frame banner-read stack trace per attempt. The pre-loop level is restored on both success and failure (unit-tested). Our own one-line `WARNING smoke connect attempt N/M failed` still fires per attempt for visibility.
- [x] On retry success, a single `INFO smoke connect succeeded on attempt N/M (<vendor>)` log lets us see whether the budget is being burned. (At default pytest log levels this is suppressed; bump to `--log-cli-level=INFO` to surface.)
- [x] `tests/e2e/test_harness_topology.py` pins both behaviors: `test_paramiko_logger_restored_after_smoke` (success path) and `test_paramiko_logger_restored_after_smoke_failure` (RuntimeError path).

## Issue 3: Stale assertion in `test_connect_with_ssh_key`

Failing test (unit, not e2e):

- [x] `tests/test_connection.py::TestNetmikoConnectionContextManager::test_connect_with_ssh_key`

Symptom: `assert "use_keys" not in call_kwargs` fails — `use_keys=True` is now in the kwargs.

Root cause: commit `8776b40 Fix SSH key auth and add bcd-fw-den-ssl device` correctly added `params["use_keys"] = True` to `NetmikoConnection.connect()` for the `key_file` branch (Netmiko ignores `key_file` unless `use_keys=True`). The unit test was not updated to match. The implementation is correct; the test is stale.

Resolved: assertion flipped to `assert call_kwargs["use_keys"] is True` in `tests/test_connection.py:102`. Test passes.
