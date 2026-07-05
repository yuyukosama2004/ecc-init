from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class PlannedCommand:
    args: tuple[str, ...]
    description: str
    dry_run: bool = True


@dataclass(frozen=True)
class EnvironmentCheck:
    check_id: str
    ok: bool
    message: str
    detail: str = ""


class CommandRunner(Protocol):
    def run(self, args: list[str], *, cwd: Path | None = None) -> CommandResult:
        ...


class SubprocessRunner:
    def run(self, args: list[str], *, cwd: Path | None = None) -> CommandResult:
        process = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return CommandResult(tuple(args), process.returncode, process.stdout, process.stderr)


@dataclass
class WorkflowResult:
    workflow_id: str
    status: str
    commands: list[PlannedCommand] = field(default_factory=list)
    checks: list[EnvironmentCheck] = field(default_factory=list)
    logs: list[CommandResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {
            "ok",
            "planned",
            "installed",
            "installed_verified",
            "installed_unverified",
            "updated",
            "updated_verified",
            "updated_unverified",
            "removed",
        } and all(check.ok for check in self.checks)
