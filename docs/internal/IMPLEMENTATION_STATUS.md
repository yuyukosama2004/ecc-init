# Implementation Status

## Current phase
- Phase: Post-alpha batch 5, read-only apply audit status
- Batch: 2026-07-05 status/doctor apply audit integration
- Branch: main
- Started: 2026-07-04 Asia/Shanghai

## Scope
- In scope: baseline command evidence; `ecc-init gsd status/install/update/verify`; pinned runtime/scope GSD installer command semantics; `init --yes` separation from workflow update; `ApplyReport` dry-run/preflight skeleton; apply project-root/path/registry validation; bundled project-scope component writes behind `--yes`; explicit pinned GitHub archive project component projection; transactional apply GSD config sync for existing `.planning/config.json`; `.claude/ecc-sources.lock.json`; apply operation receipts including config changes; apply rollback by operation id; read-only `status --json` and `doctor --json` audit reporting for GSD runtime, source lock, receipt, installed/planned Packs, plan/apply consistency, managed-file dirtiness, and apply readiness; tests for GSD dry-run, command shape, environment blocking, init/apply boundary, apply JSON stability, bundled apply writes, fixed GitHub archive apply from offline cache, optional archive skip behavior, existing GSD config sync, `--no-sync-gsd`, user-file preservation, rollback, and read-only audit behavior.
- Out of scope: copying, vendoring, forking, or modifying GSD Core; real external_cli/Anthropic/Vercel/UI UX Pro Max installs; adding new Packs; global component writes; switching default Packs away from bundled fallbacks; GitHub archive directory projection; creating `.planning/config.json` when GSD has not initialized the project; deleting user files; executing unpinned installers in tests.

