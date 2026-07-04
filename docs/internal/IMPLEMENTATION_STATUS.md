# Implementation Status

## Current phase
- Phase: 6 GSD config bridge
- Batch: 2026-07-04 continuation after phase 5 batch
- Branch: main
- Started: 2026-07-03 Asia/Shanghai

## Scope
- In scope: AgentPolicyProfile defaults, default-only `.planning/config.json` merge, agent_skills bridge, advisory-only reporting, `sync-gsd`, doctor path/status reporting, user deletion protection, malformed JSON safety, and Pack cleanup helper.
- Out of scope: real GSD install, GSD vendoring/forking, defaulting legacy init to GSD, v1 migration, full Pack uninstall command, and parallel write subagents.

## Baseline
- Test command: `python -m pytest`
- Result: initial system Python failed before tests because `pytest` was not installed.
- Known pre-existing failures: none after creating a temporary test venv at `%TEMP%\ecc-init-pytest-venv`, installing pinned `pytest==8.4.1`, installing this repository editable in that venv, and running the pre-change suite: `9 passed`.

## Completed
- [x] Confirmed current repository path is `D:\项目\ecc-init`.
- [x] Confirmed `origin` points to `https://github.com/yuyukosama2004/ecc-init.git`.
- [x] Read `DEVELOPMENT_PLAN_CODEX.md`, confirmed no root `AGENTS.md` existed at start, and read core source, tests, manifest, templates, and bundled skills.
- [x] Created root `AGENTS.md`.
- [x] Created `.codex/config.toml`.
- [x] Created current architecture inventory.
- [x] Added changelog and corrected repository URL metadata.
- [x] Added phase 1 core models, StateStore, manifest validation, receipt helper, and legacy plan builder.
- [x] Added `ecc-init plan`.
- [x] Added tests for rollback, doctor, model round-trip, StateStore, manifest validation, and plan JSON no-write behavior.
- [x] Added `src/ecc_init/resources/registry/registry.json`.
- [x] Added registry loader and Pack resolver.
- [x] Added initial workflows: `none`, `gsd`.
- [x] Added initial profiles: `minimal`, `default`, `frontend`, `rag`.
- [x] Added initial Packs: `project-baseline`, `quality-basic`, `python-fastapi`, `rag-python`, `java-spring`, `frontend-essential`.
- [x] Added `ecc-init packs list` and `ecc-init packs show`.
- [x] Updated `ecc-init plan` to output parsed declarative Packs.
- [x] Added phase 2 tests for stable plan output, stack filtering, profile/exclude behavior, dependency cycles, and conflicts.
- [x] Added `src/ecc_init/core/transaction.py`.
- [x] Added `src/ecc_init/core/ownership.py`.
- [x] Extended `src/ecc_init/core/receipt.py` with `ReceiptStore`.
- [x] Legacy init now records an operation receipt when a backup is created.
- [x] Rollback can resolve backups by operation id or receipt path.
- [x] Status reports locally modified managed files.
- [x] Added phase 3 tests for transaction rollback, concurrent user edit protection, receipt contents, ownership helpers, operation-id rollback, and status dirty reporting.
- [x] Added `src/ecc_init/sources/`.
- [x] Added bundled provider and GitHub archive provider foundations.
- [x] Added SHA256 verification, archive cache, safe zip extraction, and directory projection.
- [x] Added source lock model/store.
- [x] Added local source declaration verification.
- [x] Added `ecc-init sources list` and `ecc-init sources verify`.
- [x] Added phase 4 tests for offline cache, hash mismatch, host allowlist, zip slip, projection traversal, source lock round-trip, and sources CLI.
- [x] Added `src/ecc_init/workflows/`.
- [x] Added `CommandRunner`, `CommandResult`, `PlannedCommand`, and `WorkflowResult`.
- [x] Added `GsdWorkflowAdapter` with pinned `@opengsd/gsd-core@1.6.1`.
- [x] Added Node/npm/npx environment checks and Node 18+ version check.
- [x] Added dry-run install/update/remove surfaces and inspect/verify checks.
- [x] Added `ecc-init workflow status`.
- [x] Updated declarative plan output to include the pinned GSD dry-run external command preview.
- [x] Added phase 5 tests using FakeRunner.
- [x] Added `src/ecc_init/packs/gsd_bridge.py`.
- [x] Added AgentPolicyProfile values for `minimal`, `default`, `frontend`, and `high-assurance`.
- [x] Added default-only deep merge for hard-enforced config keys.
- [x] Added advisory-only policy reporting.
- [x] Added agent_skills merge with dedupe and path safety.
- [x] Added user deletion protection by skipping missing Skill directories.
- [x] Added `ecc-init sync-gsd`.
- [x] Added doctor reporting for GSD config bridge, hard-enforced config, and advisory-only policy.
- [x] Added phase 6 tests for merge semantics, malformed JSON, path traversal, missing skills, Pack cleanup, and CLI dry-run.

