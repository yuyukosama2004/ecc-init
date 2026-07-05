from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..paths import AppPaths
from .base import CommandResult, CommandRunner, EnvironmentCheck, PlannedCommand, SubprocessRunner, WorkflowResult


GSD_PACKAGE = "@opengsd/gsd-core"
GSD_PINNED_VERSION = "1.6.1"
MIN_NODE_VERSION = (18, 0, 0)
RUNTIME_FLAGS = {
    "auto": "--claude",
    "claude": "--claude",
    "codex": "--codex",
    "cursor": "--cursor",
}
SCOPE_FLAGS = {
    "global": "--global",
    "project": "--local",
    "local": "--local",
}


@dataclass(frozen=True)
class GsdInstallOptions:
    runtime: str = "claude"
    scope: str = "global"
    version: str = GSD_PINNED_VERSION
    yes: bool = False
    dry_run: bool = True


def _tool(name: str) -> str:
    if os.name == "nt" and name in {"npx", "npm", "node"}:
        return f"{name}.cmd"
    return name


def _parse_version(output: str) -> tuple[int, int, int] | None:
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", output)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


class GsdWorkflowAdapter:
    workflow_id = "gsd"

    def __init__(self, runner: CommandRunner | None = None):
        self.runner = runner or SubprocessRunner()

    def _runtime_flag(self, runtime: str) -> str:
        try:
            return RUNTIME_FLAGS[runtime]
        except KeyError as exc:
            raise ValueError(f"unsupported GSD runtime: {runtime}") from exc

    def _scope_flag(self, scope: str) -> str:
        try:
            return SCOPE_FLAGS[scope]
        except KeyError as exc:
            raise ValueError(f"unsupported GSD install scope: {scope}") from exc

    def install_command(self, options: GsdInstallOptions | None = None) -> PlannedCommand:
        options = options or GsdInstallOptions()
        return PlannedCommand(
            args=(
                _tool("npx"),
                "-y",
                f"{GSD_PACKAGE}@{options.version}",
                self._runtime_flag(options.runtime),
                self._scope_flag(options.scope),
            ),
            description=f"Run the pinned official GSD Core installer for {options.runtime}/{options.scope}.",
            dry_run=options.dry_run,
        )

    def update_command(self, options: GsdInstallOptions | None = None) -> PlannedCommand:
        options = options or GsdInstallOptions()
        return PlannedCommand(
            args=self.install_command(options).args,
            description=f"Re-run the pinned official GSD Core installer for {options.runtime}/{options.scope}.",
            dry_run=options.dry_run,
        )

    def environment_checks(self, *, run_version: bool = True) -> list[EnvironmentCheck]:
        checks: list[EnvironmentCheck] = []
        node_path = shutil.which(_tool("node")) or shutil.which("node")
        npx_path = shutil.which(_tool("npx")) or shutil.which("npx")
        npm_path = shutil.which(_tool("npm")) or shutil.which("npm")
        checks.append(EnvironmentCheck("node-present", node_path is not None, "Node.js executable", node_path or "not found"))
        checks.append(EnvironmentCheck("npx-present", npx_path is not None, "npx executable", npx_path or "not found"))
        checks.append(EnvironmentCheck("npm-present", npm_path is not None, "npm executable", npm_path or "not found"))
        if node_path and run_version:
            result = self.runner.run([node_path, "--version"])
            version = _parse_version(result.stdout or result.stderr)
            ok = result.ok and version is not None and version >= MIN_NODE_VERSION
            checks.append(
                EnvironmentCheck(
                    "node-version",
                    ok,
                    "Node.js 18+ required",
                    (result.stdout or result.stderr).strip() or f"exit {result.returncode}",
                )
            )
        elif node_path:
            checks.append(
                EnvironmentCheck(
                    "node-version",
                    True,
                    "Node.js 18+ required",
                    "not checked during dry-run",
                )
            )
        return checks

    def _target_root(self, paths: AppPaths, options: GsdInstallOptions) -> Path:
        runtime = "claude" if options.runtime == "auto" else options.runtime
        if runtime == "claude" and options.scope == "global":
            return paths.claude_home
        if runtime == "claude":
            return paths.project_root / ".claude"
        return paths.project_root if options.scope in {"project", "local"} else paths.ecc_home

    def _scope_checks(self, paths: AppPaths, options: GsdInstallOptions) -> list[EnvironmentCheck]:
        target = self._target_root(paths, options)
        probe = target if target.exists() else target.parent
        writable = probe.exists() and os.access(probe, os.W_OK)
        return [
            EnvironmentCheck(
                "install-scope-writable",
                writable,
                f"GSD {options.runtime}/{options.scope} install target",
                str(target),
            )
        ]

    def _has_verified_markers(self, paths: AppPaths, options: GsdInstallOptions) -> bool:
        root = self._target_root(paths, options)
        if not root.exists():
            return False
        marker_patterns = (
            "commands/gsd*",
            "commands/gsd/*",
            "agents/gsd*",
            "skills/gsd-*",
            "hooks/gsd*",
        )
        return any(any(root.glob(pattern)) for pattern in marker_patterns)

    def status(self, paths: AppPaths, *, runtime: str = "claude", scope: str = "global") -> WorkflowResult:
        options = GsdInstallOptions(runtime=runtime, scope=scope)
        checks = [*self.environment_checks(run_version=True), *self._scope_checks(paths, options)]
        command = self.install_command(options)
        warnings: list[str] = []
        if not all(check.ok for check in checks):
            return WorkflowResult(self.workflow_id, "blocked_environment", [command], checks, warnings=warnings)
        if self._has_verified_markers(paths, options):
            return WorkflowResult(self.workflow_id, "installed_verified", [command], checks, warnings=warnings)
        warnings.append("GSD Core was not detected for this runtime/scope; run `ecc-init gsd install --yes` if needed.")
        return WorkflowResult(self.workflow_id, "not_installed", [command], checks, warnings=warnings)

    def install(self, paths: AppPaths, options: GsdInstallOptions | None = None, *, dry_run: bool | None = None) -> WorkflowResult:
        options = options or GsdInstallOptions(dry_run=True if dry_run is None else dry_run)
        if dry_run is not None:
            options = GsdInstallOptions(
                runtime=options.runtime,
                scope=options.scope,
                version=options.version,
                yes=options.yes,
                dry_run=dry_run,
            )
        checks = [*self.environment_checks(run_version=not options.dry_run), *self._scope_checks(paths, options)]
        command = self.install_command(options)
        affected = str(self._target_root(paths, options))
        warnings = [f"GSD {options.runtime}/{options.scope} install affects runtime configuration at: {affected}"]
        if options.dry_run:
            return WorkflowResult(self.workflow_id, "planned", [command], checks, warnings=warnings)
        if not all(check.ok for check in checks):
            return WorkflowResult(self.workflow_id, "blocked_environment", [command], checks, warnings=warnings)
        result = self.runner.run(list(command.args), cwd=paths.project_root)
        if result.ok:
            status = "installed_verified" if self._has_verified_markers(paths, options) else "installed_unverified"
            if status == "installed_unverified":
                warnings.append("Installer succeeded, but ecc-init could not verify GSD runtime artifacts.")
        else:
            status = "failed"
        return WorkflowResult(self.workflow_id, status, [command], checks, [result], warnings)

    def inspect(self, paths: AppPaths) -> WorkflowResult:
        planning_config = paths.project_root / ".planning" / "config.json"
        checks = [
            EnvironmentCheck(
                "planning-config",
                planning_config.exists(),
                "GSD planning config",
                str(planning_config),
            )
        ]
        return WorkflowResult(self.workflow_id, "ok" if planning_config.exists() else "missing", checks=checks)

    def verify(self, paths: AppPaths, *, runtime: str = "claude", scope: str = "global") -> WorkflowResult:
        return self.status(paths, runtime=runtime, scope=scope)

    def update(self, paths: AppPaths, options: GsdInstallOptions | None = None, *, dry_run: bool | None = None) -> WorkflowResult:
        options = options or GsdInstallOptions(dry_run=True if dry_run is None else dry_run)
        if dry_run is not None:
            options = GsdInstallOptions(
                runtime=options.runtime,
                scope=options.scope,
                version=options.version,
                yes=options.yes,
                dry_run=dry_run,
            )
        checks = [*self.environment_checks(run_version=not options.dry_run), *self._scope_checks(paths, options)]
        command = self.update_command(options)
        if options.dry_run:
            return WorkflowResult(self.workflow_id, "planned", [command], checks=checks)
        if not all(check.ok for check in checks):
            return WorkflowResult(self.workflow_id, "blocked_environment", [command], checks=checks)
        result = self.runner.run(list(command.args), cwd=paths.project_root)
        if result.ok:
            status = "updated_verified" if self._has_verified_markers(paths, options) else "updated_unverified"
        else:
            status = "failed"
        return WorkflowResult(self.workflow_id, status, [command], checks=checks, logs=[result])

    def remove(self, paths: AppPaths, *, dry_run: bool = True) -> WorkflowResult:
        warnings = [
            "GSD removal is strategy-only in this phase; use migration/remove phases for managed cleanup.",
            f"Inspect before removing files under: {paths.claude_home}",
        ]
        return WorkflowResult(self.workflow_id, "planned" if dry_run else "blocked", warnings=warnings)

    def command_log(self, result: WorkflowResult) -> list[CommandResult]:
        return result.logs