## Baseline
- Test command: `python -m pytest`
- Result: bare command failed in this working tree because `ecc_init` is not installed and `PYTHONPATH` was not set; collection reported `ModuleNotFoundError: No module named 'ecc_init'`.
- Known pre-existing failures: with the repository test environment (`$env:PYTHONPATH='src'`), the pre-change suite passed with `113 passed, 4 skipped`.
- Git baseline: `git status --short` showed only untracked `CODEX_NEXT_PLAN_GSD_APPLY.md`; branch was `main`; `git log -5 --oneline` was `6fff8ca`, `c855757`, `1499add`, `4e32b6c`, `d86c935`.

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
- [x] Added `src/ecc_init/migration/` with legacy v1 detection, migration plan/report models, and apply orchestration.
- [x] Added clean managed-section removal for legacy global/project workflow markers.
- [x] Added deprecated workflow skill removal for clean v1-managed `task-planning`, `verification-loop`, and `dev-retrospective`.
- [x] Added preservation and warning behavior for user-modified legacy workflow skills.
- [x] Added schema v2 migration state with `gsd` workflow authority and `ecc-init/legacy-v1` Pack migration record.
- [x] Added migration report writing to `docs/ecc-init-migration-report.md`.
- [x] Added operation receipt creation for migration and rollback via `--operation-id`.
- [x] Added `ecc-init migrate --dry-run` / `ecc-init migrate --json`.
- [x] Added init-time hint telling legacy v1 users to preview migration.
- [x] Added phase 7 tests for dry-run, clean migration, user modification protection, repeatability, rollback, CLI JSON, and init warning behavior.
- [x] Added `src/ecc_init/frontend.py` for frontend project/tool detection and lifecycle command metadata.
- [x] Expanded `frontend-essential` to include UI UX Pro Max, Vercel, Playwright-quality, and frontend lifecycle document components.
- [x] Added bundled frontend project skills for UI UX Pro Max, Vercel platform guidance, and Playwright-quality verification.
- [x] Added `docs/FRONTEND_LIFECYCLE.md` template with the required frontend GSD lifecycle command display.
- [x] Added optional source-policy declarations for Vercel and Anthropic frontend guidance without downloading or installing external content.
- [x] Updated `frontend-essential` React stack selection so React projects receive the Pack without requiring TypeScript evidence.
- [x] Added GSD UI agent mappings for `gsd-ui-designer`, `gsd-ui-reviewer`, executor, reviewer, and verifier roles.
- [x] Added Pack `gsd_config_defaults` merging through `sync-gsd` while preserving user explicit values.
- [x] Added doctor frontend checks for frontend project, Playwright, Vercel, and GSD Browser detection.
- [x] Added phase 8 tests for React selection, non-frontend exclusion, config defaults, UI agent injection, doctor detection, source policy declarations, and skill workflow-boundary checks.
- [x] Added fixed `ecc-upstream-pinned` source declaration for `affaan-m/ECC` at commit `81af40761939056ab3dc54732fd4f562a27309d0`.
- [x] Added component-level `stack_conditions` to Pack components and resolver filtering.
- [x] Changed Pack stack selection to include a Pack when any declared stack condition is detected, while component filtering keeps installs precise.
- [x] Added stack-aware GSD agent skill injection so non-detected components are not injected or warned about.
- [x] Added `researcher` role mapping to `gsd-phase-researcher`.
- [x] Expanded Python/FastAPI, RAG Python, and Java/Spring GSD agent mappings for planner/executor/reviewer/verifier/researcher roles as appropriate.
- [x] Added `source_id` and `content_version` metadata to all project Skill frontmatter.
- [x] Added tests ensuring project Skills do not duplicate GSD lifecycle commands.
- [x] Added tests for independent Python/FastAPI, LangChain/LangGraph, and Java/Spring component filtering.
- [x] Added tests for bundled offline stack Skill resources and fixed ECC source verification.
- [x] Reworked `ecc-init update` from a legacy init alias into a lifecycle update command with `--check`, `--dry-run`, `--yes`, scoped source/workflow/Pack previews, JSON output, conflict reporting, and exit-code mapping.
- [x] Added `ecc-init remove` with dry-run-by-default behavior, `--yes` guarded writes, `--pack`, `--workflow`, `--all`, JSON output, backups, operation receipts, and user-file-preserving GSD config cleanup.
- [x] Added validate-only `ecc-init apply` help and JSON output for plan validation without file writes.
- [x] Added JSON output for `init`, `status`, `doctor`, and `rollback`.
- [x] Added global `--debug` traceback behavior while keeping stack traces hidden by default.
- [x] Added CI-friendly doctor/update exit code behavior for FAIL/manual-action states.
- [x] Added safer Pack agent skill removal so shared Pack bindings are preserved by default and only all-pack removal clears shared registry-managed entries.
- [x] Added PowerShell lifecycle examples for update/remove/doctor and documented that remove does not delete Skill files or uninstall GSD Core in this phase.
- [x] Added phase 10 tests for lifecycle JSON, dry-run no-write behavior, `--yes` writes with receipts, help coverage, debug errors, and shared-binding preservation.
- [x] Bumped package and runtime version to `0.2.0a0`.
- [x] Changed `ecc-init init` default behavior to GSD declarative plan preview and moved legacy writes behind explicit `--legacy`.
- [x] Updated bundled source registry version to `0.2.0a0`.
- [x] Added `.github/workflows/ci.yml` with Windows/Linux/macOS and Python 3.10/3.12 matrix, pytest, compileall, wheel build, wheel content check, wheel CLI smoke, and pipx smoke.
- [x] Added `.github/workflows/nightly-network-e2e.yml` for opt-in pinned npm/GitHub source checks.
- [x] Added `scripts/check_wheel_contents.py`, `scripts/cli_smoke.py`, and `scripts/release_dry_run.py`.
- [x] Added `.gitignore` for local generated artifacts including `.claude/`, `.planning/`, cache, build, and dist directories.
- [x] Added archive absolute-path and symlink-member rejection plus source projection symlink rejection.
- [x] Added phase 11 tests for subprocess argument-list execution, symlink rollback safety, package data integrity, release docs/CI file presence, and version metadata consistency.
- [x] Added `ARCHITECTURE.md`, `MIGRATION.md`, `NOTICE.md`, `SECURITY.md`, and `SOURCE_POLICY.md`.
- [x] Added `docs/e2e/0.2.0-alpha.md` mapping acceptance scenarios to automated tests and manual smoke evidence.
- [x] Updated README for 0.2.0a0 alpha behavior, GSD default init, legacy opt-in, update/remove/rollback demos, and source boundaries.
- [x] Added `ecc-init gsd status/install/update/verify` command group.
- [x] Added `GsdInstallOptions` and runtime/scope-aware GSD install command planning.
- [x] Changed GSD install/update to use the pinned official installer shape, including `--claude --global` for Claude global.
- [x] Added GSD statuses for `not_installed`, `installed_verified`, `installed_unverified`, and `blocked_environment`.
- [x] Kept GSD install/update dry-run by default unless `--yes` is supplied.
- [x] Changed declarative plan external operation preview to include GSD runtime/scope flags.
- [x] Changed `init --yes` to enter the project-level apply path instead of using lifecycle workflow update as a pseudo-install.
- [x] Added `--install-gsd` to `init` and `apply` as the explicit gate for device/runtime-level GSD install.
- [x] Added `src/ecc_init/apply.py` with `ApplyOptions`, `ApplyReport`, plan loading, project-root validation, registry validation, operation-id checks, path-boundary checks, GSD status reporting, and GSD config sync preview.
- [x] Changed `ecc-init apply` from validate-only output to structured ApplyReport dry-run/preflight output.
- [x] Added tests for GSD CLI JSON, GSD installer command shape, local/project scope, update installer semantics, Windows command suffix, init/apply boundary, project-root mismatch, and apply dry-run no-write behavior.
- [x] Updated README and ARCHITECTURE to distinguish one-time GSD runtime install from per-project Pack apply.
- [x] Added `src/ecc_init/packs/installer.py` for transaction-backed bundled project-scope component installation.
- [x] Changed project Source Lock output to `.claude/ecc-sources.lock.json`.
- [x] Changed `apply --yes` from preflight-only to bundled Pack file writes with `Transaction`, state v2 managed-file records, Source Lock, operation receipt, and rollback support.
- [x] Added apply preservation behavior for existing unowned files and user-modified managed files.
- [x] Kept non-project component writes skipped with warnings and unsupported required non-bundled sources blocked.
- [x] Changed GSD install/update dry-runs so they do not execute Node version subprocess checks.
- [x] Updated tests for bundled apply write path, source lock/state/receipt output, rollback by operation id, unowned file preservation, and `init --yes` project apply behavior.
- [x] Added fixed GitHub archive project component projection through the apply installer for explicit single-file components.
- [x] Reused the existing pinned GitHub archive provider, cache, offline mode, source path, integrity, safe extraction, and symlink/traversal protections.
- [x] Changed apply Source Lock generation to lock only sources that actually wrote files.
- [x] Added optional GitHub archive skip behavior so missing optional archives warn without blocking unrelated bundled writes.
- [x] Kept default registry/Packs on bundled fallback resources; no new Packs or real third-party installers were added.
- [x] Added tests for offline cached fixed GitHub archive apply and optional missing archive skip/no-lock behavior.
- [x] Wired apply GSD config sync into the apply transaction for existing `.planning/config.json`.
- [x] Changed apply config sync to run after component writes so newly installed project Skills can be added to GSD `agent_skills`.
- [x] Added apply receipt `config_changes` entries for transactional `sync-gsd` writes.
- [x] Kept missing GSD config as warning-only; apply does not create `.planning/config.json`.
- [x] Added `--no-sync-gsd` coverage to keep existing GSD config untouched when explicitly requested.
- [x] Added rollback coverage proving apply restores a pre-existing GSD config after operation-id rollback.
- [x] Extended `status --json` with read-only GSD runtime status, installed/planned Packs, planned/locked sources, Source Lock status, latest project receipt, plan/apply consistency, receipt consistency, and apply readiness.
- [x] Extended human `status` with concise workflow, Pack, Source Lock, receipt, and readiness summaries.
- [x] Extended `doctor --json` with GSD runtime, installed Packs, project Source Lock, latest apply receipt, apply readiness, and plan/apply consistency checks.
- [x] Changed doctor path checks to probe writability through existing parents without creating missing runtime directories.
- [x] Added status/doctor tests covering apply audit JSON after apply and no-write doctor directory probing.

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

