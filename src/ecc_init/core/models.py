from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(str(item) for item in value)


def _dict(value: Any) -> dict[str, Any]:
    return value.copy() if isinstance(value, dict) else {}


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    kind: str
    repository: str | None = None
    package: str | None = None
    version: str = ""
    commit: str | None = None
    path: str | None = None
    license_id: str | None = None
    license_path: str | None = None
    integrity: str | None = None
    executable_surface: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "repository": self.repository,
            "package": self.package,
            "version": self.version,
            "commit": self.commit,
            "path": self.path,
            "license_id": self.license_id,
            "license_path": self.license_path,
            "integrity": self.integrity,
            "executable_surface": list(self.executable_surface),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceSpec":
        return cls(
            source_id=str(data["source_id"]),
            kind=str(data["kind"]),
            repository=data.get("repository"),
            package=data.get("package"),
            version=str(data.get("version") or ""),
            commit=data.get("commit"),
            path=data.get("path"),
            license_id=data.get("license_id"),
            license_path=data.get("license_path"),
            integrity=data.get("integrity"),
            executable_surface=_tuple(data.get("executable_surface")),
        )


@dataclass(frozen=True)
class ComponentSpec:
    component_id: str
    source_id: str
    install_name: str
    target_scope: str
    target_subdir: str
    projection_include: tuple[str, ...] = ()
    projection_exclude: tuple[str, ...] = ()
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "source_id": self.source_id,
            "install_name": self.install_name,
            "target_scope": self.target_scope,
            "target_subdir": self.target_subdir,
            "projection_include": list(self.projection_include),
            "projection_exclude": list(self.projection_exclude),
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComponentSpec":
        return cls(
            component_id=str(data["component_id"]),
            source_id=str(data["source_id"]),
            install_name=str(data["install_name"]),
            target_scope=str(data["target_scope"]),
            target_subdir=str(data["target_subdir"]),
            projection_include=_tuple(data.get("projection_include")),
            projection_exclude=_tuple(data.get("projection_exclude")),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True)
class PackSpec:
    pack_id: str
    version: int
    description: str
    components: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    stack_conditions: tuple[str, ...] = ()
    gsd_agent_skills: dict[str, tuple[str, ...]] = field(default_factory=dict)
    gsd_config_defaults: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "version": self.version,
            "description": self.description,
            "components": list(self.components),
            "requires": list(self.requires),
            "conflicts": list(self.conflicts),
            "stack_conditions": list(self.stack_conditions),
            "gsd_agent_skills": {key: list(value) for key, value in self.gsd_agent_skills.items()},
            "gsd_config_defaults": self.gsd_config_defaults,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackSpec":
        skills = data.get("gsd_agent_skills", {})
        return cls(
            pack_id=str(data["pack_id"]),
            version=int(data["version"]),
            description=str(data.get("description") or ""),
            components=_tuple(data.get("components")),
            requires=_tuple(data.get("requires")),
            conflicts=_tuple(data.get("conflicts")),
            stack_conditions=_tuple(data.get("stack_conditions")),
            gsd_agent_skills={str(key): _tuple(value) for key, value in _dict(skills).items()},
            gsd_config_defaults=_dict(data.get("gsd_config_defaults")),
        )


