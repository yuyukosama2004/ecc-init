from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from ..core.models import ComponentSpec, InstallPlan
from ..core.transaction import Transaction
from ..errors import ConflictError, SourceError
from ..resources import read_resource_text
from ..sources import GitHubArchiveProvider
from ..util import read_text, sha256_text
from .registry import Registry


@dataclass(frozen=True)
class InstalledFile:
    path: Path
    component_id: str
    source_id: str
    owner: str
    sha256: str
    previous_sha256: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "component_id": self.component_id,
            "source_id": self.source_id,
            "owner": self.owner,
            "sha256": self.sha256,
            "previous_sha256": self.previous_sha256,
            "status": self.status,
        }


@dataclass
class ComponentInstallReport:
    files_planned: list[dict[str, Any]] = field(default_factory=list)
    files_written: list[InstalledFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _managed_entry(state: dict[str, Any], path: Path) -> dict[str, Any] | None:
    managed = state.get("managed_files", {})
    if not isinstance(managed, dict):
        return None
    value = managed.get(str(path.resolve()))
    return value if isinstance(value, dict) else None


def _component_owner(plan: InstallPlan, registry: Registry, component_id: str) -> str:
    owners = [
        f"pack:{pack_id}"
        for pack_id in plan.packs
        if pack_id in registry.packs and component_id in registry.packs[pack_id].components
    ]
    return owners[0] if owners else f"component:{component_id}"


def _safe_source_path(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts:
        raise SourceError(f"unsafe source projection path: {relative}")
    candidate = root.joinpath(*posix.parts)
    resolved_candidate = candidate.resolve()
    resolved_root = root.resolve()
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise SourceError(f"source projection escapes root: {relative}")
    return candidate


class ComponentInstaller:
    def __init__(self, registry: Registry):
        self.registry = registry

    def _read_bundled_component(self, component: ComponentSpec) -> str:
        includes = list(component.projection_include)
        if len(includes) != 1:
            raise SourceError(f"bundled component {component.component_id} must project exactly one file in this batch")
        include = includes[0]
        if include.endswith("/"):
            raise SourceError(f"bundled directory projection is not enabled in this batch: {component.component_id}")
        return read_resource_text(include)

    def _read_github_archive_component(self, component: ComponentSpec, *, cache_dir: Path, offline: bool) -> str:
        source = self.registry.sources[component.source_id]
        includes = list(component.projection_include)
        if len(includes) != 1:
            raise SourceError(f"github archive component {component.component_id} must project exactly one file in this batch")
        include = includes[0]
        if include.endswith("/"):
            raise SourceError(f"github archive directory projection is not enabled in this batch: {component.component_id}")
        resolved = GitHubArchiveProvider().resolve(source, cache_dir, offline=offline)
        source_root = resolved.root
        if source.path:
            source_root = _safe_source_path(source_root, source.path)
            if source_root.is_symlink():
                raise SourceError(f"unsafe source projection symlink: {source_root}")
        candidate = _safe_source_path(source_root, include)
        if candidate.is_symlink():
            raise SourceError(f"unsafe source projection symlink: {candidate}")
        if not candidate.is_file():
            raise SourceError(f"github archive component file not found: {component.component_id} -> {include}")
        return candidate.read_text(encoding="utf-8")

    def install(
        self,
        plan: InstallPlan,
        *,
        transaction: Transaction,
        state: dict[str, Any],
        cache_dir: Path | None = None,
        offline: bool = False,
    ) -> ComponentInstallReport:
        report = ComponentInstallReport(files_planned=[operation.to_dict() for operation in plan.file_operations])
        for resolved in plan.resolved_components:
            component = self.registry.components.get(resolved.component_id)
            if component is None:
                report.errors.append(f"unknown component: {resolved.component_id}")
                continue
            source = self.registry.sources.get(component.source_id)
            if source is None:
                report.errors.append(f"unknown source for component: {component.component_id}")
                continue
            if source.kind not in {"bundled", "github_archive"}:
                if component.required:
                    report.errors.append(f"unsupported required source kind for component: {component.component_id} ({source.kind})")
                else:
                    report.warnings.append(f"skipped unsupported optional component: {component.component_id}")
                continue
            if component.target_scope != "project":
                report.warnings.append(f"skipped non-project component in apply batch: {component.component_id}")
                continue

            target = resolved.target_path
            owner = _component_owner(plan, self.registry, component.component_id)
            try:
                if source.kind == "bundled":
                    incoming = self._read_bundled_component(component)
                else:
                    if cache_dir is None:
                        raise SourceError(f"cache directory is required for github archive component: {component.component_id}")
                    incoming = self._read_github_archive_component(component, cache_dir=cache_dir, offline=offline)
            except SourceError as exc:
                if component.required:
                    report.errors.append(str(exc))
                else:
                    report.warnings.append(f"skipped optional component {component.component_id}: {exc}")
                continue
            incoming_hash = sha256_text(incoming)
            existing_content = read_text(target)
            previous_hash = sha256_text(existing_content) if target.exists() else None
            managed_entry = _managed_entry(state, target)

            if target.exists() and managed_entry is None:
                report.warnings.append(f"preserved existing unowned file: {target}")
                continue
            if target.exists() and managed_entry is not None:
                recorded_hash = managed_entry.get("sha256")
                if recorded_hash and previous_hash != recorded_hash:
                    report.warnings.append(f"preserved user-modified managed file: {target}")
                    continue
                status = "updated"
            else:
                status = "created"

            try:
                transaction.write_text(target, incoming, owner=owner)
            except OSError as exc:
                raise ConflictError(f"failed to write component {component.component_id} to {target}: {exc}") from exc

            report.files_written.append(
                InstalledFile(
                    path=target,
                    component_id=component.component_id,
                    source_id=component.source_id,
                    owner=owner,
                    sha256=incoming_hash,
                    previous_sha256=previous_hash,
                    status=status,
                )
            )
        return report