- ID: D-2026-07-04-05
- Decision: Legacy migration preserves user-modified deprecated workflow skills instead of deleting or rewriting them.
- Evidence: Phase 7 requires modified v1 not to be overwritten or deleted.
- Consequence: Clean v1 installs become GSD-only after migration; modified legacy artifacts remain for manual review and are reported in the migration report.

- ID: D-2026-07-04-06
- Decision: `initialize_project` emits a migration hint but does not automatically apply migration.
- Evidence: Phase 7 requires an init migration prompt, while the project still needs explicit dry-run support before writes.
- Consequence: Existing init behavior stays compatible, and users can preview with `ecc-init migrate --dry-run` before changing workflow files.

- ID: D-2026-07-04-07
- Decision: Treat Vercel and Anthropic frontend inputs as optional source-policy declarations in phase 8.
- Evidence: The plan requires Vercel Skills and optional Anthropic Source policy, while current source integration must remain deterministic and avoid unpinned external installs.
- Consequence: The registry records these sources and `sources verify` reports them as declaration-only; no external content is downloaded or installed.

- ID: D-2026-07-04-08
- Decision: Keep frontend lifecycle commands in a project document instead of embedding them into frontend Skill content.
- Evidence: Phase 8 requires lifecycle command display and also requires Skills not to duplicate the main workflow rules.
- Consequence: `FRONTEND_LIFECYCLE.md` lists the GSD commands, while the frontend skills remain domain-specific.

