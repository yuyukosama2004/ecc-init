# Migration Guide: 0.1.x to 0.2.0 Alpha

`ecc-init` 0.2.0 Alpha changes the default CLI path from the legacy ECC-style initializer to the GSD-first declarative workflow.

## What Changed

- `ecc-init init .` now previews the GSD install plan by default.
- Legacy writes are still available with `ecc-init init . --legacy`.
- Existing legacy v1 project files can be migrated with `ecc-init migrate`.
- `ecc-init update`, `remove`, `status`, `doctor`, and `rollback` support JSON output for automation.
- GSD Core remains external. `ecc-init` does not fork, vendor, or modify it.

## Preview Existing Projects

```powershell
ecc-init migrate . --dry-run --json
ecc-init status . --json
ecc-init update . --check --json
```

These commands do not write project files.

## Apply Legacy v1 Migration

```powershell
ecc-init migrate .
```

The migration removes clean legacy managed workflow sections, preserves user-modified legacy skills, writes `docs/ecc-init-migration-report.md`, and records an operation receipt.

Rollback is operation-id based:

```powershell
ecc-init rollback . --operation-id <operation-id>
```

## GSD Config Updates

If a project already has `.planning/config.json`, preview Pack/GSD config changes with:

```powershell
ecc-init update . --packs --dry-run --json
```

Apply safe local config changes non-interactively:

```powershell
ecc-init update . --packs --yes --json
```

## Remove Pack Bindings

Pack removal is conservative in 0.2.0 Alpha:

```powershell
ecc-init remove . --pack frontend-essential --json
ecc-init remove . --pack frontend-essential --yes --json
```

It removes only ecc-init managed GSD agent-skill bindings. It does not delete user-modified Skill files and does not uninstall GSD Core.

## Legacy Opt-In

During the alpha window, the old initializer is available explicitly:

```powershell
ecc-init init . --legacy --offline
```

Use this only for projects that intentionally remain on the 0.1.x behavior while migration is being reviewed.
