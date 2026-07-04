from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from ..detect import detect_project
from ..paths import AppPaths
from ..resources import read_manifest
from .models import FileOperation, InstallPlan, ResolvedComponent, StateMigration


LEGACY_WORKFLOW = "legacy-ecc"


def new_operation_id(prefix: str = "op") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{timestamp}-{secrets.token_hex(4)}"


def _add_file_operation(
    operations: list[FileOperation],
    components: list[ResolvedComponent],
    *,
    action: str,
    path: Path,
    source_id: str,
    install_name: str,
    target_scope: str,
) -> None:
    operations.append(
        FileOperation(
            operation_id=new_operation_id("file"),
            action=action,
            path=path,
            source_id=source_id,
            target_scope=target_scope,
        )
    )
    components.append(
        ResolvedComponent(
            component_id=source_id,
            install_name=install_name,
            source_id=source_id,
            target_scope=target_scope,
            target_path=path,
        )
    )


def build_legacy_install_plan(project_root: Path | None = None) -> InstallPlan:
    paths = AppPaths.build(project_root)
    manifest = read_manifest()
    detection = detect_project(paths.project_root)
    operations: list[FileOperation] = []
    components: list[ResolvedComponent] = []

    _add_file_operation(
        operations,
        components,
        action="merge-managed-section",
        path=paths.global_claude_md,
        source_id="legacy:global-claude",
        install_name="global CLAUDE.md",
        target_scope="global",
    )
    for skill in manifest["global_skills"]:
        name = str(skill["name"])
        _add_file_operation(
            operations,
            components,
            action="merge-whole-file",
            path=paths.global_skills / name / "SKILL.md",
            source_id=f"legacy:global-skill:{name}",
            install_name=name,
            target_scope="global",
        )

    _add_file_operation(
        operations,
        components,
        action="merge-managed-section",
        path=paths.project_claude_md,
        source_id="legacy:project-claude",
        install_name="project CLAUDE.md",
        target_scope="project",
    )
    project_skill_map = {item["stack"]: item for item in manifest["project_skills"]}
    for stack in detection.stacks:
        item = project_skill_map.get(stack)
        if not item:
            continue
        name = str(item["name"])
        _add_file_operation(
            operations,
            components,
            action="merge-whole-file",
            path=paths.project_skills / name / "SKILL.md",
            source_id=f"legacy:project-skill:{name}",
            install_name=name,
            target_scope="project",
        )

    for source_id, path, label, target_scope in (
        ("legacy:development-log", paths.docs_dir / "DEVELOPMENT_LOG.md", "DEVELOPMENT_LOG.md", "project"),
        ("legacy:project-overview", paths.docs_dir / "PROJECT_OVERVIEW.md", "PROJECT_OVERVIEW.md", "project"),
        ("legacy:project-state-v1", paths.project_state, "ecc-init-state.json", "project"),
        ("legacy:global-state-v1", paths.global_state, "state.json", "global"),
    ):
        _add_file_operation(
            operations,
            components,
            action="create-or-update",
            path=path,
            source_id=source_id,
            install_name=label,
            target_scope=target_scope,
        )

    warnings = [
        "This is a legacy ecc-init 0.1.x plan preview; it does not install or modify GSD.",
        "Network-synced ECC skills are represented as legacy project-skill operations and are not fetched during planning.",
    ]
    if not detection.stacks:
        warnings.append("No project stack was detected, so only global and baseline project files are planned.")

    return InstallPlan(
        project_root=paths.project_root,
        workflow=LEGACY_WORKFLOW,
        workflow_scope="global+project",
        packs=["legacy-global", *[f"legacy-stack:{stack}" for stack in detection.stacks]],
        resolved_components=components,
        state_migrations=[StateMigration(from_schema=1, to_schema=2, description="future v1 to v2 migration")],
        file_operations=operations,
        warnings=warnings,
    )
