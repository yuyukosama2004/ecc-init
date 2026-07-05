from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .backup import BackupSession, list_backups, rollback_backup
from .core.models import Receipt
from .core.ownership import managed_file_statuses
from .core.plan import new_operation_id
from .core.receipt import ReceiptStore
from .detect import DetectionResult, detect_project
from .errors import ConfigError
from .frontend import frontend_doctor_checks
from .merge import InstallResult, install_managed_section, install_whole_file
from .migration import detect_legacy_v1
from .paths import AppPaths
from .packs import build_registry_install_plan, load_registry
from .packs.gsd_bridge import POLICY_PROFILES, build_gsd_config, remove_pack_agent_skills
from .project import render_project_overview, render_project_section, structure_fingerprint
from .resources import read_manifest, read_resource_text
from .sources import SourceLockStore, verify_registry_sources
from .sync import fetch_upstream_skill, resolve_stable_ref
from .util import human_bool, load_json, now_iso, read_text, sha256_text, write_json_atomic, write_text_atomic
from .workflows import GsdWorkflowAdapter


GLOBAL_START = "<!-- ecc-init:start global -->"
GLOBAL_END = "<!-- ecc-init:end global -->"
PROJECT_START = "<!-- ecc-init:start project -->"
PROJECT_END = "<!-- ecc-init:end project -->"
SUPPORTED_APPLY_SOURCE_KINDS = {"bundled", "github_archive"}


@dataclass
class RunReport:
    project_root: Path
    detection: DetectionResult
    results: list[InstallResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backup_id: str | None = None
    upstream_ref: str | None = None

    @property
    def conflicts(self) -> list[InstallResult]:
        return [result for result in self.results if result.status in {"conflict", "preserved"}]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "detected_stacks": list(self.detection.stacks),
            "detection_evidence": self.detection.evidence,
            "results": [
                {
                    "path": str(result.path),
                    "status": result.status,
                    "message": result.message,
                }
                for result in self.results
            ],
            "warnings": list(self.warnings),
            "backup_id": self.backup_id,
            "upstream_ref": self.upstream_ref,
            "conflicts": [
                {
                    "path": str(result.path),
                    "status": result.status,
                    "message": result.message,
                }
                for result in self.conflicts
            ],
        }


def _planned_command_to_dict(command) -> dict[str, Any]:
    return {
        "args": list(command.args),
        "description": command.description,
        "dry_run": command.dry_run,
    }


def _environment_check_to_dict(check) -> dict[str, Any]:
    return {
        "check_id": check.check_id,
        "ok": check.ok,
        "message": check.message,
        "detail": check.detail,
    }


def _command_result_to_dict(result) -> dict[str, Any]:
    return {
        "args": list(result.args),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _workflow_result_to_dict(result) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "workflow_id": result.workflow_id,
        "status": result.status,
        "ok": result.ok,
        "commands": [_planned_command_to_dict(command) for command in result.commands],
        "checks": [_environment_check_to_dict(check) for check in result.checks],
        "logs": [_command_result_to_dict(log) for log in result.logs],
        "warnings": list(result.warnings),
    }


def _status_conflicts(paths: AppPaths) -> tuple[list[str], list[str]]:
    status = project_status(paths.project_root)
    return list(status["conflicts"]), list(status["modified_managed_files"])


def _nearest_existing_parent(path: Path) -> Path | None:
    current = path if path.exists() else path.parent
    while True:
        if current.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def _writable_path_check(path: Path) -> tuple[bool, str]:
    if path.exists():
        return os.access(path, os.W_OK), str(path)
    parent = _nearest_existing_parent(path)
    if parent is None:
        return False, f"{path} (missing; no existing parent)"
    return os.access(parent, os.W_OK), f"{path} (missing; parent {parent})"


def _plan_audit(paths: AppPaths, registry) -> dict[str, Any]:
    try:
        plan = build_registry_install_plan(paths.project_root)
    except ConfigError as exc:
        return {
            "valid": False,
            "error": str(exc),
            "workflow": None,
            "packs": [],
            "sources": [],
            "unsupported_source_kinds": [],
            "unsupported_required_source_kinds": [],
            "component_count": 0,
            "file_operation_count": 0,
            "external_operation_count": 0,
            "config_operation_count": 0,
        }

    source_ids = sorted({component.source_id for component in plan.resolved_components})
    unsupported: list[dict[str, Any]] = []
    unsupported_required: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for source_id in source_ids:
        source = registry.sources.get(source_id)
        kind = source.kind if source else "unknown"
        item = {"source_id": source_id, "kind": kind}
        sources.append(item)
        if source is None or kind not in SUPPORTED_APPLY_SOURCE_KINDS:
            unsupported.append(item)
            if any(component.source_id == source_id and component.required for component in plan.resolved_components):
                unsupported_required.append(item)

    return {
        "valid": True,
        "error": None,
        "workflow": {"id": plan.workflow, "scope": plan.workflow_scope},
        "packs": list(plan.packs),
        "sources": sources,
        "unsupported_source_kinds": unsupported,
        "unsupported_required_source_kinds": unsupported_required,
        "component_count": len(plan.resolved_components),
        "file_operation_count": len(plan.file_operations),
        "external_operation_count": len(plan.external_operations),
        "config_operation_count": len(plan.config_operations),
    }


