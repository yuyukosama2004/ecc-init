from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MigrationAction:
    action: str
    path: Path
    status: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "path": str(self.path),
            "status": self.status,
            "reason": self.reason,
        }


@dataclass
class MigrationPlan:
    project_root: Path
    detected: bool
    actions: list[MigrationAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "detected": self.detected,
            "actions": [action.to_dict() for action in self.actions],
            "warnings": list(self.warnings),
        }


@dataclass
class MigrationReport(MigrationPlan):
    applied: bool = False
    backup_id: str | None = None
    operation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "applied": self.applied,
                "backup_id": self.backup_id,
                "operation_id": self.operation_id,
            }
        )
        return payload

    def to_markdown(self) -> str:
        lines = [
            "# ecc-init Legacy v1 Migration Report",
            "",
            f"- Project: `{self.project_root}`",
            f"- Applied: `{self.applied}`",
            f"- Backup: `{self.backup_id or 'none'}`",
            f"- Operation: `{self.operation_id or 'none'}`",
            "",
            "## Actions",
            "",
        ]
        if not self.actions:
            lines.append("- No legacy v1 items detected.")
        for action in self.actions:
            detail = f" - {action.reason}" if action.reason else ""
            lines.append(f"- `{action.status}` {action.action}: `{action.path}`{detail}")
        if self.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
        lines.append("")
        return "\n".join(lines)
