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
from .sources import verify_registry_sources
from .sync import fetch_upstream_skill, resolve_stable_ref
from .util import human_bool, load_json, now_iso, read_text, sha256_text, write_json_atomic, write_text_atomic
from .workflows import GsdWorkflowAdapter


GLOBAL_START = "<!-- ecc-init:start global -->"
GLOBAL_END = "<!-- ecc-init:end global -->"
PROJECT_START = "<!-- ecc-init:start project -->"
PROJECT_END = "<!-- ecc-init:end project -->"


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
    global_state = load_json(paths.global_state)
    project_state = load_json(paths.project_state)
    conflicts = sorted(
        str(path.relative_to(paths.project_root))
        for path in paths.project_root.rglob("*.ecc-upstream")
        if path.is_file()
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
        "modified_managed_files": [
            str(status.path)
            for status in [*managed_file_statuses(global_state), *managed_file_statuses(project_state)]
            if status.modified
        ],
    }


def doctor(project_root: Path | None = None) -> list[tuple[str, bool, str]]:
    paths = AppPaths.build(project_root)
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python 版本", sys.version_info >= (3, 10), sys.version.split()[0]))
    checks.append(("Git 三方合并", shutil.which("git") is not None, shutil.which("git") or "未找到；冲突时将保留本地版本"))

    for label, path in (
        ("ecc-init 数据目录", paths.ecc_home),
        ("Claude 配置目录", paths.claude_home),
        ("当前项目目录", paths.project_root),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
            writable = os.access(path, os.W_OK)
        except OSError:
            writable = False
        checks.append((label, writable, str(path)))

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