def _source_lock_status(paths: AppPaths, registry) -> dict[str, Any]:
    base = {
        "path": str(paths.source_lock),
        "exists": paths.source_lock.exists(),
        "valid": False,
        "status": "missing",
        "source_count": 0,
        "sources": {},
        "unknown_sources": [],
        "unsupported_source_kinds": [],
        "error": None,
    }
    if not paths.source_lock.exists():
        return base
    try:
        locks = SourceLockStore(paths.source_lock).load_all()
    except (ConfigError, KeyError, TypeError, ValueError) as exc:
        base.update({"status": "invalid", "error": str(exc)})
        return base

    unknown_sources = sorted(source_id for source_id in locks if source_id not in registry.sources)
    unsupported = []
    for source_id in sorted(locks):
        source = registry.sources.get(source_id)
        if source is not None and source.kind not in SUPPORTED_APPLY_SOURCE_KINDS:
            unsupported.append({"source_id": source_id, "kind": source.kind})
    base.update(
        {
            "valid": True,
            "status": "present",
            "source_count": len(locks),
            "sources": {source_id: lock.to_dict() for source_id, lock in sorted(locks.items())},
            "unknown_sources": unknown_sources,
            "unsupported_source_kinds": unsupported,
        }
    )
    return base


def _latest_receipt_status(paths: AppPaths) -> dict[str, Any]:
    base = {
        "path": str(paths.operations_dir),
        "exists": False,
        "valid": False,
        "status": "missing",
        "operation_id": None,
        "created_at": None,
        "result": None,
        "backup_id": None,
        "workflow": None,
        "packs": [],
        "sources": [],
        "file_count": 0,
        "config_change_count": 0,
        "invalid_receipt_count": 0,
        "error": None,
    }
    receipt_paths = sorted(paths.operations_dir.glob("*/receipt.json"), key=lambda path: path.parent.name, reverse=True)
    if not receipt_paths:
        return base

    invalid_count = 0
    store = ReceiptStore(paths.operations_dir)
    for receipt_path in receipt_paths:
        try:
            receipt = store.load_path(receipt_path)
        except (ConfigError, KeyError, TypeError, ValueError) as exc:
            invalid_count += 1
            base["error"] = str(exc)
            continue
        if receipt.project_root.expanduser().resolve() != paths.project_root:
            continue
        return {
            "path": str(receipt_path),
            "exists": True,
            "valid": True,
            "status": "present",
            "operation_id": receipt.operation_id,
            "created_at": receipt.created_at,
            "result": receipt.result,
            "backup_id": receipt.backup_id,
            "workflow": receipt.workflow,
            "packs": receipt.packs,
            "sources": receipt.sources,
            "file_count": len(receipt.files),
            "config_change_count": len(receipt.config_changes),
            "invalid_receipt_count": invalid_count,
            "error": None,
        }

    base["invalid_receipt_count"] = invalid_count
    if invalid_count:
        base["status"] = "missing_for_project"
    return base


def _gsd_runtime_status(paths: AppPaths) -> dict[str, Any]:
    try:
        result = GsdWorkflowAdapter().status(paths, runtime="claude", scope="global")
    except Exception as exc:
        return {
            "workflow_id": "gsd",
            "status": "error",
            "ok": False,
            "commands": [],
            "checks": [],
            "logs": [],
            "warnings": [str(exc)],
        }
    return _workflow_result_to_dict(result) or {
        "workflow_id": "gsd",
        "status": "unknown",
        "ok": False,
        "commands": [],
        "checks": [],
        "logs": [],
        "warnings": [],
    }


def _pack_summary(project_state: dict[str, Any], plan_audit: dict[str, Any], registry) -> dict[str, Any]:
    raw_installed = project_state.get("packs", {})
    if not isinstance(raw_installed, dict):
        raw_installed = {}
    managed_files = project_state.get("managed_files", {})
    if not isinstance(managed_files, dict):
        managed_files = {}

    # Build component→pack mapping from registry
    component_pack: dict[str, str] = {}
    for pack_id, pack in registry.packs.items():
        for component_id in pack.components:
            component_pack[component_id] = pack_id

    installed: dict[str, dict[str, Any]] = {}
    for pack_id in sorted(raw_installed):
        pack_entry = raw_installed[pack_id]
        if isinstance(pack_entry, dict) and "status" in pack_entry:
            # Prefer persisted pack state (new schema)
            installed[pack_id] = {
                "version": pack_entry.get("version", 1),
                "status": pack_entry.get("status", "unknown"),
                "components_applied": pack_entry.get("components_applied", []),
                "components_skipped": pack_entry.get("components_skipped", []),
            }
            continue

        # Fallback: derive from managed_files (legacy schema)
        pack = registry.packs.get(pack_id)
        expected = set(pack.components) if pack else set()
        pack_components_set: set[str] = set()
        for path_str, entry in managed_files.items():
            if not isinstance(entry, dict):
                continue
            component_id = entry.get("component_id")
            if component_id and component_pack.get(component_id) == pack_id:
                pack_components_set.add(component_id)
        missing = expected - pack_components_set
        version = pack_entry.get("version", 1) if isinstance(pack_entry, dict) else 1
        if not expected:
            status = "declaration_only"
        elif not pack_components_set:
            status = "skipped"
        elif missing:
            status = "partial"
        else:
            status = "applied"
        installed[pack_id] = {
            "version": version,
            "status": status,
            "components_applied": sorted(pack_components_set),
            "components_skipped": [{"component_id": c, "reason": "legacy: derived from managed_files"} for c in sorted(missing)],
        }

    return {
        "installed": installed,
        "planned": list(plan_audit.get("packs", [])),
    }


