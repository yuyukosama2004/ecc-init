from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .. import __version__
from ..backup import BackupSession
from ..core.models import Receipt
from ..core.plan import new_operation_id
from ..core.receipt import ReceiptStore
from ..detect import detect_project
from ..paths import AppPaths
from ..project import structure_fingerprint
from ..util import load_json, now_iso, read_text, sha256_text, write_json_atomic, write_text_atomic
from .reports import MigrationAction, MigrationPlan, MigrationReport


DEPRECATED_WORKFLOW_SKILLS = ("task-planning", "verification-loop", "dev-retrospective")
GLOBAL_START = "<!-- ecc-init:start global -->"
GLOBAL_END = "<!-- ecc-init:end global -->"
PROJECT_START = "<!-- ecc-init:start project -->"
PROJECT_END = "<!-- ecc-init:end project -->"


def _managed_record(state: dict[str, Any], path: Path) -> dict[str, Any] | None:
    records = state.get("managed_files", {})
    if not isinstance(records, dict):
        return None
    record = records.get(str(path.resolve()))
    return record if isinstance(record, dict) else None


def _is_clean_managed_file(state: dict[str, Any], path: Path) -> bool:
    record = _managed_record(state, path)
    if not record or not path.exists():
        return False
    expected = record.get("base_hash")
    return bool(expected) and sha256_text(read_text(path)) == expected


def _remove_section(content: str, start: str, end: str) -> tuple[str, bool]:
    start_index = content.find(start)
    end_index = content.find(end)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        return content, False
    end_index += len(end)
    prefix = content[:start_index].rstrip()
    suffix = content[end_index:].lstrip()
    if prefix and suffix:
        return prefix + "\n\n" + suffix, True
    if prefix:
        return prefix + "\n", True
    if suffix:
        return suffix, True
    return "", True


def _state_version(path: Path) -> int | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    value = payload.get("schema_version", payload.get("version"))
    return int(value) if isinstance(value, int) else None


def detect_legacy_v1(project_root: Path | None = None) -> bool:
    paths = AppPaths.build(project_root)
    if _state_version(paths.project_state) == 1 or _state_version(paths.global_state) == 1:
        return True
    if GLOBAL_START in read_text(paths.global_claude_md) or PROJECT_START in read_text(paths.project_claude_md):
        return True
    return any((paths.global_skills / skill / "SKILL.md").exists() for skill in DEPRECATED_WORKFLOW_SKILLS)


def _add_section_action(
    actions: list[MigrationAction],
    state: dict[str, Any],
    path: Path,
    start: str,
    status_action: str,
) -> None:
    if start not in read_text(path):
        return
    if _is_clean_managed_file(state, path):
        actions.append(MigrationAction(status_action, path, "apply", "clean managed section"))
    else:
        actions.append(MigrationAction(status_action, path, "preserve", "local modifications or missing baseline"))


def _add_skill_action(actions: list[MigrationAction], state: dict[str, Any], path: Path, skill: str) -> None:
    if not path.exists():
        return
    if _is_clean_managed_file(state, path):
        actions.append(MigrationAction("remove-deprecated-skill", path.parent, "apply", skill))
    else:
        actions.append(MigrationAction("preserve-modified-skill", path.parent, "preserve", skill))


def build_migration_plan(project_root: Path | None = None) -> MigrationPlan:
    paths = AppPaths.build(project_root)
    global_state = load_json(paths.global_state)
    project_state = load_json(paths.project_state)
    actions: list[MigrationAction] = []
    warnings: list[str] = []
    detected = detect_legacy_v1(paths.project_root)
    if not detected:
        return MigrationPlan(paths.project_root, detected=False)

    _add_section_action(actions, global_state, paths.global_claude_md, GLOBAL_START, "remove-global-managed-section")
    _add_section_action(actions, project_state, paths.project_claude_md, PROJECT_START, "remove-project-managed-section")
    for skill in DEPRECATED_WORKFLOW_SKILLS:
        _add_skill_action(actions, global_state, paths.global_skills / skill / "SKILL.md", skill)

    if any(action.status == "preserve" for action in actions):
        warnings.append("Some legacy files were locally modified and will be preserved for manual review.")
    actions.append(MigrationAction("write-state-v2", paths.project_state, "apply", "workflow authority becomes gsd"))
    actions.append(MigrationAction("write-migration-report", paths.docs_dir / "ecc-init-migration-report.md", "apply"))
    return MigrationPlan(paths.project_root, detected=True, actions=actions, warnings=warnings)


def _backup_directory_files(path: Path, backup: BackupSession) -> None:
    if not path.exists():
        return
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        backup.record_before_change(child)


def _apply_action(action: MigrationAction, backup: BackupSession) -> None:
    if action.status != "apply":
        return
    if action.action == "remove-global-managed-section":
        content, changed = _remove_section(read_text(action.path), GLOBAL_START, GLOBAL_END)
        if changed:
            backup.record_before_change(action.path)
            write_text_atomic(action.path, content)
    elif action.action == "remove-project-managed-section":
        content, changed = _remove_section(read_text(action.path), PROJECT_START, PROJECT_END)
        if changed:
            backup.record_before_change(action.path)
            write_text_atomic(action.path, content)
    elif action.action == "remove-deprecated-skill":
        _backup_directory_files(action.path, backup)
        if action.path.exists():
            shutil.rmtree(action.path)