- ID: D-2026-07-04-09
- Decision: `sync-gsd` merges Pack config defaults with default-only semantics.
- Evidence: Phase 8 requires GSD UI config defaults and user config protection.
- Consequence: `frontend-essential` can add UI defaults and lifecycle commands without turning user-disabled `ui_review` or `review_enabled` back on.

- ID: D-2026-07-04-10
- Decision: Pin ECC upstream as a source declaration while continuing to use bundled stack Skill fallbacks in ordinary tests and previews.
- Evidence: Phase 9 requires fixed ECC source and offline fallback, but source installation wiring is a later phase.
- Consequence: `sources verify` can prove the ECC ref is immutable, and `plan` remains deterministic offline.

- ID: D-2026-07-04-11
- Decision: Use component-level stack filtering instead of splitting every stack into separate user-facing Pack names.
- Evidence: Phase 9 requires Java without Spring and LangChain without LangGraph to avoid unrelated Skill installation while preserving the planned Pack names.
- Consequence: `python-fastapi`, `rag-python`, and `java-spring` remain stable Pack IDs, but only matching components and GSD bindings are emitted.

- ID: D-2026-07-04-12
- Decision: Treat Skill frontmatter `content_version` as the stack Skill content version for phase 9.
- Evidence: The phase requires Skill content versioning and frontmatter tests.
- Consequence: Bundled Skill updates can be detected and tested without introducing a separate manifest schema yet.

- ID: D-2026-07-04-13
- Decision: Make lifecycle update/remove commands preview-first and require `--yes` before safe local writes.
- Evidence: Phase 10 requires dry-run, update preview, safe remove, and non-interactive `--yes`.
- Consequence: `ecc-init update` and `ecc-init remove` are machine-parseable and safe by default; `--yes` applies only bounded local config changes unless an explicitly scoped workflow update is requested.