def _plan_consistency(project_state: dict[str, Any], plan_audit: dict[str, Any]) -> dict[str, Any]:
    installed = project_state.get("packs", {})
    if not isinstance(installed, dict):
        installed = {}
    installed_ids = set(installed)
    planned_ids = set(plan_audit.get("packs", [])) if plan_audit.get("valid") else set()
    missing = sorted(planned_ids - installed_ids)
    extra = sorted(installed_ids - planned_ids)
    if not installed_ids:
        status = "not_applied"
    elif not plan_audit.get("valid"):
        status = "unknown"
    elif not missing and not extra:
        status = "matches"
    else:
        status = "drift"
    return {
        "status": status,
        "missing_packs": missing,
        "extra_packs": extra,
    }


def _receipt_consistency(project_state: dict[str, Any], receipt_status: dict[str, Any]) -> dict[str, Any]:
    state_operation_id = project_state.get("last_operation_id")
    receipt_operation_id = receipt_status.get("operation_id")
    if not state_operation_id and not receipt_operation_id:
        status = "not_applied"
    elif state_operation_id and state_operation_id == receipt_operation_id:
        status = "matches"
    elif state_operation_id and not receipt_operation_id:
        status = "missing_receipt"
    else:
        status = "mismatch"
    return {
        "status": status,
        "state_operation_id": state_operation_id,
        "receipt_operation_id": receipt_operation_id,
    }


def _apply_readiness(
    *,
    conflicts: list[str],
    modified_managed_files: list[str],
    plan_audit: dict[str, Any],
    source_lock_status: dict[str, Any],
    receipt_status: dict[str, Any],
    workflow_status: dict[str, Any],
    project_state: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not plan_audit.get("valid"):
        blockers.append(f"install plan could not be built: {plan_audit.get('error')}")
    if conflicts:
        blockers.append(f"{len(conflicts)} conflict file(s) require review")
    if modified_managed_files:
        blockers.append(f"{len(modified_managed_files)} managed file(s) have local modifications")
    unsupported = plan_audit.get("unsupported_required_source_kinds", [])
    if unsupported:
        blockers.append(
            "unsupported required source kind(s): "
            + ", ".join(f"{item['source_id']} ({item['kind']})" for item in unsupported)
        )

    if workflow_status.get("status") in {"not_installed", "blocked_environment", "error"}:
        warnings.append(f"GSD runtime status is {workflow_status.get('status')}")
    if source_lock_status.get("status") == "missing":
        warnings.append("source lock will be created on first successful apply")
    elif not source_lock_status.get("valid"):
        blockers.append(f"source lock is {source_lock_status.get('status')}")
    if receipt_status.get("status") in {"missing", "missing_for_project"}:
        warnings.append("no apply receipt exists for this project yet")
    elif not receipt_status.get("valid"):
        blockers.append(f"latest receipt is {receipt_status.get('status')}")

    plan_consistency = _plan_consistency(project_state, plan_audit)
    receipt_consistency = _receipt_consistency(project_state, receipt_status)
    if plan_consistency["status"] == "drift":
        warnings.append("installed packs differ from the current plan")
    if receipt_consistency["status"] in {"missing_receipt", "mismatch"}:
        warnings.append("project state and latest receipt do not match")

    ready = not blockers
    return {
        "ready": ready,
        "status": "ready" if ready else "manual_action_required",
        "blockers": blockers,
        "warnings": warnings,
        "plan_consistency": plan_consistency,
        "receipt_consistency": receipt_consistency,
    }


def _read_json_object_strict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"unable to read JSON object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"JSON file must contain an object: {path}")
    return payload


def _save_lifecycle_receipt(
    paths: AppPaths,
    *,
    operation: str,
    workflow_status: str,
    packs: list[dict[str, Any]],
    config_changes: list[dict[str, Any]],
    backup_id: str | None,
    result: str = "success",
) -> str:
    operation_id = new_operation_id(operation)
    receipt = Receipt(
        operation_id=operation_id,
        created_at=now_iso(),
        project_root=paths.project_root,
        workflow={"id": "gsd", "status": workflow_status},
        packs=packs,
        config_changes=config_changes,
        backup_id=backup_id,
        result=result,
    )
    ReceiptStore(paths.operations_dir).save(receipt)
    return operation_id


@dataclass
class UpdateReport:
    project_root: Path
    dry_run: bool
    check: bool
    applied: bool
    plan: Any | None = None
    source_checks: list[Any] = field(default_factory=list)
    workflow_result: Any | None = None
    config_report: Any | None = None
    conflicts: list[str] = field(default_factory=list)
    modified_managed_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backup_id: str | None = None
    operation_id: str | None = None

    @property
    def source_ok(self) -> bool:
        return all(check.ok for check in self.source_checks)

    @property
    def manual_action_required(self) -> bool:
        return bool(self.conflicts or self.modified_managed_files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "dry_run": self.dry_run,
            "check": self.check,
            "applied": self.applied,
            "install_plan": self.plan.to_dict() if self.plan else None,
            "source_checks": [check.to_dict() for check in self.source_checks],
            "workflow_update": _workflow_result_to_dict(self.workflow_result),
            "pack_update": self.config_report.to_dict() if self.config_report else None,
            "conflicts": list(self.conflicts),
            "modified_managed_files": list(self.modified_managed_files),
            "warnings": list(self.warnings),
            "backup_id": self.backup_id,
            "operation_id": self.operation_id,
            "manual_action_required": self.manual_action_required,
        }


@dataclass
class RemoveReport:
    project_root: Path
    dry_run: bool
    applied: bool
    packs: list[str] = field(default_factory=list)
    remove_workflow: bool = False
    remove_all: bool = False
    config_path: Path | None = None
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    workflow_result: Any | None = None
    warnings: list[str] = field(default_factory=list)
    backup_id: str | None = None
    operation_id: str | None = None

    @property
    def changed(self) -> bool:
        return self.after != self.before

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "dry_run": self.dry_run,
            "applied": self.applied,
            "packs": list(self.packs),
            "remove_workflow": self.remove_workflow,
            "remove_all": self.remove_all,
            "config_path": str(self.config_path) if self.config_path else None,
            "changed": self.changed,
            "before": self.before,
            "after": self.after,
            "workflow_remove": _workflow_result_to_dict(self.workflow_result),
            "warnings": list(self.warnings),
            "backup_id": self.backup_id,
            "operation_id": self.operation_id,
        }


