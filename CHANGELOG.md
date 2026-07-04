# Changelog

## Unreleased

- Documented `0.1.x` as the legacy initialization line and `0.2.0` as the planned GSD-core architecture line.
- Corrected the project repository metadata to point at `yuyukosama2004/ecc-init`.
- Added the first minimal `ecc-init plan` skeleton for previewing the existing legacy install behavior without writing project files.
- Added a declarative registry and Pack resolver with `none`/`gsd` workflow declarations, initial profiles, stable plan output, and `ecc-init packs list/show`.
- Added a minimal transaction, ownership, and receipt foundation with safe rollback tests and operation-id rollback support.
- Added source provider foundations: bundled and GitHub archive providers, cache/integrity checks, zip-slip-safe extraction, source locks, and `ecc-init sources list/verify`.
- Added a GSD workflow adapter foundation with pinned `@opengsd/gsd-core@1.6.1` command planning, Node/npm checks, dry-run install/update/remove surfaces, and `ecc-init workflow status`.
- Added a GSD config bridge with AgentPolicyProfile defaults, default-only `.planning/config.json` merge, agent skill injection, `sync-gsd`, and doctor hard/advisory reporting.
- Added legacy v1 migration planning and apply support with `ecc-init migrate --dry-run`, migration reports, operation receipts, rollback support, user-modified legacy skill preservation, and init-time migration hints.

## 0.1.0 Alpha

- Initial lightweight Claude Code configuration initializer with stack detection, managed CLAUDE.md sections, bundled skills, backups, rollback, and legacy ECC skill synchronization.
