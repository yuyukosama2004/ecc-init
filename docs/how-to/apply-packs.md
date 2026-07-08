# Apply Project Packs

Packs are project-level capabilities selected from the `ecc-init` registry. Applying a Pack writes only project-scope files unless a future plan explicitly adds another safe target.

GSD Core remains external and device/runtime-level. Applying Packs does not reinstall GSD unless `--install-gsd` is supplied.

## Prerequisites

### Existing Projects: Migrate Legacy State

If your project was created with an older `ecc-init` version (v1 schema), you must migrate before applying:

```powershell
ecc-init migrate . --dry-run    # preview what will change
ecc-init migrate .              # execute migration
```

Apply will refuse to write if it detects a legacy v1 state file. The migration removes deprecated workflow skills, cleans managed sections, and upgrades the state schema to v2.

### GSD Runtime

Apply can sync existing `.planning/config.json`, but it will not create it. Initialize GSD for your project first if you want config sync.

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

## Global Components

Packs may include global-scope components (skills installed to `~/.claude/skills/` rather than the project directory). In 0.2.0a1, `apply` intentionally skips these with warnings:

```
[warning] skipped non-project component in apply batch: skill-code-review
```

**Workaround:** Copy the bundled skill files manually from the `ecc-init` source repository:

```powershell
# Source: ecc-init repo -> Target: Claude skills directory
xcopy /E /I "D:\项目\ecc-init\src\ecc_init\resources\global_skills\code-review" "%USERPROFILE%\.claude\skills\code-review"
xcopy /E /I "D:\项目\ecc-init\src\ecc_init\resources\global_skills\security-review" "%USERPROFILE%\.claude\skills\security-review"
xcopy /E /I "D:\项目\ecc-init\src\ecc_init\resources\global_skills\code-tour" "%USERPROFILE%\.claude\skills\code-tour"
```

Future versions will support global-scope component writes during apply.

## 0.2.0a1 Scope & Limitations

This alpha supports a specific, bounded apply surface. The following capabilities are **not yet supported** and remain future work:

| Capability | Status |
|---|---|
| GitHub archive directory projection (multi-file) | Not yet - only single-file projection |
| Real ECC/Vercel/Anthropic/UI UX Pro Max source install | Not yet - registry entries are declaration-only |
| `update --sources --yes` remote fetch | Not yet - source update is preview-only |
| `remove --pack X --files --yes` | Not yet - remove edits only GSD config bindings |
| Global-scope component writes during apply | Intentionally skipped - manual copy workaround available |
| Multi-scope apply (project + global in one pass) | Not yet - apply targets project scope only |
| `.planning/config.json` creation | Intentionally not created - GSD owns project init |
| `codex`/`cursor` GSD runtime flags | Experimental - `claude`/`auto` are the stable choices |
| `apply --scope global` flag | Not yet - scope is per-component, not per-invocation |