def _write_state_if_changed(path: Path, state: dict[str, Any], backup: BackupSession) -> None:
    new_content = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    if read_text(path) == new_content:
        return
    backup.record_before_change(path)
    write_text_atomic(path, new_content)


def _create_if_missing(path: Path, content: str, backup: BackupSession) -> InstallResult:
    if path.exists():
        return InstallResult(path, "unchanged")
    backup.record_before_change(path)
    write_text_atomic(path, content)
    return InstallResult(path, "created")


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _save_operation_receipt(paths: AppPaths, report: RunReport) -> None:
    if not report.backup_id:
        return
    receipt = Receipt(
        operation_id=new_operation_id("init"),
        created_at=now_iso(),
        project_root=paths.project_root,
        workflow={"id": "legacy-ecc", "status": "installed"},
        files=[
            {
                "path": str(result.path),
                "owner": result.message or "legacy-init",
                "sha256": sha256_text(read_text(result.path)) if result.path.exists() else None,
                "previous_sha256": None,
                "status": result.status,
            }
            for result in report.results
        ],
        backup_id=report.backup_id,
        result="success",
    )
    ReceiptStore(paths.operations_dir).save(receipt)


def initialize_project(
    project_root: Path | None = None,
    *,
    offline: bool = False,
    no_sync: bool = False,
) -> RunReport:
    paths = AppPaths.build(project_root)
    paths.ecc_home.mkdir(parents=True, exist_ok=True)
    paths.claude_home.mkdir(parents=True, exist_ok=True)

    manifest = read_manifest()
    global_state = load_json(paths.global_state, {"version": 1, "managed_files": {}})
    project_state = load_json(paths.project_state, {"version": 1, "managed_files": {}})
    backup = BackupSession(paths.backups_dir, paths.project_root)
    detection = detect_project(paths.project_root)
    report = RunReport(project_root=paths.project_root, detection=detection)

    # 1. 全局 CLAUDE.md：只管理标记区域，保留用户原有内容。
    global_section = read_resource_text("templates/global_CLAUDE.md")
    report.results.append(
        install_managed_section(
            target=paths.global_claude_md,
            section=global_section,
            source_id="global-claude",
            start_marker=GLOBAL_START,
            end_marker=GLOBAL_END,
            state=global_state,
            bases_root=paths.bases_dir,
            backup=backup,
        )
    )

    # 2. 六个全局通用 Skill。
    for skill in manifest["global_skills"]:
        content = read_resource_text(skill["resource"])
        target = paths.global_skills / skill["name"] / "SKILL.md"
        report.results.append(
            install_whole_file(
                target=target,
                incoming=content,
                source_id=f"global-skill:{skill['name']}",
                state=global_state,
                bases_root=paths.bases_dir,
                backup=backup,
            )
        )

    # 3. 项目级 CLAUDE.md。
    project_template = read_resource_text("templates/project_CLAUDE.md")
    project_section = render_project_section(project_template, detection)
    report.results.append(
        install_managed_section(
            target=paths.project_claude_md,
            section=project_section,
            source_id="project-claude",
            start_marker=PROJECT_START,
            end_marker=PROJECT_END,
            state=project_state,
            bases_root=paths.bases_dir,
            backup=backup,
        )
    )

    # 4. 自动同步并安装当前项目真正需要的技术栈 Skill。
    upstream_ref: str | None = None
    if no_sync:
        report.warnings.append("已禁用网络同步，使用内置技术栈模板。")
    else:
        upstream_ref, ref_warning = resolve_stable_ref(global_state, offline=offline)
        report.upstream_ref = upstream_ref
        if ref_warning:
            report.warnings.append(ref_warning)

    project_skill_map = {item["stack"]: item for item in manifest["project_skills"]}
    installed_skills: list[str] = []
    skill_sources: dict[str, str] = {}
    for stack in detection.stacks:
        item = project_skill_map.get(stack)
        if not item:
            continue
        fallback = read_resource_text(item["resource"])
        if no_sync:
            content = fallback
            source_label = "bundled"
        else:
            sync = fetch_upstream_skill(
                skill_name=item["name"],
                upstream_path=item.get("upstream_path"),
                fallback=fallback,
                cache_dir=paths.cache_dir,
                ref=upstream_ref or "main",
                offline=offline,
            )
            content = sync.content
            source_label = sync.source + (f"@{sync.ref}" if sync.ref else "")
            if sync.warning:
                report.warnings.append(f"{item['name']}：{sync.warning}")
        target = paths.project_skills / item["name"] / "SKILL.md"
        report.results.append(
            install_whole_file(
                target=target,
                incoming=content,
                source_id=f"project-skill:{item['name']}:{source_label}",
                state=project_state,
                bases_root=paths.bases_dir,
                backup=backup,
            )
        )
        installed_skills.append(item["name"])
        skill_sources[item["name"]] = source_label

    # 5. 开发日志与项目导读骨架。
    docs = paths.docs_dir
    _ensure_directory(docs / "dev-notes")
    report.results.append(
        _create_if_missing(
            docs / "DEVELOPMENT_LOG.md",
            read_resource_text("templates/DEVELOPMENT_LOG.md"),
            backup,
        )
    )
    overview = render_project_overview(read_resource_text("templates/PROJECT_OVERVIEW.md"), detection)
    report.results.append(_create_if_missing(docs / "PROJECT_OVERVIEW.md", overview, backup))

    # 6. 状态：结构发生明显变化时，让 code-tour 在下一次任务中重新触发。
    fingerprint = structure_fingerprint(paths.project_root)
    previous_fingerprint = project_state.get("structure_fingerprint")
    code_tour_completed = bool(project_state.get("code_tour_completed", False))
    if previous_fingerprint and previous_fingerprint != fingerprint:
        code_tour_completed = False
        project_state["code_tour_reset_reason"] = "project-structure-changed"
        project_state["code_tour_reset_at"] = now_iso()

    project_state.update(
        {
            "version": 1,
            "ecc_init_version": __version__,
            "project_root": str(paths.project_root),
            "detected_stacks": detection.stacks,
            "detection_evidence": detection.evidence,
            "commands": detection.commands,
            "installed_skills": installed_skills,
            "skill_sources": skill_sources,
            "structure_fingerprint": fingerprint,
            "code_tour_completed": code_tour_completed,
            "last_initialized_at": now_iso(),
            "upstream_ref": upstream_ref,
        }
    )
    global_state.update(
        {
            "version": 1,
            "ecc_init_version": __version__,
            "last_run_at": now_iso(),
        }
    )

    _write_state_if_changed(paths.project_state, project_state, backup)
    _write_state_if_changed(paths.global_state, global_state, backup)
    report.backup_id = backup.finish()
    _save_operation_receipt(paths, report)
    if detect_legacy_v1(paths.project_root):
        report.warnings.append(
            "Legacy v1 workflow files were detected. Run `ecc-init migrate --dry-run` to preview the v2 migration."
        )
    return report


