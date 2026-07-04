from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from ..paths import AppPaths
from .base import CommandResult, CommandRunner, EnvironmentCheck, PlannedCommand, SubprocessRunner, WorkflowResult


GSD_PACKAGE = "@opengsd/gsd-core"
GSD_PINNED_VERSION = "1.6.1"
MIN_NODE_VERSION = (18, 0, 0)


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

    def install_command(self) -> PlannedCommand:
        return PlannedCommand(
            args=(_tool("npx"), "-y", f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}"),
            description="Run the pinned official GSD Core installer.",
        )

    def update_command(self) -> PlannedCommand:
        return PlannedCommand(
            args=(_tool("npm"), "install", "-g", f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}"),
            description="Update GSD Core to the pinned version.",
        )

    def environment_checks(self) -> list[EnvironmentCheck]:
        checks: list[EnvironmentCheck] = []
        node_path = shutil.which(_tool("node")) or shutil.which("node")
        npx_path = shutil.which(_tool("npx")) or shutil.which("npx")
        npm_path = shutil.which(_tool("npm")) or shutil.which("npm")
        checks.append(EnvironmentCheck("node-present", node_path is not None, "Node.js executable", node_path or "not found"))
        checks.append(EnvironmentCheck("npx-present", npx_path is not None, "npx executable", npx_path or "not found"))
        checks.append(EnvironmentCheck("npm-present", npm_path is not None, "npm executable", npm_path or "not found"))
        if node_path:
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
        return checks

    def install(self, paths: AppPaths, *, dry_run: bool = True) -> WorkflowResult:
        checks = self.environment_checks()
        command = self.install_command()
        affected = str(paths.claude_home)
        warnings = [f"Claude Home affected scope should be backed up before install: {affected}"]
        if dry_run:
            return WorkflowResult(self.workflow_id, "planned", [command], checks, warnings=warnings)
        if not all(check.ok for check in checks):
            return WorkflowResult(self.workflow_id, "blocked", [command], checks, warnings=warnings)
        result = self.runner.run(list(command.args), cwd=paths.project_root)
        status = "installed" if result.ok else "failed"
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

    def verify(self, paths: AppPaths) -> WorkflowResult:
        result = self.inspect(paths)
        checks = [*self.environment_checks(), *result.checks]
        status = "ok" if all(check.ok for check in checks) else "blocked"
        return WorkflowResult(self.workflow_id, status, checks=checks)

    def update(self, paths: AppPaths, *, dry_run: bool = True) -> WorkflowResult:
        command = self.update_command()
        if dry_run:
            return WorkflowResult(self.workflow_id, "planned", [command])
        result = self.runner.run(list(command.args), cwd=paths.project_root)
        return WorkflowResult(self.workflow_id, "ok" if result.ok else "failed", [command], logs=[result])

    def remove(self, paths: AppPaths, *, dry_run: bool = True) -> WorkflowResult:
        warnings = [
            "GSD removal is strategy-only in this phase; use migration/remove phases for managed cleanup.",
            f"Inspect before removing files under: {paths.claude_home}",
        ]
        return WorkflowResult(self.workflow_id, "planned" if dry_run else "blocked", warnings=warnings)

    def command_log(self, result: WorkflowResult) -> list[CommandResult]:
        return result.logs