- ID: D-2026-07-04-14
- Decision: Keep `apply` validate-only in phase 10.
- Evidence: Full plan application spans source projection, transactions, and release hardening beyond this phase; the phase only requires CLI completion and preview surfaces.
- Consequence: `ecc-init apply --dry-run --json` validates plan JSON, while non-dry-run apply returns a clear nonzero result instead of partially applying an install plan.

- ID: D-2026-07-04-15
- Decision: `remove` cleans GSD config bindings but never deletes Skill files or uninstalls GSD Core in phase 10.
- Evidence: Scenario H requires preserving user-modified files and only removing owned Agent bindings.
- Consequence: Pack removal records backups/receipts for `.planning/config.json`; user files and GSD Core remain untouched.

- ID: D-2026-07-04-16
- Decision: Preserve agent skill entries shared by other Packs unless the user requests `remove --all`.
- Evidence: Scenario H requires retaining shared items from other Packs.
- Consequence: Single-Pack removal is conservative and avoids breaking other Pack bindings.

- ID: D-2026-07-04-17
- Decision: Promote the package to `0.2.0a0` and make `ecc-init init` GSD-first by default.
- Evidence: The Definition of Done requires GSD to be the default and only main workflow, while phase 5 allowed legacy mode only as a temporary explicit flag.
- Consequence: Default init produces the GSD declarative plan and does not install legacy workflow skills; the old writer remains available as `ecc-init init --legacy` for migration compatibility.

- ID: D-2026-07-04-18
- Decision: Do not restore the root `LICENSE` file.
- Evidence: The maintainer explicitly deleted `LICENSE` and stated they did not want to keep it.
- Consequence: License/source attribution is recorded through package metadata and `NOTICE.md`; CI/package checks do not require a root `LICENSE` file.

- ID: D-2026-07-04-19
- Decision: Keep network E2E isolated to scheduled/manual CI and an opt-in environment variable.
- Evidence: Phase 11 requires nightly network E2E, and repository safety rules require ordinary tests to remain deterministic and avoid unpinned installers.
- Consequence: PR CI runs local tests and package smoke, explicitly ignores `tests/test_network_e2e.py`, and sets `ECC_INIT_NETWORK_E2E=0`; that network suite runs only when `ECC_INIT_NETWORK_E2E=1` in the nightly/manual workflow.

- ID: D-2026-07-04-20
- Decision: Reject source archive symlinks and source projection symlinks.
- Evidence: Phase 11 requires symlink tests, and symlink-following could copy or expose files outside the intended source tree.
- Consequence: `safe_extract_zip` and `project_directory` fail closed on symlink inputs.

- ID: D-2026-07-04-21
- Decision: Treat `ecc-init gsd *` as the device/runtime-level GSD Core command surface.
- Evidence: `CODEX_NEXT_PLAN_GSD_APPLY.md` separates `ecc-init gsd install --yes` from project-level `plan/apply`, and the official GSD install guide documents runtime/scope flags such as `--claude --global` and `--claude --local`.
- Consequence: GSD install/update commands now include pinned package, runtime, and scope; project `init` no longer silently performs device-level GSD install.

- ID: D-2026-07-04-22
- Decision: Use the official pinned GSD installer command for both install and update surfaces in this batch.
- Evidence: The next plan calls out the old `npm install -g @opengsd/gsd-core@1.6.1` update surface as misleading for runtime installation semantics.
- Consequence: `GsdWorkflowAdapter.update()` now plans/runs `npx -y @opengsd/gsd-core@1.6.1 --<runtime> --<scope>` instead of `npm install -g`.

- ID: D-2026-07-04-23
- Decision: Introduce `ApplyReport` and block write phases until component installation, Source Lock, Receipt, and rollback are implemented transactionally.
- Evidence: The first batch requires apply dry-run/report skeleton and also forbids a temporary script that bypasses transaction/receipt/source-lock design.
- Consequence: First-batch `apply --dry-run --json` became stable and no-write; the bundled project-scope write path was intentionally deferred until D-2026-07-04-25.