def update_project(
    project_root: Path | None = None,
    *,
    profile_id: str = "default",
    include_packs: list[str] | None = None,
    exclude_packs: list[str] | None = None,
    update_sources: bool = False,
    update_workflow: bool = False,
    update_packs: bool = False,
    source_ids: list[str] | None = None,
    check: bool = False,
    dry_run: bool = False,
    yes: bool = False,
) -> UpdateReport:
    paths = AppPaths.build(project_root)
    registry = load_registry()
    include_packs = include_packs or []
    exclude_packs = exclude_packs or []
    source_ids = source_ids or []
    scoped = update_sources or update_workflow or update_packs or bool(source_ids)
    run_sources = update_sources or bool(source_ids) or not scoped
    run_workflow = update_workflow or not scoped
    run_packs = update_packs or bool(include_packs or exclude_packs) or not scoped
    effective_dry_run = dry_run or check or not yes
    warnings: list[str] = []
    if not yes and not dry_run and not check:
        warnings.append("No --yes supplied; update is reported as a dry-run preview.")

    plan = build_registry_install_plan(
        paths.project_root,
        profile_id=profile_id,
        include_packs=include_packs,
        exclude_packs=exclude_packs,
    )
    source_checks = []
    if run_sources:
        unknown_sources = sorted(set(source_ids) - set(registry.sources))
        if unknown_sources:
            raise ConfigError(f"unknown source: {', '.join(unknown_sources)}")
        source_checks = verify_registry_sources(registry)
        if source_ids:
            allowed_prefixes = tuple(f"source:{source_id}:" for source_id in source_ids)
            source_checks = [check for check in source_checks if check.check_id.startswith(allowed_prefixes)]
        warnings.append("Source update is preview-only in this phase; no network fetch was executed.")

    workflow_result = None
    if run_workflow:
        workflow_result = GsdWorkflowAdapter().update(paths, dry_run=effective_dry_run)

    config_report = None
    backup_id = None
    operation_id = None
    if run_packs:
        config_report = build_gsd_config(paths.project_root, profile_id=profile_id, packs=plan.packs)
        if not config_report.initialized:
            warnings.append("GSD config is not initialized; Pack update is preview-only.")
        if config_report.initialized and config_report.changed and not effective_dry_run:
            backup = BackupSession(paths.backups_dir, paths.project_root)
            backup.record_before_change(config_report.config_path)
            write_json_atomic(config_report.config_path, config_report.after)
            backup_id = backup.finish()
            operation_id = _save_lifecycle_receipt(
                paths,
                operation="update",
                workflow_status=workflow_result.status if workflow_result else "config-updated",
                packs=[{"pack_id": pack_id, "action": "update"} for pack_id in plan.packs],
                config_changes=[
                    {
                        "path": str(config_report.config_path),
                        "action": "update-gsd-config",
                        "before": config_report.before,
                        "after": config_report.after,
                    }
                ],
                backup_id=backup_id,
            )

    conflicts, modified_managed_files = _status_conflicts(paths)
    return UpdateReport(
        project_root=paths.project_root,
        dry_run=effective_dry_run,
        check=check,
        applied=not effective_dry_run,
        plan=plan,
        source_checks=source_checks,
        workflow_result=workflow_result,
        config_report=config_report,
        conflicts=conflicts,
        modified_managed_files=modified_managed_files,
        warnings=warnings,
        backup_id=backup_id,
        operation_id=operation_id,
    )


