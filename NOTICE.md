# ecc-init Notices

This repository is the `ecc-init` toolkit for configuring Claude Code projects with a GSD-first workflow.

The project metadata declares the package license as MIT. The repository intentionally does not include a root `LICENSE` file because the maintainer removed it and asked not to restore it. This notice records attribution and redistribution boundaries for bundled and declared sources.

## Bundled Content

- `src/ecc_init/resources/global_skills/`
- `src/ecc_init/resources/project_skills/`
- `src/ecc_init/resources/templates/`
- `src/ecc_init/resources/registry/registry.json`

Bundled resources are packaged with the wheel and are covered by this repository's package metadata unless their frontmatter or registry source declaration says otherwise.

## Declared External Sources

- GSD Core: official npm package `@opengsd/gsd-core@1.6.1`, planned and installed through the workflow adapter only.
- ECC upstream source policy: `https://github.com/affaan-m/ECC` pinned to commit `81af40761939056ab3dc54732fd4f562a27309d0`.
- Vercel and Anthropic frontend guidance: declaration-only source policy entries. The wheel must not redistribute Anthropic documentation content.

## Redistribution Boundary

The package may contain source declarations and local guidance derived from repository policy, but it must not vendor, fork, or modify GSD Core. Network source fetching and external CLI execution must be explicit, pinned, previewable, and auditable.