## Decisions
- ID: D-2026-07-03-01
- Decision: Do not create a new repository, fork, worktree, or GSD copy.
- Evidence: `Get-Location` returned `D:\项目\ecc-init`; `git remote -v` returned `yuyukosama2004/ecc-init`.
- Consequence: All edits stay in the existing repository.

- ID: D-2026-07-03-02
- Decision: Do not create the broader phase branch in this first batch.
- Evidence: Section 22 Task 0 requires reporting branch/status/log, while the user explicitly constrained the first round to phase 0 and phase 1 minimum work.
- Consequence: Work remains on `main`; no Git branch directive was emitted.

- ID: D-2026-07-03-03
- Decision: Use a temporary pinned pytest venv for verification.
- Evidence: both available Python runtimes reported `No module named pytest`.
- Consequence: Tests can run without adding project dependencies or changing user/global Python packages.

- ID: D-2026-07-03-04
- Decision: Keep `initialize_project` on the legacy path and make `plan` read-only by default.
- Evidence: Phase 1 explicitly requires not changing `initialize_project` default behavior and requires `ecc-init plan --json` to avoid file writes.
- Consequence: GSD and v2 state are preview/model foundations only in this batch.

- ID: D-2026-07-03-05
- Decision: Make the registry-backed `plan` the CLI default while leaving `initialize_project` unchanged.
- Evidence: Phase 2 requires `ecc-init plan` to output parsed Packs while preserving the old init path.
- Consequence: Users can inspect the future Pack selection without changing installed files.

- ID: D-2026-07-03-06
- Decision: Treat GSD as declaration-only in the registry.
- Evidence: Phase 2 asks for `gsd` workflow declaration only, and GSD Adapter is phase 5.
- Consequence: No external command or GSD installation is planned or executed in this batch.

- ID: D-2026-07-03-07
- Decision: Keep the legacy init writer on direct BackupSession orchestration for now, while recording operation receipts after successful backup creation.
- Evidence: Phase 3 needs rollback foundations, but replacing the full init writer would expand risk before Source Provider and Transaction phases are stable.
- Consequence: Future external installs can use `Transaction`; existing init behavior remains compatible.

- ID: D-2026-07-03-08
- Decision: Transaction rollback skips files whose current hash differs from the transaction's expected post-write hash.
- Evidence: Phase 3 requires user concurrent modifications not to be overwritten.
- Consequence: Rollback can be partial and returns skipped paths for reporting.

- ID: D-2026-07-03-09
- Decision: `sources verify` performs local declaration checks only in this phase.
- Evidence: Phase 4 needs source verification, while real external source integration and installation should remain deterministic and testable.
- Consequence: Verification checks host allowlists and fixed refs without downloading remote archives.

- ID: D-2026-07-03-10
- Decision: GitHub archive sources require a fixed 40-character commit SHA.
- Evidence: The development plan forbids storing `main`, `next`, or `latest` as long-term state.
- Consequence: Mutable branch names fail before network access.

- ID: D-2026-07-04-01
- Decision: Pin GSD Core to `@opengsd/gsd-core@1.6.1` for adapter planning.
- Evidence: Upstream GitHub Releases lists `v1.6.1` as a stable install target using `npm i @opengsd/gsd-core@1.6.1`; upstream docs identify `@opengsd/gsd-core` as the package and Node.js 18+ as required.
- Consequence: `ecc-init` never stores or plans `latest` for GSD.