def remove_project(
    project_root: Path | None = None,
    *,
    pack_ids: list[str] | None = None,
    workflow: bool = False,
    all_: bool = False,
    dry_run: bool = False,
    yes: bool = False,
) -> RemoveReport:
    paths = AppPaths.build(project_root)
    registry = load_registry()
    pack_ids = list(dict.fromkeys(pack_ids or []))
    if all_:
        pack_ids = sorted(registry.packs)
        workflow = True
    if not pack_ids and not workflow:
        raise ConfigError("remove requires --pack, --workflow, or --all")
    unknown_packs = sorted(set(pack_ids) - set(registry.packs))
    if unknown_packs:
        raise ConfigError(f"unknown pack: {', '.join(unknown_packs)}")

    effective_dry_run = dry_run or not yes
    warnings: list[str] = []
    if not yes and not dry_run:
        warnings.append("No --yes supplied; remove is reported as a dry-run preview.")

    config_path = paths.project_root / ".planning" / "config.json"
    before = _read_json_object_strict(config_path)
    after = before
    for pack_id in pack_ids:
        after = remove_pack_agent_skills(after, registry, pack_id, preserve_shared=not all_)

    workflow_result = GsdWorkflowAdapter().remove(paths, dry_run=True) if workflow else None
    if workflow:
        warnings.append("Workflow removal is strategy-only in this phase; GSD Core files are not deleted.")
    if not config_path.exists():
        warnings.append("GSD config is not initialized; no config file will be removed or created.")

    backup_id = None
    operation_id = None
    if config_path.exists() and after != before and not effective_dry_run:
        backup = BackupSession(paths.backups_dir, paths.project_root)
        backup.record_before_change(config_path)
        write_json_atomic(config_path, after)
        backup_id = backup.finish()
        operation_id = _save_lifecycle_receipt(
            paths,
            operation="remove",
            workflow_status="pack-bindings-removed",
            packs=[{"pack_id": pack_id, "action": "remove-agent-bindings"} for pack_id in pack_ids],
            config_changes=[
                {
                    "path": str(config_path),
                    "action": "remove-pack-agent-bindings",
                    "before": before,
                    "after": after,
                }
            ],
            backup_id=backup_id,
        )

    return RemoveReport(
        project_root=paths.project_root,
        dry_run=effective_dry_run,
        applied=not effective_dry_run,
        packs=pack_ids,
        remove_workflow=workflow,
        remove_all=all_,
        config_path=config_path,
        before=before,
        after=after,
        workflow_result=workflow_result,
        warnings=warnings,
        backup_id=backup_id,
        operation_id=operation_id,
    )


