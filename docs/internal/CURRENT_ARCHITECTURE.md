# Current Architecture

Snapshot date: 2026-07-03

This inventory is based on the existing `yuyukosama2004/ecc-init` repository. It does not treat the development plan as already implemented.

## Current File Tree

```text
.
├── AGENTS.md                         # phase 0 repository instructions
├── CHANGELOG.md                      # phase 0 metadata
├── DEVELOPMENT_PLAN_CODEX.md         # development plan supplied to Codex
├── README.md
├── pyproject.toml
├── .codex/
│   └── config.toml                   # Codex development-side agent limits
├── docs/
│   └── internal/
│       ├── CURRENT_ARCHITECTURE.md
│       └── IMPLEMENTATION_STATUS.md
├── src/
│   └── ecc_init/
│       ├── __init__.py
│       ├── app.py                    # legacy init/status/doctor/rollback orchestration
│       ├── backup.py                 # backup sessions and rollback restore
│       ├── cli.py                    # argparse CLI
│       ├── detect.py                 # stack detection
│       ├── errors.py                 # phase 1 user-facing error types
│       ├── frontend.py               # frontend Pack tool detection and lifecycle metadata
│       ├── merge.py                  # managed section and whole-file three-way merge
│       ├── migration/                # legacy v1 to v2 migration
│       ├── paths.py                  # project/global path resolution
│       ├── project.py                # rendered project docs and fingerprint
│       ├── packs/
│       │   ├── __init__.py
│       │   ├── gsd_bridge.py         # GSD config merge and agent_skills bridge
│       │   ├── registry.py           # declarative registry loader and validation
│       │   └── resolver.py           # Pack ordering and InstallPlan projection
│       ├── resources.py              # bundled resource reads and manifest validation
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── locks.py              # source lock model/store
│       │   ├── providers.py          # bundled and GitHub archive providers
│       │   └── verify.py             # registry source checks
│       ├── sync.py                   # legacy ECC release/raw sync
│       ├── workflows/
│       │   ├── __init__.py
│       │   ├── base.py               # command runner/result abstractions
│       │   ├── gsd.py                # GSD adapter foundation
│       │   ├── none.py
│       │   └── registry.py
│       ├── util.py                   # atomic writes, JSON helpers, hashes
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py             # phase 1 dataclass models
│       │   ├── ownership.py          # managed-file owner/status helpers
│       │   ├── plan.py               # phase 1 legacy InstallPlan preview
│       │   ├── receipt.py            # operation receipt helper/store
│       │   ├── state_store.py        # phase 1 atomic JSON state store
│       │   ├── transaction.py        # BackupSession-backed transaction skeleton
│       │   └── validation.py         # manifest validation
│       └── resources/
│           ├── manifest.json
│           ├── registry/
│           │   └── registry.json
│           ├── templates/
│           ├── global_skills/
│           └── project_skills/
└── tests/
    ├── test_app.py
    ├── test_cli.py
    ├── test_core_models.py
    ├── test_detect.py
    ├── test_frontend.py
    ├── test_merge.py
    ├── test_migration.py
    ├── test_packs.py
    ├── test_sources.py
    ├── test_workflows.py
    ├── test_gsd_bridge.py
    ├── test_ownership.py
    ├── test_transaction.py
    └── test_state_store.py
```

Note: the worktree already had tracked `LICENSE` deleted before this implementation batch. This batch did not restore or modify it.

## Current CLI

- `ecc-init` defaults to `init`.
- `ecc-init <path>` is normalized to `ecc-init init <path>`.
- `init` and `update` call the same legacy `initialize_project` path and accept `--offline` and `--no-sync`.
- `plan` now emits a v2-shaped preview from the declarative Pack Registry. It reads project files and bundled resources but does not create project files unless `--output` is explicitly provided.
- `packs list` and `packs show <pack>` inspect the declarative registry.
- `sources list` and `sources verify` inspect and validate source declarations. Verification is local/declaration-level in this phase and does not download archives.
- `workflow status` runs local GSD adapter environment checks and does not install GSD.
- `sync-gsd` performs a default-only merge into `.planning/config.json` when it already exists. It skips missing/deleted Skill directories and never overwrites explicit user values.
- `migrate` previews or applies legacy v1-to-v2 migration. `--dry-run` writes nothing; apply writes a migration report, operation receipt, and rollback-capable backup.
- `status` reports detected stacks, installed global/project skills, code-tour state, upstream ref, conflicts, and backup count.
- `status` also reports locally modified managed files by comparing current hashes with recorded base hashes.
- `doctor` checks Python, Git, directory writability, bundled manifest presence, GSD bridge status, and frontend tool detection status.
- `rollback` restores the latest or specified backup, or resolves a backup from `--operation-id` / `--receipt`.

## Current State