- ID: D-2026-07-04-02
- Decision: Keep GSD install as dry-run/planned unless adapter methods are explicitly called with `dry_run=False`.
- Evidence: The current phase requires fake-runner coverage and must not alter real GSD files during development.
- Consequence: Tests do not execute `npx`, and legacy init remains unchanged.

- ID: D-2026-07-04-03
- Decision: `sync-gsd` only writes when `.planning/config.json` already exists.
- Evidence: GSD creates project config during its own initialization, and phase 6 must not silently initialize GSD.
- Consequence: Uninitialized projects get a non-failing report and no new `.planning` files.

- ID: D-2026-07-04-04
- Decision: Agent skill entries are added only when the target `SKILL.md` exists.
- Evidence: The GSD config docs require project-relative skill entries to point at directories containing `SKILL.md`, and the plan requires user deletion protection.
- Consequence: Deleted or not-yet-installed skills are skipped with warnings instead of recreated or referenced.

## Subagent ledger
| ID | Role | Task | Read/Write | Files owned | Result | Retries |
|---|---|---|---|---|---|---|
| none | none | No subagents used | n/a | n/a | n/a | 0 |

## Verification
| Command | Result | Evidence |
|---|---|---|
| `python -m pytest` | Failed in system env | `No module named pytest` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest` after pinned pytest/editable install, before edits | Passed | `9 passed` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest tests/test_core_models.py tests/test_state_store.py tests/test_cli.py tests/test_app.py` | Passed | `12 passed` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest` | Passed | `18 passed` |
| `python -m compileall src` | Passed | compiled all source files |
| `git diff --check` | Passed | exit code 0; Git emitted CRLF normalization warnings only |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest tests/test_packs.py tests/test_cli.py tests/test_core_models.py` | Passed | `15 passed` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest` | Passed | `26 passed` |
| `python -m compileall src` | Passed | compiled all source files after phase 2 |
| `git diff --check` | Passed | exit code 0 after phase 2; Git emitted CRLF normalization warnings only |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest tests/test_transaction.py tests/test_ownership.py tests/test_app.py tests/test_cli.py` | Passed | `16 passed` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest` | Passed | `33 passed` |
| `python -m compileall src` | Passed | compiled all source files after phase 3 |
| `git diff --check` | Passed | exit code 0 after phase 3; Git emitted CRLF normalization warnings only |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest tests/test_sources.py tests/test_cli.py` | Passed | `15 passed` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest` | Passed | `42 passed` |
| `python -m compileall src` | Passed | compiled all source files after phase 4 |
| `git diff --check` | Passed | exit code 0 after phase 4; Git emitted CRLF normalization warnings only |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest tests/test_workflows.py tests/test_cli.py tests/test_packs.py` | Passed | `21 passed` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest` | Passed | `49 passed` |
| `python -m compileall src` | Passed | compiled all source files after phase 5 |
| `git diff --check` | Passed | exit code 0 after phase 5; Git emitted CRLF normalization warnings only |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest tests/test_gsd_bridge.py tests/test_cli.py tests/test_app.py` | Passed | `25 passed` |
| `%TEMP%\ecc-init-pytest-venv\Scripts\python.exe -m pytest` | Passed | `59 passed` |
| `python -m compileall src` | Passed | compiled all source files after phase 6 |
| `git diff --check` | Passed | exit code 0 after phase 6; Git emitted CRLF normalization warnings only |

## Remaining risks
- The tracked `LICENSE` deletion existed before this batch and remains unresolved.
- `DEVELOPMENT_PLAN_CODEX.md` was present as an untracked root file at start and remains part of the worktree state.
- The new v2 model, registry, transaction, source, workflow, and config bridge layers are intentionally not fully integrated into real installation or migration yet.
- Legacy `rollback_backup` still performs backup-level rollback; partial rollback protection currently lives in `Transaction.rollback` for future transaction-managed operations.
- `sources verify` does not prove remote archive availability; network E2E remains a later integration/release concern.
- `workflow status` can fail on machines without Node.js 18+/npm/npx; this is reported as a local environment check, not a code failure.
- `sync-gsd` does not validate global Skill symlink escapes beyond requiring `SKILL.md` existence; trusted global roots remain a future hardening item.

## Next permitted batch
- Continue with phase 7 only after this phase 6 batch passes full verification and review.
