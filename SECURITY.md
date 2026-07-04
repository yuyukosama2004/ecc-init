# Security Policy

## Supported Version

`ecc-init` 0.2.0 Alpha is the supported development line for GSD-first architecture validation. The 0.1.x legacy initializer remains available only through `ecc-init init --legacy` during migration.

## Reporting

Report security issues privately through the repository maintainer before opening a public issue. Include:

- affected command and version;
- platform and Python version;
- minimal reproduction steps;
- whether the issue involves file overwrite, path traversal, source integrity, external command execution, or rollback.

## Security Boundaries

- GSD Core is external. `ecc-init` must not fork, vendor, or patch it.
- External installers must be pinned and previewable.
- Tests must not run unpinned external installers.
- Source archives must use allowed hosts, fixed commits, and integrity checks when hashes are declared.
- Archive extraction rejects traversal and symlink members.
- Source projection rejects traversal and symlinks.
- Subprocess calls use argument arrays and `shell=False` semantics.
- User-modified files are preserved or backed up before managed writes.
- Operation receipts record changes that support rollback.

## CI Coverage

The CI workflow runs unit/integration tests, compile checks, wheel build, wheel content verification, wheel-install CLI smoke, and pipx install smoke across the supported platform matrix. Nightly network E2E is isolated from ordinary PR checks.
