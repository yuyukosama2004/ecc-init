from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..core.models import ExternalOperation, FileOperation, InstallPlan, ResolvedComponent
from ..detect import detect_project
from ..errors import ConfigError
from ..paths import AppPaths
from .registry import Registry, load_registry


def _stable_file_operation_id(component_id: str) -> str:
    return f"file:{component_id}"


def _target_path(paths: AppPaths, target_scope: str, target_subdir: str) -> Path:
    if target_scope == "global":
        return paths.claude_home / Path(target_subdir)
    if target_scope == "project":
        return paths.project_root / Path(target_subdir)
    raise ConfigError(f"unknown target scope: {target_scope}")


def _selected_profile_packs(
    registry: Registry,
    profile_id: str,
    detected_stacks: set[str],
    include_packs: Iterable[str],
    exclude_packs: Iterable[str],
) -> list[str]:
    profile = registry.profiles.get(profile_id)
    if profile is None:
        raise ConfigError(f"unknown profile: {profile_id}")

    explicit = list(dict.fromkeys(str(item) for item in include_packs))
    excluded = set(str(item) for item in exclude_packs)
    selected: list[str] = []
    for pack_id in profile.packs:
        pack = registry.packs[pack_id]
        if pack.stack_conditions and not all(stack in detected_stacks for stack in pack.stack_conditions):
            continue
        selected.append(pack_id)
    for pack_id in explicit:
        if pack_id not in registry.packs:
            raise ConfigError(f"unknown pack: {pack_id}")
        if pack_id not in selected:
            selected.append(pack_id)
    return [pack_id for pack_id in selected if pack_id not in excluded]


def resolve_pack_order(registry: Registry, selected_packs: Iterable[str]) -> list[str]:
    selected = list(dict.fromkeys(str(item) for item in selected_packs))
    selected_set = set(selected)
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(pack_id: str, trail: tuple[str, ...]) -> None:
        if pack_id not in registry.packs:
            raise ConfigError(f"unknown pack: {pack_id}")
        if pack_id in visited:
            return
        if pack_id in visiting:
            cycle = " -> ".join((*trail, pack_id))
            raise ConfigError(f"pack dependency cycle: {cycle}")
        visiting.add(pack_id)
        pack = registry.packs[pack_id]
        for required in pack.requires:
            if required not in selected_set:
                raise ConfigError(f"pack {pack_id} requires excluded or missing pack {required}")
            visit(required, (*trail, pack_id))
        visiting.remove(pack_id)
        visited.add(pack_id)
        ordered.append(pack_id)

    for pack_id in selected:
        visit(pack_id, ())

    for pack_id in ordered:
        pack = registry.packs[pack_id]
        for conflict in pack.conflicts:
            if conflict in selected_set:
                raise ConfigError(f"pack {pack_id} conflicts with pack {conflict}")
    return ordered


def build_registry_install_plan(
    project_root: Path | None = None,
    *,
    profile_id: str = "default",
    include_packs: Iterable[str] = (),
    exclude_packs: Iterable[str] = (),
    workflow: str | None = None,
) -> InstallPlan:
    paths = AppPaths.build(project_root)
    registry = load_registry()
    detection = detect_project(paths.project_root)
    detected_stacks = set(detection.stacks)
    selected = _selected_profile_packs(registry, profile_id, detected_stacks, include_packs, exclude_packs)
    ordered_packs = resolve_pack_order(registry, selected)
    profile = registry.profiles[profile_id]
    workflow_id = workflow or profile.workflow
    workflow_spec = registry.workflows.get(workflow_id)
    if workflow_spec is None:
        raise ConfigError(f"unknown workflow: {workflow_id}")

    components: list[ResolvedComponent] = []
    file_operations: list[FileOperation] = []
    seen_components: set[str] = set()
    for pack_id in ordered_packs:
        pack = registry.packs[pack_id]
        for component_id in pack.components:
            if component_id in seen_components:
                continue
            seen_components.add(component_id)
            component = registry.components[component_id]
            target = _target_path(paths, component.target_scope, component.target_subdir)
            components.append(
                ResolvedComponent(
                    component_id=component.component_id,
                    install_name=component.install_name,
                    source_id=component.source_id,
                    target_scope=component.target_scope,
                    target_path=target,
                    required=component.required,
                )
            )
            file_operations.append(
                FileOperation(
                    operation_id=_stable_file_operation_id(component.component_id),
                    action="plan-install",
                    path=target,
                    source_id=component.source_id,
                    target_scope=component.target_scope,
                    managed=True,
                    required=component.required,
                )
            )

    warnings = [
        "This is a declarative plan preview; it does not install GSD or write project files.",
        "The gsd workflow is declaration-only until the workflow adapter phase is implemented.",
    ]
    external_operations: list[ExternalOperation] = []
    if workflow_spec.workflow_id == "gsd":
        source = registry.sources.get(workflow_spec.source_id or "")
        if source and source.package and source.version:
            external_operations.append(
                ExternalOperation(
                    operation_id="external:gsd-install",
                    command="npx",
                    args=("-y", f"{source.package}@{source.version}"),
                    dry_run=True,
                    required=True,
                    description="Pinned GSD Core installer command preview.",
                )
            )
    return InstallPlan(
        project_root=paths.project_root,
        workflow=workflow_spec.workflow_id,
        workflow_scope=workflow_spec.scope_default,
        packs=ordered_packs,
        resolved_components=components,
        file_operations=file_operations,
        external_operations=external_operations,
        warnings=warnings,
    )
