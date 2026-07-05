# Audit And Roll Back

`ecc-init` records project apply state so Pack installation can be inspected and reverted without treating GSD Core as project-owned content.

## Audit Status

```powershell
ecc-init status . --json
ecc-init doctor . --json
```

`status --json` reports:

- planned workflow and Packs;
- GSD runtime status;
- installed and planned Packs;
- planned and locked sources;
- Source Lock status;
- latest project operation receipt;
- managed-file dirtiness;
- apply readiness.

`doctor --json` reuses the same read-only audit facts and reports PASS/WARN/FAIL checks. It does not create missing runtime directories or initialize `.planning/config.json`.

## Source Lock

Successful project apply writes:

```text
.claude/ecc-sources.lock.json
```

The lock records sources that actually wrote files. Dry-runs do not create or update it.

## Operation Receipt

Successful apply writes an operation receipt under `ECC_INIT_HOME`, including the operation id, selected Packs, locked sources, changed files, config changes, backup id, and result.

Use the operation id for rollback:

```powershell
ecc-init rollback . --operation-id <operation-id> --json
```

Rollback restores project files and Source Lock state recorded by the transaction. If a file was edited after apply, rollback avoids overwriting that concurrent user edit and reports the partial outcome.

## What Rollback Does Not Own

Project rollback does not uninstall GSD Core. GSD Core is a device/runtime-level workflow dependency installed separately through `ecc-init gsd install --yes`.

Rollback also does not delete user-authored files that were preserved during apply, and `remove` currently edits only managed GSD config bindings rather than deleting Pack files.

## Future: File-Level Remove

`remove` currently only cleans managed GSD config bindings. File-level removal is planned for a future release. It will require four preconditions before deleting any managed file:

1. The file was installed by `ecc-init` and is recorded in managed state;
2. The file hash has not been changed by the user;
3. No other installed Pack shares ownership of the file;
4. A backup and receipt exist so the removal can be rolled back.

Until file-level remove is available, user-modified Skill files are preserved, and GSD config bindings are the only safe removal target.