- ID: D-2026-07-04-24
- Decision: Route `init --yes` through project-level apply, not lifecycle update.
- Evidence: The next plan explicitly forbids continuing to treat workflow update as GSD install.
- Consequence: `init --yes` no longer calls `update_project(update_workflow=True)`; `--install-gsd` is the only explicit path that can call the GSD installer from init.

- ID: D-2026-07-04-25
- Decision: Unblock only bundled project-scope component writes in the first transaction-backed apply batch.
- Evidence: The current target requires not leaving apply validate-only, while still forbidding real external_cli/Anthropic/Vercel installs and broader source integration.
- Consequence: `apply --yes` writes bundled project files with state, Source Lock, receipt, and rollback; global components are skipped with warnings and unsupported required non-bundled sources fail closed.

- ID: D-2026-07-04-26
- Decision: Store project source locks at `.claude/ecc-sources.lock.json`.
- Evidence: The GSD apply plan separates project Pack source state from GSD Core runtime installation state.
- Consequence: Source locks live alongside ecc-init project state and can be included in transaction receipts and rollback.

- ID: D-2026-07-04-27
- Decision: Support fixed GitHub archive apply only for explicit project-scope single-file components in this batch.
- Evidence: The next plan requires completing bundled and fixed GitHub archive apply closure while forbidding real external_cli/Anthropic/Vercel installs and new Pack expansion.
- Consequence: The installer can project pinned archive content through the existing source provider/cache path, while default Packs remain deterministic bundled fallbacks.

- ID: D-2026-07-04-28
- Decision: Lock only sources that actually wrote files during apply.
- Evidence: Optional archive components can be skipped when offline cache is absent, and preserved user files can prevent writes.
- Consequence: `.claude/ecc-sources.lock.json`, state, and receipts do not falsely record skipped or preserved sources as installed.

- ID: D-2026-07-05-01
- Decision: Run apply GSD config sync after component files are installed.
- Evidence: `pack_agent_skill_additions` only injects `agent_skills` for directories that already contain `SKILL.md`.
- Consequence: `apply --yes` can install project Skills and then transactionally merge them into existing `.planning/config.json` in the same operation.

- ID: D-2026-07-05-02
- Decision: Keep `.planning/config.json` creation outside apply.
- Evidence: GSD initializes project config through its own workflow, and the next plan requires ecc-init not to create GSD projects silently.
- Consequence: Missing GSD config remains a warning/report state; `apply --yes` writes config only when the file already exists and `--no-sync-gsd` was not supplied.

