# ecc-init Architecture

`ecc-init` 0.2.0 Alpha is a GSD-first CLI with a declarative Pack registry, source policy layer, workflow adapter, migration path, and rollback receipts. It evolves the existing repository; it does not create a replacement repository or vendor GSD Core.

## Layers

- CLI layer: `src/ecc_init/cli.py`
  Provides `init`, `plan`, `apply`, `status`, `update`, `doctor`, `rollback`, `remove`, `migrate`, `sync-gsd`, `packs`, `sources`, and `workflow`.
- Application layer: `src/ecc_init/app.py`
  Orchestrates lifecycle reports, legacy init compatibility, update/remove previews, backups, receipts, status, doctor, and rollback.
- Core model layer: `src/ecc_init/core/`
  Defines plans, receipts, state, ownership, transactions, and validation.
- Pack layer: `src/ecc_init/packs/`
  Loads the declarative registry, resolves profiles and dependencies, filters components by stack, and bridges Pack settings to GSD config.
- Source layer: `src/ecc_init/sources/`
  Implements bundled and pinned GitHub archive providers, source locks, integrity checks, safe archive extraction, and projection helpers.
- Workflow layer: `src/ecc_init/workflows/`
  Provides the GSD adapter with device/runtime-level status, verify, install, and update semantics for pinned `@opengsd/gsd-core@1.6.1`. The adapter generates runtime/scope-specific commands such as `npx -y @opengsd/gsd-core@1.6.1 --claude --global`.
- Apply layer: `src/ecc_init/apply.py`
  Loads InstallPlan JSON, validates schema-derived plan content, checks project-root and path boundaries, reports GSD status, previews GSD config sync, and returns a stable ApplyReport. With `--yes`, it transactionally installs bundled project-scope Pack files and explicitly configured pinned GitHub archive project files, writes `.claude/ecc-sources.lock.json`, updates managed-file state, records an operation receipt, and supports rollback by operation id. Non-project component writes and unsupported sources remain guarded.
- Migration layer: `src/ecc_init/migration/`
  Detects and migrates legacy v1 managed workflow sections and deprecated workflow skills.
- Resource layer: `src/ecc_init/resources/`
  Contains the registry, templates, and bundled skills packaged into the wheel.

## Default Workflow

`ecc-init init .` defaults to the GSD declarative plan. Legacy writes require `--legacy` and are kept only for migration compatibility.

GSD Core installation is a device/runtime-level operation:

```text
ecc-init gsd install --yes
        |
        v
Pinned official GSD installer for the selected runtime/scope
```

Pack application is a project-level operation:

```text
ecc-init plan . --output ecc-plan.json
ecc-init apply ecc-plan.json --yes
        |
        v
Project Pack apply pipeline with bundled/pinned archive file writes, Source Lock, state, receipt
```

`init --yes` uses the project-level apply path and does not run the GSD installer unless `--install-gsd` is explicitly supplied.

```text
init/status/update/remove/doctor
        |
        v
Application services
        |
        +-- Registry and Pack resolver
        +-- GSD workflow adapter
        +-- Source verification and locks
        +-- Backup, receipt, rollback
        +-- Legacy migration
```

## Safety Model

- Dry-run and JSON previews are first-class.
- Writes require explicit `--yes`.
- External installers are pinned and represented as planned commands before execution.
- GSD Core is external and never vendored.
- GSD Core is not installed during every project init; Pack installation is the project-level operation.
- Project apply does not run the GSD installer unless `--install-gsd` is explicitly supplied.
- Pinned GitHub archive apply requires a fixed commit ref and records locks only for sources that actually wrote files.
- Writes that can affect user files are backed up and receipt-recorded.
- User-modified legacy skills are preserved during migration.
- Pack removal edits only managed GSD bindings and preserves shared entries unless `remove --all` is explicitly requested.
- Archive extraction rejects path traversal and symlink members.
- Source projection rejects traversal and symlinks.
- Subprocess execution uses argument lists, not shell strings.

## Release Verification

GitHub Actions runs unit/integration tests, compile checks, wheel builds, wheel content checks, wheel install smoke tests, and pipx install smoke tests across Windows, Linux, and macOS. Nightly CI runs opt-in network E2E checks for pinned npm and GitHub sources.