- Global state path: `~/.ecc-init/state.json`.
- Project state path: `<project>/.claude/ecc-init-state.json`.
- Existing runtime state is still version `1`.
- Managed files are tracked by absolute target path with `source_id`, `kind`, immutable base path, and base hash.
- Phase 1 adds schema v2 dataclasses and `StateStore`; phase 7 adds an explicit `migrate` path that writes schema v2 state.
- Phase 2 adds a declarative registry for workflows, profiles, components, and Packs. It is used by `plan` only; runtime initialization is still legacy.
- Phase 3 adds operation receipts under `~/.ecc-init/operations/<operation-id>/receipt.json` when legacy init creates a backup.
- Phase 4 adds source provider foundations, source locks, archive cache safety, integrity checks, and directory projection helpers. These are not yet wired into legacy init.
- Phase 5 adds a GSD Workflow Adapter foundation with a pinned package version, command runner abstraction, Node/npm checks, and dry-run command planning. It is not enabled as the default installer path.
- Phase 6 adds a GSD config bridge for hard-enforced config defaults, advisory-only policy reporting, and agent_skills injection. It is only used by `sync-gsd` and doctor/status style reporting.
- Phase 7 adds legacy v1 detection and migration. Clean v1 installs can be migrated to schema v2, deprecated workflow skills and managed workflow sections are removed, user-modified legacy skills are preserved, and rollback can restore the v1 state.
- Phase 8 expands `frontend-essential` into a React-focused Pack with UI UX Pro Max, Vercel, Playwright-quality, frontend lifecycle documentation, optional source-policy declarations, GSD UI agent mappings, and frontend doctor checks.

## Current Install Flow

1. Resolve `AppPaths` from the project path, `ECC_INIT_HOME`, and `CLAUDE_HOME`.
2. Load the bundled legacy manifest.
3. Create a backup session.
4. Detect project stacks from dependency files and source files.
5. Merge the global `CLAUDE.md` managed section.
6. Install the six legacy global skills from bundled resources.
7. Merge the project `CLAUDE.md` managed section.
8. Resolve the latest legacy ECC release ref unless `--offline` or `--no-sync` is used.
9. Install matching project skills from upstream/cache/bundled fallback.
10. Create `docs/DEVELOPMENT_LOG.md`, `docs/PROJECT_OVERVIEW.md`, and `docs/dev-notes/`.
11. Update v1 project/global state.
12. Finish the backup manifest if files changed.

## Current Tests

- Detection tests cover Python/FastAPI/LangChain/LangGraph/TypeScript/React and Spring Boot.
- Merge tests cover managed section preservation, whole-file update, non-overlapping merge, and conflict artifacts.
- App tests cover offline init, CLAUDE.md preservation, status, rollback, and doctor.
- CLI tests cover argument normalization and `plan --json` not writing project files.
- Core tests cover model JSON round-trips, legacy plan contents, manifest validation errors, and StateStore behavior.
- Pack tests cover registry contents, stable plan output, stack filtering, profile/exclude behavior, dependency cycles, and conflicts.
- Transaction tests cover rollback of created/modified/deleted files, concurrent user edit protection, receipt contents, and ownership status helpers.
- Source tests cover fixed-commit GitHub archive resolution with offline cache, hash mismatch, host allowlist, zip slip rejection, projection safety, source lock round-trip, and `sources` CLI.
- Workflow tests cover fake runner execution, dry-run command planning, Node missing/too-old checks, inspect/remove strategy, and CLI status output.
- GSD bridge tests cover default-only merge, explicit value preservation, agent_skills dedupe, missing Skill protection, malformed JSON safety, Pack cleanup, path traversal rejection, and CLI dry-run.
- Migration tests cover dry-run no-write behavior, clean v1 migration, user-modified legacy skill preservation, repeatability, operation-id rollback, init migration hints, and CLI JSON output.
- Frontend tests cover React Pack selection, non-frontend exclusion, GSD UI config defaults, UI agent injection, doctor frontend tool detection, optional source-policy declarations, and skill content boundaries.

## Differences From The Development Plan

- GSD Core is not installed, vendored, forked, or modified.
- The runtime default remains the legacy 0.1 initializer; GSD is not yet the workflow authority.
- Pack Registry, local resolver, Transaction skeleton, ownership helpers, operation receipts, Source Provider foundations, Source Lock store, GSD Adapter foundation, GSD config bridge, and legacy v1 migration now exist.
- Full source integration, full transaction integration into legacy init, real GSD installation, stack Pack installation, and release CI remain later phases.
- Legacy global workflow skills (`task-planning`, `verification-loop`, `dev-retrospective`) are still installed by the legacy init path until migration is applied.
- Legacy network sync still targets selected `affaan-m/ECC` release/raw files.
- `StateStore` and v2 models exist as foundations; phase 7 migration writes v2 migration state, but `initialize_project` still writes legacy v1 state.
- `ecc-init plan` previews declarative Pack operations and deliberately performs no external network resolution.
- `Transaction` is available for future external component installs, but the legacy init path still uses the original direct `BackupSession` orchestration.
- `GitHubArchiveProvider` requires a fixed 40-character commit SHA and an allowed host. Tests use local fake archives; no real source archive is downloaded during verification.
- `GsdWorkflowAdapter` plans pinned commands for `@opengsd/gsd-core@1.6.1`. Tests use FakeRunner and never invoke real `npx`.
- `sync-gsd` writes only when `.planning/config.json` already exists and `--dry-run` is not set. GSD-uninitialized projects receive a non-failing report.
- `frontend-essential` is selected for React projects by the declarative plan. It does not install external Vercel, Anthropic, Playwright, or browser tools; those sources and tools are declaration/detection surfaces in this phase.
