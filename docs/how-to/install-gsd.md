# Install GSD Core

GSD Core is a device/runtime-level workflow kernel. Install it once for the runtime you use, then apply `ecc-init` Packs per project.

`ecc-init` does not copy, vendor, or modify GSD Core files. It plans and runs the pinned official installer command for the selected runtime and scope.

## Prerequisites

GSD Core `@opengsd/gsd-core@1.6.1` requires:

- **Node.js** >= 22.0.0
- **npm** >= 10.0.0
- **npx** present (bundled with npm)

`ecc-init gsd status` checks these before install or update. If any check fails, the status is `blocked_environment` and the installer will not execute. Dry-run previews do not run version checks against the actual toolchain.

## Check Status

```powershell
ecc-init gsd status --json
ecc-init gsd verify --json
```

The status output distinguishes local environment failures from install state:

- `blocked_environment`: Node.js, npm, npx, or writable target checks failed.
- `not_installed`: the runtime can be checked, but GSD is not known to be installed.
- `installed_unverified`: the install command can be planned or ran, but local files cannot prove the runtime is fully verified.
- `installed_verified`: the runtime-level checks can verify the install.

## Preview Install

All write-capable commands are dry-run by default. Preview the device/runtime install first:

```powershell
ecc-init gsd install --dry-run --json
```

For Claude global installs, the planned command is pinned and argument-list based:

```powershell
npx -y @opengsd/gsd-core@1.6.1 --claude --global
```

Project/local scope uses the same pinned package with local scope:

```powershell
npx -y @opengsd/gsd-core@1.6.1 --claude --local
```

## Install Or Update

Run the installer only when you intentionally want to modify the selected runtime:

```powershell
ecc-init gsd install --yes --json
ecc-init gsd update --yes --json
```

`ecc-init init .` and `ecc-init apply plan.json --yes` do not install GSD Core by default. Use `--install-gsd` only when you want to include the device/runtime install step explicitly:

```powershell
ecc-init init . --yes --install-gsd
ecc-init apply ecc-plan.json --yes --install-gsd
```

Keep GSD Core installation separate from project Pack application. A machine/runtime normally needs the GSD install once; each project can then select and apply its own Packs.
