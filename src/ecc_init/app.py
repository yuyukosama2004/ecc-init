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
from .detect import DetectionResult, detect_project
from .merge import InstallResult, install_managed_section, install_whole_file
from .paths import AppPaths
from .project import render_project_overview, render_project_section, structure_fingerprint
from .resources import read_manifest, read_resource_text
from .sync import fetch_upstream_skill, resolve_stable_ref
from .util import human_bool, load_json, now_iso, read_text, write_json_atomic, write_text_atomic


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
    return report


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
    return checks


def rollback(project_root: Path | None = None, backup_id: str | None = None) -> tuple[str, int]:
    paths = AppPaths.build(project_root)
    return rollback_backup(paths.backups_dir, backup_id)