def project_status(project_root: Path | None = None) -> dict[str, Any]:
    paths = AppPaths.build(project_root)
    detection = detect_project(paths.project_root)
    registry = load_registry()
    global_state = load_json(paths.global_state)
    project_state = load_json(paths.project_state)
    conflicts = sorted(
        str(path.relative_to(paths.project_root))
        for path in paths.project_root.rglob("*.ecc-upstream")
        if path.is_file()
    )
    modified_managed_files = [
        str(status.path)
        for status in [*managed_file_statuses(global_state), *managed_file_statuses(project_state)]
        if status.modified
    ]
    plan_audit = _plan_audit(paths, registry)
    source_lock = _source_lock_status(paths, registry)
    receipt = _latest_receipt_status(paths)
    runtime_status = _gsd_runtime_status(paths)
    packs = _pack_summary(project_state, plan_audit, registry)
    apply_readiness = _apply_readiness(
        conflicts=conflicts,
        modified_managed_files=modified_managed_files,
        plan_audit=plan_audit,
        source_lock_status=source_lock,
        receipt_status=receipt,
        workflow_status=runtime_status,
        project_state=project_state,
    )
    return {
        "project_root": str(paths.project_root),
        "detected_stacks": detection.stacks,
        "evidence": detection.evidence,
        "commands": detection.commands,
        "global_claude_md": paths.global_claude_md.exists(),
        "global_skills": sorted(
            path.parent.name for path in paths.global_skills.glob("*/SKILL.md") if path.is_file()
        )
        if paths.global_skills.exists()
        else [],
        "project_skills": sorted(
            path.parent.name for path in paths.project_skills.glob("*/SKILL.md") if path.is_file()
        )
        if paths.project_skills.exists()
        else [],
        "code_tour_completed": bool(project_state.get("code_tour_completed", False)),
        "upstream_ref": project_state.get("upstream_ref") or global_state.get("ecc_upstream_ref"),
        "last_initialized_at": project_state.get("last_initialized_at"),
        "conflicts": conflicts,
        "backup_count": len(list_backups(paths.backups_dir)),
        "modified_managed_files": modified_managed_files,
        "workflow": {
            "state": project_state.get("workflow") if isinstance(project_state.get("workflow"), dict) else {},
            "planned": plan_audit.get("workflow"),
            "runtime": runtime_status,
        },
        "packs": packs,
        "sources": {
            "locked": source_lock.get("sources", {}),
            "planned": plan_audit.get("sources", []),
            "unsupported_source_kinds": plan_audit.get("unsupported_source_kinds", []),
        },
        "source_lock": source_lock,
        "last_receipt": receipt,
        "apply_readiness": apply_readiness,
    }


@dataclass(frozen=True)
class DoctorCheck:
    check_id: str
    label: str
    ok: bool
    detail: str
    severity_if_failed: str = "fail"  # "fail" | "warn"


def doctor(project_root: Path | None = None, *, mode: str = "preflight") -> list[DoctorCheck]:
    """Run environment and project health checks.

    mode='preflight': suitable before first apply — missing Packs/Source Lock/Receipt are WARN not FAIL.
    mode='audit': suitable after apply — missing audit artifacts are FAIL.
    """
    paths = AppPaths.build(project_root)
    strict = mode == "audit"
    checks: list[DoctorCheck] = []

    def _add(check_id: str, label: str, ok: bool, detail: str, severity_if_failed: str = "fail") -> None:
        checks.append(DoctorCheck(check_id, label, ok, detail, severity_if_failed))

    _add("doctor:python", "Python 版本", sys.version_info >= (3, 10), sys.version.split()[0], "fail")
    _add("doctor:git", "Git 三方合并", shutil.which("git") is not None, shutil.which("git") or "未找到；冲突时将保留本地版本", "warn")

    for check_id, label, path in (
        ("doctor:ecc-home", "ecc-init 数据目录", paths.ecc_home),
        ("doctor:claude-home", "Claude 配置目录", paths.claude_home),
        ("doctor:project-root", "当前项目目录", paths.project_root),
    ):
        writable, detail = _writable_path_check(path)
        _add(check_id, label, writable, detail, "fail")

    manifest = read_manifest()
    _add("doctor:manifest", "内置清单", bool(manifest.get("global_skills") and manifest.get("project_skills")), "manifest.json", "fail")
    gsd_config = paths.project_root / ".planning" / "config.json"
    _add("doctor:gsd-config-bridge", "GSD config bridge", True, f"{gsd_config} ({'已初始化' if gsd_config.exists() else '未初始化'})", "warn")
    default_policy = POLICY_PROFILES["default"]
    _add("doctor:gsd-hard-config", "GSD hard-enforced config", True, "parallelization.*, workflow.use_worktrees, workflow.subagent_timeout, workflow.node_repair_budget", "warn")
    _add("doctor:gsd-advisory", "GSD advisory-only policy", True, ", ".join(sorted(default_policy.advisory)), "warn")
    status = project_status(paths.project_root)
    runtime = status["workflow"]["runtime"]
    runtime_command = ""
    if runtime.get("commands"):
        runtime_command = " | install preview: " + " ".join(runtime["commands"][0].get("args", []))
    gsd_runtime_ok = runtime.get("status") in {"installed_verified", "installed_unverified"}
    _add("doctor:gsd-runtime", "GSD runtime", gsd_runtime_ok if strict else True, f"{runtime.get('status', 'unknown')}{runtime_command}", "warn")
    packs = status["packs"]
    installed_packs = packs["installed"]
    has_packs = bool(installed_packs)
    _add("doctor:installed-packs", "Installed Packs", has_packs if strict else True, _installed_packs_summary(installed_packs), "warn")
    source_lock = status["source_lock"]
    source_lock_ok = source_lock["status"] == "present" and source_lock["valid"]
    _add("doctor:source-lock", "Project source lock", source_lock_ok if strict else True, f"{source_lock['status']} ({source_lock['source_count']} source(s)) at {source_lock['path']}", "warn")
    receipt = status["last_receipt"]
    receipt_ok = receipt["status"] == "present" and receipt["valid"]
    _add("doctor:receipt", "Latest apply receipt", receipt_ok if strict else True, f"{receipt['status']} ({receipt.get('operation_id') or 'none'})", "warn")
    readiness = status["apply_readiness"]
    _add("doctor:apply-readiness", "Apply readiness", readiness["ready"], readiness["status"] if readiness["ready"] else "; ".join(readiness["blockers"]), "fail")
    plan_consistency = readiness["plan_consistency"]
    _add("doctor:plan-consistency", "Plan/apply consistency", plan_consistency["status"] in {"matches", "not_applied"}, plan_consistency["status"], "warn")
    for label, ok, detail in frontend_doctor_checks(paths.project_root):
        check_id = "doctor:frontend-" + label.lower().replace(" ", "-")
        _add(check_id, label, ok, detail, "warn")
    return checks