@dataclass(frozen=True)
class WorkflowSpec:
    workflow_id: str
    adapter: str
    source_id: str | None = None
    scope_default: str = "global"
    conflicts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "adapter": self.adapter,
            "source_id": self.source_id,
            "scope_default": self.scope_default,
            "conflicts": list(self.conflicts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowSpec":
        return cls(
            workflow_id=str(data["workflow_id"]),
            adapter=str(data["adapter"]),
            source_id=data.get("source_id"),
            scope_default=str(data.get("scope_default") or "global"),
            conflicts=_tuple(data.get("conflicts")),
        )


@dataclass(frozen=True)
class Operation:
    operation_id: str
    kind: str
    summary: str
    target: str | None = None
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "kind": self.kind,
            "summary": self.summary,
            "target": self.target,
            "required": self.required,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Operation":
        return cls(
            operation_id=str(data["operation_id"]),
            kind=str(data["kind"]),
            summary=str(data.get("summary") or ""),
            target=data.get("target"),
            required=bool(data.get("required", True)),
            metadata=_dict(data.get("metadata")),
        )


@dataclass(frozen=True)
class ResolvedComponent:
    component_id: str
    install_name: str
    source_id: str
    target_scope: str
    target_path: Path
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "install_name": self.install_name,
            "source_id": self.source_id,
            "target_scope": self.target_scope,
            "target_path": str(self.target_path),
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResolvedComponent":
        return cls(
            component_id=str(data["component_id"]),
            install_name=str(data["install_name"]),
            source_id=str(data["source_id"]),
            target_scope=str(data["target_scope"]),
            target_path=Path(str(data["target_path"])),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True)
class StateMigration:
    from_schema: int
    to_schema: int
    description: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_schema": self.from_schema,
            "to_schema": self.to_schema,
            "description": self.description,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StateMigration":
        return cls(
            from_schema=int(data["from_schema"]),
            to_schema=int(data["to_schema"]),
            description=str(data.get("description") or ""),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True)
class FileOperation:
    operation_id: str
    action: str
    path: Path
    source_id: str
    target_scope: str
    managed: bool = True
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "action": self.action,
            "path": str(self.path),
            "source_id": self.source_id,
            "target_scope": self.target_scope,
            "managed": self.managed,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileOperation":
        return cls(
            operation_id=str(data["operation_id"]),
            action=str(data["action"]),
            path=Path(str(data["path"])),
            source_id=str(data["source_id"]),
            target_scope=str(data["target_scope"]),
            managed=bool(data.get("managed", True)),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True)
class ExternalOperation:
    operation_id: str
    command: str
    args: tuple[str, ...] = ()
    dry_run: bool = True
    required: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "command": self.command,
            "args": list(self.args),
            "dry_run": self.dry_run,
            "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalOperation":
        return cls(
            operation_id=str(data["operation_id"]),
            command=str(data["command"]),
            args=_tuple(data.get("args")),
            dry_run=bool(data.get("dry_run", True)),
            required=bool(data.get("required", True)),
            description=str(data.get("description") or ""),
        )


@dataclass(frozen=True)
class ConfigOperation:
    operation_id: str
    path: Path
    action: str
    description: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "path": str(self.path),
            "action": self.action,
            "description": self.description,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigOperation":
        return cls(
            operation_id=str(data["operation_id"]),
            path=Path(str(data["path"])),
            action=str(data["action"]),
            description=str(data.get("description") or ""),
            required=bool(data.get("required", True)),
        )


@dataclass
class InstallPlan:
    project_root: Path
    workflow: str
    workflow_scope: str
    packs: list[str] = field(default_factory=list)
    resolved_components: list[ResolvedComponent] = field(default_factory=list)
    state_migrations: list[StateMigration] = field(default_factory=list)
    file_operations: list[FileOperation] = field(default_factory=list)
    external_operations: list[ExternalOperation] = field(default_factory=list)
    config_operations: list[ConfigOperation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "project_root": str(self.project_root),
            "workflow": self.workflow,
            "workflow_scope": self.workflow_scope,
            "packs": list(self.packs),
            "resolved_components": [item.to_dict() for item in self.resolved_components],
            "state_migrations": [item.to_dict() for item in self.state_migrations],
            "file_operations": [item.to_dict() for item in self.file_operations],
            "external_operations": [item.to_dict() for item in self.external_operations],
            "config_operations": [item.to_dict() for item in self.config_operations],
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstallPlan":
        schema_version = int(data.get("schema_version", SCHEMA_VERSION))
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported install plan schema_version: {schema_version}")
        return cls(
            project_root=Path(str(data["project_root"])),
            workflow=str(data["workflow"]),
            workflow_scope=str(data["workflow_scope"]),
            packs=[str(item) for item in data.get("packs", [])],
            resolved_components=[
                ResolvedComponent.from_dict(item) for item in data.get("resolved_components", [])
            ],
            state_migrations=[StateMigration.from_dict(item) for item in data.get("state_migrations", [])],
            file_operations=[FileOperation.from_dict(item) for item in data.get("file_operations", [])],
            external_operations=[
                ExternalOperation.from_dict(item) for item in data.get("external_operations", [])
            ],
            config_operations=[ConfigOperation.from_dict(item) for item in data.get("config_operations", [])],
            warnings=[str(item) for item in data.get("warnings", [])],
        )

    @classmethod
    def from_json(cls, content: str) -> "InstallPlan":
        return cls.from_dict(json.loads(content))


@dataclass(frozen=True)
class Receipt:
    operation_id: str
    created_at: str
    project_root: Path
    workflow: dict[str, Any]
    packs: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    config_changes: list[dict[str, Any]] = field(default_factory=list)
    backup_id: str | None = None
    result: str = "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "operation_id": self.operation_id,
            "created_at": self.created_at,
            "project_root": str(self.project_root),
            "workflow": self.workflow,
            "packs": self.packs,
            "sources": self.sources,
            "files": self.files,
            "config_changes": self.config_changes,
            "backup_id": self.backup_id,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Receipt":
        schema_version = int(data.get("schema_version", SCHEMA_VERSION))
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported receipt schema_version: {schema_version}")
        return cls(
            operation_id=str(data["operation_id"]),
            created_at=str(data["created_at"]),
            project_root=Path(str(data["project_root"])),
            workflow=_dict(data.get("workflow")),
            packs=list(data.get("packs", [])),
            sources=list(data.get("sources", [])),
            files=list(data.get("files", [])),
            config_changes=list(data.get("config_changes", [])),
            backup_id=data.get("backup_id"),
            result=str(data.get("result") or "success"),
        )


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    ok: bool
    severity: str
    message: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "ok": self.ok,
            "severity": self.severity,
            "message": self.message,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckResult":
        return cls(
            check_id=str(data["check_id"]),
            ok=bool(data["ok"]),
            severity=str(data.get("severity") or "info"),
            message=str(data.get("message") or ""),
            detail=str(data.get("detail") or ""),
        )
