# Source Policy

This project uses explicit source declarations for all bundled, pinned, generated, and external workflow inputs.

## Rules

- Do not store `main`, `latest`, `next`, or other mutable refs as a durable source version.
- Do not execute unpinned external installers in tests.
- Do not fork, vendor, or directly modify GSD Core.
- Do not redistribute third-party documentation unless the license and redistribution scope are explicit.
- External CLI output must be staged, verified, and transactionally copied before becoming project state.
- Network E2E belongs in nightly or manual CI, not ordinary PR CI.

## Current Sources

### Bundled

The bundled source contains local templates, global skills, project skills, and the registry under `src/ecc_init/resources/`. These files are packaged into the wheel and tested by `scripts/check_wheel_contents.py`.

### GSD Core

- Package: `@opengsd/gsd-core`
- Version: `1.6.1`
- Use: official workflow adapter install/update command preview.
- Boundary: never vendored, forked, or modified.

### ECC Upstream

- Repository: `https://github.com/affaan-m/ECC`
- Pinned commit: `81af40761939056ab3dc54732fd4f562a27309d0`
- Use: source policy and selected stack skill provenance.

### Vercel and Anthropic

Vercel and Anthropic entries are declaration-only source-policy records in this alpha. They may guide future integration decisions, but the package must not include redistributed Anthropic documentation content.

## Verification

- `ecc-init sources verify --json` checks local source declarations.
- `tests/test_sources.py` covers fixed refs, host allowlists, hash mismatch handling, Zip Slip rejection, projection traversal, and source locks.
- `tests/test_security_release.py` covers symlink rejection and package data rules.
- `tests/test_network_e2e.py` checks pinned network sources only when `ECC_INIT_NETWORK_E2E=1`.
