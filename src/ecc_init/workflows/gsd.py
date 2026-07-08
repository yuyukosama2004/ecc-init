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
MIN_NODE_VERSION = (22, 0, 0)
MIN_NPM_VERSION = (10, 0, 0)
RUNTIME_FLAGS = {
    "auto": "--claude",
    "claude": "--claude",
}
_EXPERIMENTAL_RUNTIME_FLAGS = {
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
                _tool("npm"),
                "install",
                "-g",
                f"{GSD_PACKAGE}@{options.version}",
            ),
            description=f"Install pinned GSD Core globally via npm, then run its {options.runtime}/{options.scope} setup commands manually.",
            dry_run=options.dry_run,
        )

    def update_command(self, options: GsdInstallOptions | None = None) -> PlannedCommand:
        options = options or GsdInstallOptions()
        return PlannedCommand(
            args=self.install_command(options).args,
            description=f"Re-run npm install -g for pinned GSD Core; then re-run {options.runtime} setup if needed.",
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
        node_version_msg = f"Node.js {MIN_NODE_VERSION[0]}+ required"
        npm_version_msg = f"npm {MIN_NPM_VERSION[0]}+ required"
        if node_path and run_version:
            result = self.runner.run([node_path, "--version"])
            version = _parse_version(result.stdout or result.stderr)
            ok = result.ok and version is not None and version >= MIN_NODE_VERSION
            checks.append(
                EnvironmentCheck(
                    "node-version",
                    ok,
                    node_version_msg,
                    (result.stdout or result.stderr).strip() or f"exit {result.returncode}",
                )
            )
        elif node_path:
            checks.append(
                EnvironmentCheck(
                    "node-version",
                    True,
                    node_version_msg,
                    "not checked during dry-run",
                )
            )
        else:
            checks.append(
                EnvironmentCheck(
                    "node-version",
                    False,
                    node_version_msg,
                    "Node.js not found",
                )
            )
        if npm_path and run_version:
            result = self.runner.run([npm_path, "--version"])
            version = _parse_version(result.stdout or result.stderr)
            ok = result.ok and version is not None and version >= MIN_NPM_VERSION
            checks.append(
                EnvironmentCheck(
                    "npm-version",
                    ok,
                    npm_version_msg,
                    (result.stdout or result.stderr).strip() or f"exit {result.returncode}",
                )
            )
        elif npm_path:
            checks.append(
                EnvironmentCheck(
                    "npm-version",
                    True,
                    npm_version_msg,
                    "not checked during dry-run",
                )
            )
        else:
            checks.append(
                EnvironmentCheck(
                    "npm-version",
                    False,
                    npm_version_msg,
                    "npm not found",
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

    # Known GSD command files that indicate a real GSD Core runtime install.
    _GSD_COMMAND_MARKERS: tuple[str, ...] = (
        "commands/gsd-new-project.md",
        "commands/gsd-discuss-phase.md",
        "commands/gsd-plan-phase.md",
        "commands/gsd-execute-phase.md",
        "commands/gsd-verify-work.md",
        "commands/gsd-ship.md",
    )

    def _has_verified_markers(self, paths: AppPaths, options: GsdInstallOptions) -> bool:
        root = self._target_root(paths, options)
        if not root.exists():
            return False
        # Check for specific known GSD command artifacts.
        # A wildcard glob is intentionally NOT used here to prevent
        # unrelated user files (e.g. commands/gsd-demo.md) from triggering a false verified.
        commands_dir = root / "commands"
        if commands_dir.is_dir():
            for marker in self._GSD_COMMAND_MARKERS:
                if (root / marker).is_file():
                    return True
        # agents/* or skills/gsd-* directories are weaker signals
        # but still indicate a GSD install when commands are present too.
        if any((root / "agents").glob("gsd*")):
            return True
        return False

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
        install_runner = self.runner if not isinstance(self.runner, SubprocessRunner) else SubprocessRunner(capture_output=False)
        result = install_runner.run(list(command.args), cwd=paths.project_root)
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
        update_runner = self.runner if not isinstance(self.runner, SubprocessRunner) else SubprocessRunner(capture_output=False)
        result = update_runner.run(list(command.args), cwd=paths.project_root)
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