- ID: D-2026-07-05-03
- Decision: Treat missing Source Lock and missing project receipt as read-only audit warnings before the first successful apply.
- Evidence: New projects have not written `.claude/ecc-sources.lock.json` or an operation receipt yet, while the next plan requires status/doctor to report readiness without writing files.
- Consequence: `status --json` and `doctor --json` can explain first-apply state without creating directories or blocking a clean project-level apply preview.

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
| `python -m pip install pytest` | Passed | installed pytest in the current Python 3.10 environment because no local venv was present |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_migration.py tests\test_cli.py tests\test_app.py` | Passed | `24 passed` |
| `$env:PYTHONPATH='src'; python -m compileall -q src` | Passed | compiled all source files after phase 7 implementation |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `66 passed` |
| `git diff --check` | Passed | exit code 0 after phase 7; Git emitted CRLF normalization warnings only |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_frontend.py tests\test_gsd_bridge.py tests\test_packs.py tests\test_app.py tests\test_sources.py` | Passed | `32 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `72 passed` |
| `$env:PYTHONPATH='src'; python -m compileall -q src` | Passed | compiled all source files after phase 8 implementation |
| `git diff --check` | Passed | exit code 0 after phase 8; Git emitted CRLF normalization warnings only |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_stack_packs.py tests\test_packs.py tests\test_gsd_bridge.py tests\test_core_models.py tests\test_sources.py tests\test_detect.py` | Passed | `34 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `80 passed` |
| `$env:PYTHONPATH='src'; python -m compileall -q src` | Passed | compiled all source files after phase 9 implementation |
| `git diff --check` | Passed | exit code 0 after phase 9; Git emitted CRLF normalization warnings only |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_lifecycle_cli.py tests\test_cli.py tests\test_gsd_bridge.py tests\test_app.py` | Passed | `47 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `102 passed` |
| `$env:PYTHONPATH='src'; python -m compileall -q src` | Passed | compiled all source files after phase 10 implementation |
| `git diff --check` | Passed | exit code 0 after phase 10; Git emitted CRLF normalization warnings only |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_security_release.py tests\test_network_e2e.py tests\test_lifecycle_cli.py tests\test_sources.py` | Passed | `36 passed, 4 skipped` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `113 passed, 4 skipped` |
| `$env:PYTHONPATH='src'; $env:ECC_INIT_NETWORK_E2E='1'; python -m pytest tests\test_network_e2e.py` | Passed | `2 passed` |
| `$env:PYTHONPATH='src'; python -m compileall -q src scripts` | Passed | compiled source and release scripts after phase 11 implementation |
| `$env:PYTHONPATH='src'; python scripts\release_dry_run.py` | Passed | created a pinned temporary build venv, built `ecc_init-0.2.0a0-py3-none-any.whl`, checked wheel contents and entry point, and ran wheel CLI smoke |
| `%TEMP%\ecc-init-release-venv-codex\Scripts\python.exe -m pipx install . --force` with temporary `PIPX_HOME`/`PIPX_BIN_DIR` | Passed | installed `ecc-init 0.2.0a0` and `ecc-init --version` returned `ecc-init 0.2.0a0` |
| GitHub Actions CI on pushed `main` and `v0.2.0-alpha.0` | Passed | Windows/Linux/macOS Python 3.10/3.12 matrix and pipx smoke completed successfully |
| `git status --short` | Passed | baseline showed only `?? CODEX_NEXT_PLAN_GSD_APPLY.md` |
| `git branch --show-current` | Passed | `main` |
| `git log -5 --oneline` | Passed | `6fff8ca`, `c855757`, `1499add`, `4e32b6c`, `d86c935` |
| `python -m pytest` | Failed in bare environment | collection failed with `ModuleNotFoundError: No module named 'ecc_init'` because the package was not installed and `PYTHONPATH` was unset |
| `$env:PYTHONPATH='src'; python -m pytest` before edits | Passed | `113 passed, 4 skipped` |
| `python -m compileall -q src scripts` before edits | Passed | compiled source and scripts |
| `git diff --check` before edits | Passed | exit code 0 |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_workflows.py tests\test_gsd_install_cli.py tests\test_apply.py tests\test_cli.py tests\test_lifecycle_cli.py` | Passed | `52 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `124 passed, 4 skipped` |
| `$env:PYTHONPATH='src'; python -m compileall -q src scripts` | Passed | compiled source and scripts after GSD/apply changes |
| `git diff --check` | Passed | exit code 0; Git emitted CRLF normalization warnings only |
| `python -m pytest` after edits | Failed in bare environment | collection failed with `ModuleNotFoundError: No module named 'ecc_init'`; use editable install or `PYTHONPATH=src` for this src-layout repo |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_workflows.py tests\test_gsd_install_cli.py tests\test_apply.py tests\test_transaction.py tests\test_sources.py tests\test_cli.py tests\test_lifecycle_cli.py` | Passed | `65 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `127 passed, 4 skipped` |
| `$env:PYTHONPATH='src'; python -m compileall -q src scripts` | Passed | compiled source and scripts after bundled apply changes |
| `git diff --check` | Passed | exit code 0; Git emitted CRLF normalization warnings only |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_apply.py tests\test_sources.py` | Passed | `15 passed` |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_workflows.py tests\test_gsd_install_cli.py tests\test_apply.py tests\test_transaction.py tests\test_sources.py tests\test_cli.py tests\test_lifecycle_cli.py` | Passed | `67 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `129 passed, 4 skipped` |
| `$env:PYTHONPATH='src'; python -m compileall -q src scripts` | Passed | compiled source and scripts after fixed GitHub archive apply changes |
| `git diff --check` | Passed | exit code 0; Git emitted CRLF normalization warnings only |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_apply.py tests\test_gsd_bridge.py` | Passed | `19 passed` |
| `$env:PYTHONPATH='src'; python -m pytest tests\test_apply.py tests\test_gsd_bridge.py tests\test_transaction.py tests\test_cli.py tests\test_lifecycle_cli.py` | Passed | `60 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `131 passed, 4 skipped` |
| `python -m compileall -q src scripts` | Passed | compiled source and scripts after apply GSD config sync changes |
| `git diff --check` | Passed | exit code 0; Git emitted CRLF normalization warnings only |
| `$env:PYTHONPATH='src'; python -m pytest tests/test_lifecycle_cli.py tests/test_app.py tests/test_apply.py` | Passed | `42 passed` |
| `$env:PYTHONPATH='src'; python -m pytest tests/test_gsd_install_cli.py tests/test_workflows.py tests/test_sources.py tests/test_ownership.py` | Passed | `20 passed` |
| `$env:PYTHONPATH='src'; python -m pytest` | Passed | `134 passed, 4 skipped` |
| `python -m compileall -q src scripts` | Passed | compiled source and scripts after status/doctor audit changes |
| `git diff --check` | Passed | exit code 0; Git emitted CRLF normalization warnings only |

## Remaining risks
- The tracked `LICENSE` deletion was user-intended and committed before phase 7; `NOTICE.md` and package metadata now carry the release attribution record.
- Legacy `rollback_backup` still performs backup-level rollback; bundled apply writes now use `Transaction.rollback` for partial rollback protection.
- `sources verify` does not prove remote archive availability during ordinary local checks; opt-in/nightly network E2E covers pinned npm and GitHub source availability.
- `workflow status` can fail on machines without Node.js 18+/npm/npx; this is reported as a local environment check, not a code failure.
- `sync-gsd` does not validate global Skill symlink escapes beyond requiring `SKILL.md` existence; trusted global roots remain a future hardening item.
- If legacy workflow skills were modified by the user, migration preserves them and leaves manual cleanup for the report-guided review path.
- Frontend Vercel, Anthropic, Playwright, and GSD Browser integrations are declaration/detection surfaces only; real third-party installs remain future integration work.
- Fixed GitHub archive single-file project projection is supported for explicit components; default Pack registry entries still use bundled fallbacks, and archive directory projection remains future work.
- `ecc-init apply --yes` installs bundled and explicit pinned GitHub archive project-scope files transactionally; global components and real external installers remain guarded or unsupported.
- `init --yes` now routes to project-level apply and can install bundled project files; it still does not install GSD Core unless `--install-gsd` is explicit.
- `apply --install-gsd --yes` can invoke the pinned GSD installer explicitly, but the device/runtime-level GSD install remains outside project file rollback.
- Apply now transactionally syncs existing `.planning/config.json`, but does not initialize missing GSD config; users still need GSD project initialization before config sync can write.
- `ecc-init update --sources` verifies declarations and reports preview status only; it does not fetch new remote source content in 0.2.0a0.
- `ecc-init remove` removes only managed GSD config bindings; it intentionally does not delete Skill files or uninstall GSD Core.

## Next permitted batch
- Add bundled E2E fixtures for empty, FastAPI+LangGraph, React+Vite, and existing-GSD-config project flows before expanding source behavior.
- Add release-gating assertions around the bundled E2E fixtures before enabling any broader external source behavior.
