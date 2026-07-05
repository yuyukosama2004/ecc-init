# Apply Project Packs

Packs are project-level capabilities selected from the `ecc-init` registry. Applying a Pack writes only project-scope files unless a future plan explicitly adds another safe target.

GSD Core remains external and device/runtime-level. Applying Packs does not reinstall GSD unless `--install-gsd` is supplied.

## Create A Plan

```powershell
ecc-init plan . --output ecc-plan.json
```

The plan records detected stacks, selected workflow, selected Packs, file operations, source declarations, and GSD runtime status.

## Preview Apply

Apply is dry-run by default:

```powershell
ecc-init apply ecc-plan.json --json
ecc-init apply ecc-plan.json --dry-run --json
```

The JSON output is a stable `ApplyReport` containing project-root validation, planned files, GSD status, planned source locks, config sync preview, warnings, and errors.

## Write Project Files

Use `--yes` to write:

```powershell
ecc-init apply ecc-plan.json --yes --json
```

The current apply path supports:

- bundled project-scope Pack files;
- explicit pinned GitHub archive single-file components;
- `.claude/ecc-sources.lock.json`;
- `.claude/ecc-init-state.json` state v2 managed-file records;
- operation receipts under the configured `ECC_INIT_HOME`;
- transactional rollback by operation id;
- GSD config sync only when `.planning/config.json` already exists.

Apply preserves existing unowned files and user-modified managed files. Missing `.planning/config.json` is reported as a warning; it is not created by `ecc-init`.

## GSD Config Sync

By default, apply syncs existing GSD config after project files are installed, so newly written Skill directories can be added to `agent_skills`.

```powershell
ecc-init apply ecc-plan.json --yes --json
ecc-init apply ecc-plan.json --yes --no-sync-gsd --json
```

Use `--no-sync-gsd` when you want Pack files written but GSD config left untouched.

## Offline Source Behavior

Bundled sources work offline. Optional unsupported sources are skipped with warnings when they are not required. Required unsupported sources fail closed. Fixed GitHub archive components require a pinned archive, an offline cache entry, or network access when allowed.