def _installed_packs_summary(installed: dict[str, Any]) -> str:
    if not installed:
        return "none installed for this project"
    lines: list[str] = []
    for pack_id, info in sorted(installed.items()):
        if isinstance(info, dict):
            status = info.get("status", "unknown")
            lines.append(f"{pack_id}: {status}")
        else:
            lines.append(pack_id)
    return ", ".join(lines)
    """Run environment and project health checks.

    mode='preflight': suitable before first apply — missing Packs/Source Lock/Receipt are WARN not FAIL.
    mode='audit': suitable after apply — missing audit artifacts are FAIL.
    """
    paths = AppPaths.build(project_root)
    strict = mode == "audit"
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python 版本", sys.version_info >= (3, 10), sys.version.split()[0]))
    checks.append(("Git 三方合并", shutil.which("git") is not None, shutil.which("git") or "未找到；冲突时将保留本地版本"))

    for label, path in (
        ("ecc-init 数据目录", paths.ecc_home),
        ("Claude 配置目录", paths.claude_home),
        ("当前项目目录", paths.project_root),
    ):
        writable, detail = _writable_path_check(path)
        checks.append((label, writable, detail))

    manifest = read_manifest()
    checks.append(("内置清单", bool(manifest.get("global_skills") and manifest.get("project_skills")), "manifest.json"))
    gsd_config = paths.project_root / ".planning" / "config.json"
    checks.append(("GSD config bridge", True, f"{gsd_config} ({'已初始化' if gsd_config.exists() else '未初始化'})"))
    default_policy = POLICY_PROFILES["default"]
    checks.append(
        (
            "GSD hard-enforced config",
            True,
            "parallelization.*, workflow.use_worktrees, workflow.subagent_timeout, workflow.node_repair_budget",
        )
    )
    checks.append(("GSD advisory-only policy", True, ", ".join(sorted(default_policy.advisory))))
    status = project_status(paths.project_root)
    runtime = status["workflow"]["runtime"]
    runtime_command = ""
    if runtime.get("commands"):
        runtime_command = " | install preview: " + " ".join(runtime["commands"][0].get("args", []))
    gsd_runtime_ok = runtime.get("status") in {"installed_verified", "installed_unverified"}
    checks.append(
        (
            "GSD runtime",
            gsd_runtime_ok if strict else True,
            f"{runtime.get('status', 'unknown')}{runtime_command}",
        )
    )
    packs = status["packs"]
    installed_packs = sorted(packs["installed"])
    has_packs = bool(installed_packs)
    checks.append(
        (
            "Installed Packs",
            has_packs if strict else True,
            ", ".join(installed_packs) or "none installed for this project",
        )
    )
    source_lock = status["source_lock"]
    source_lock_ok = source_lock["status"] == "present" and source_lock["valid"]
    checks.append(
        (
            "Project source lock",
            source_lock_ok if strict else True,
            f"{source_lock['status']} ({source_lock['source_count']} source(s)) at {source_lock['path']}",
        )
    )
    receipt = status["last_receipt"]
    receipt_ok = receipt["status"] == "present" and receipt["valid"]
    checks.append(
        (
            "Latest apply receipt",
            receipt_ok if strict else True,
            f"{receipt['status']} ({receipt.get('operation_id') or 'none'})",
        )
    )
    readiness = status["apply_readiness"]
    checks.append(
        (
            "Apply readiness",
            readiness["ready"],
            readiness["status"] if readiness["ready"] else "; ".join(readiness["blockers"]),
        )
    )
    plan_consistency = readiness["plan_consistency"]
    checks.append(
        (
            "Plan/apply consistency",
            plan_consistency["status"] in {"matches", "not_applied"},
            plan_consistency["status"],
        )
    )
    checks.extend(frontend_doctor_checks(paths.project_root))
    return checks


def rollback(
    project_root: Path | None = None,
    backup_id: str | None = None,
    operation_id: str | None = None,
    receipt_path: Path | None = None,
) -> tuple[str, int]:
    paths = AppPaths.build(project_root)
    selectors = [bool(backup_id), bool(operation_id), bool(receipt_path)]
    if sum(selectors) > 1:
        raise ConfigError("rollback 只能同时指定 backup、operation 或 receipt 之一")
    if operation_id:
        receipt = ReceiptStore(paths.operations_dir).load(operation_id)
        if not receipt.backup_id:
            raise ConfigError(f"operation {operation_id} 没有可回滚的 backup")
        backup_id = receipt.backup_id
    elif receipt_path:
        receipt = ReceiptStore(paths.operations_dir).load_path(receipt_path)
        if not receipt.backup_id:
            raise ConfigError(f"receipt {receipt_path} 没有可回滚的 backup")
        backup_id = receipt.backup_id
    return rollback_backup(paths.backups_dir, backup_id)