def _filtered_managed_files(previous: dict[str, Any], removed_paths: set[str]) -> dict[str, Any]:
    records = previous.get("managed_files", {})
    if not isinstance(records, dict):
        return {}
    return {path: record for path, record in records.items() if path not in removed_paths}


def _state_v2(
    paths: AppPaths,
    previous: dict[str, Any],
    operation_id: str,
    removed_paths: set[str],
    legacy_workflow_removed: bool,
) -> dict[str, Any]:
    detection = detect_project(paths.project_root)
    return {
        "schema_version": 2,
        "tool_version": __version__,
        "project_root": str(paths.project_root),
        "detected_stacks": detection.stacks,
        "detection_evidence": detection.evidence,
        "workflow": {
            "id": "gsd",
            "scope": "global",
            "requested_version": "1.6.1",
            "resolved_version": None,
            "installed": (paths.project_root / ".planning" / "config.json").exists(),
        },
        "profiles": ["default"],
        "agent_policy": {
            "profile": "default",
            "max_concurrent_agents": 3,
            "plan_level_parallel": True,
            "task_level_parallel": False,
            "advisory_phase_budget": 8,
        },
        "packs": {
            "ecc-init/legacy-v1": {
                "migrated_at": now_iso(),
                "previous_installed_skills": previous.get("installed_skills", []),
            }
        },
        "managed_files": _filtered_managed_files(previous, removed_paths),
        "source_locks": {},
        "pending_gsd_config": {},
        "code_tour_completed": False,
        "last_operation_id": operation_id,
        "last_initialized_at": previous.get("last_initialized_at") or now_iso(),
        "structure_fingerprint": structure_fingerprint(paths.project_root),
        "migration": {
            "from_schema": 1,
            "to_schema": 2,
            "legacy_workflow_removed": legacy_workflow_removed,
        },
    }


def _global_state_v2(previous: dict[str, Any], operation_id: str, removed_paths: set[str]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "tool_version": __version__,
        "workflow": {"id": "gsd", "scope": "global", "installed": False},
        "legacy_v1": {
            "migrated_at": now_iso(),
            "deprecated_workflow_skills": list(DEPRECATED_WORKFLOW_SKILLS),
        },
        "managed_files": _filtered_managed_files(previous, removed_paths),
        "last_operation_id": operation_id,
        "last_run_at": previous.get("last_run_at") or now_iso(),
    }


def _removed_state_paths(paths: AppPaths, actions: list[MigrationAction]) -> tuple[set[str], set[str]]:
    global_removed: set[str] = set()
    project_removed: set[str] = set()
    for action in actions:
        if action.status != "apply":
            continue
        if action.action == "remove-global-managed-section":
            global_removed.add(str(paths.global_claude_md.resolve()))
        elif action.action == "remove-project-managed-section":
            project_removed.add(str(paths.project_claude_md.resolve()))
        elif action.action == "remove-deprecated-skill":
            global_removed.add(str((action.path / "SKILL.md").resolve()))
    return global_removed, project_removed


def migrate_legacy_v1(project_root: Path | None = None, *, dry_run: bool = False) -> MigrationReport:
    paths = AppPaths.build(project_root)
    plan = build_migration_plan(paths.project_root)
    if dry_run or not plan.detected:
        return MigrationReport(
            project_root=plan.project_root,
            detected=plan.detected,
            actions=plan.actions,
            warnings=plan.warnings,
            applied=False,
        )

    backup = BackupSession(paths.backups_dir, paths.project_root)
    operation_id = new_operation_id("migrate")
    previous_project_state = load_json(paths.project_state)
    previous_global_state = load_json(paths.global_state)
    for action in plan.actions:
        _apply_action(action, backup)

    global_removed, project_removed = _removed_state_paths(paths, plan.actions)
    legacy_workflow_removed = not any(action.status == "preserve" for action in plan.actions)
    backup.record_before_change(paths.project_state)
    new_state = _state_v2(paths, previous_project_state, operation_id, project_removed, legacy_workflow_removed)
    write_json_atomic(paths.project_state, new_state)
    backup.record_before_change(paths.global_state)
    write_json_atomic(paths.global_state, _global_state_v2(previous_global_state, operation_id, global_removed))
    report = MigrationReport(
        project_root=plan.project_root,
        detected=True,
        actions=plan.actions,
        warnings=plan.warnings,
        applied=True,
        backup_id=backup.backup_id,
        operation_id=operation_id,
    )
    report_path = paths.docs_dir / "ecc-init-migration-report.md"
    backup.record_before_change(report_path)
    write_text_atomic(report_path, report.to_markdown())
    backup_id = backup.finish()
    receipt = Receipt(
        operation_id=operation_id,
        created_at=now_iso(),
        project_root=paths.project_root,
        workflow={"id": "gsd", "status": "migrated"},
        files=[{"path": str(action.path), "status": action.status, "action": action.action} for action in plan.actions],
        backup_id=backup_id,
        result="success",
    )
    ReceiptStore(paths.operations_dir).save(receipt)
    report.backup_id = backup_id
    return report
