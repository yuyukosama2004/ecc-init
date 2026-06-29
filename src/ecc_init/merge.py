from __future__ import annotations

import difflib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .backup import BackupSession
from .util import path_key, read_text, sha256_text, write_text_atomic


MergeStatus = Literal["created", "updated", "unchanged", "conflict", "preserved"]


@dataclass(frozen=True)
class InstallResult:
    path: Path
    status: MergeStatus
    message: str = ""


def _run_git_merge(local: str, base: str, incoming: str) -> tuple[bool, str]:
    git = shutil.which("git")
    if not git:
        return False, ""
    with tempfile.TemporaryDirectory(prefix="ecc-init-merge-") as temp_dir:
        root = Path(temp_dir)
        local_path = root / "local"
        base_path = root / "base"
        incoming_path = root / "incoming"
        local_path.write_text(local, encoding="utf-8")
        base_path.write_text(base, encoding="utf-8")
        incoming_path.write_text(incoming, encoding="utf-8")
        process = subprocess.run(
            [git, "merge-file", "-p", str(local_path), str(base_path), str(incoming_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if process.returncode == 0 and "<<<<<<<" not in process.stdout:
            return True, process.stdout
        return False, process.stdout


def _write_conflict_artifacts(target: Path, local: str, incoming: str, backup: BackupSession) -> None:
    upstream = target.with_name(target.name + ".ecc-upstream")
    diff_path = target.with_name(target.name + ".ecc-diff")
    diff_text = "".join(
        difflib.unified_diff(
            local.splitlines(keepends=True),
            incoming.splitlines(keepends=True),
            fromfile=str(target),
            tofile=str(upstream),
        )
    )
    for path, content in ((upstream, incoming), (diff_path, diff_text)):
        backup.record_before_change(path)
        write_text_atomic(path, content)


def _base_path(bases_root: Path, target: Path, content: str) -> Path:
    # 基线文件按内容哈希保存且不可变。这样回滚旧 state 后，旧基线仍然存在。
    return bases_root / path_key(target) / f"{sha256_text(content)}.txt"


def _record_base(bases_root: Path, target: Path, content: str) -> Path:
    path = _base_path(bases_root, target, content)
    if not path.exists():
        write_text_atomic(path, content)
    return path


def _state_record(state: dict[str, Any], target: Path) -> dict[str, Any] | None:
    records = state.setdefault("managed_files", {})
    record = records.get(str(target.resolve()))
    return record if isinstance(record, dict) else None


def _save_record(
    state: dict[str, Any],
    target: Path,
    source_id: str,
    base_path: Path,
    base_content: str,
    kind: str,
) -> None:
    state.setdefault("managed_files", {})[str(target.resolve())] = {
        "source_id": source_id,
        "kind": kind,
        "base_path": str(base_path),
        "base_hash": sha256_text(base_content),
    }


def _replace_managed_section(base_document: str, new_section: str, start: str, end: str) -> str:
    start_index = base_document.find(start)
    end_index = base_document.find(end)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        separator = "" if not base_document.strip() else "\n\n"
        return base_document.rstrip() + separator + new_section.strip() + "\n"
    end_index += len(end)
    prefix = base_document[:start_index]
    suffix = base_document[end_index:]
    return prefix + new_section.strip() + suffix


def install_managed_section(
    *,
    target: Path,
    section: str,
    source_id: str,
    start_marker: str,
    end_marker: str,
    state: dict[str, Any],
    bases_root: Path,
    backup: BackupSession,
) -> InstallResult:
    local = read_text(target)
    record = _state_record(state, target)

    if not target.exists():
        backup.record_before_change(target)
        content = section.strip() + "\n"
        write_text_atomic(target, content)
        base_path = _record_base(bases_root, target, content)
        _save_record(state, target, source_id, base_path, content, "managed-section")
        return InstallResult(target, "created")

    if record is None:
        expected = _replace_managed_section(local, section, start_marker, end_marker)
        if expected == local:
            base_path = _record_base(bases_root, target, local)
            _save_record(state, target, source_id, base_path, local, "managed-section")
            return InstallResult(target, "unchanged")
        backup.record_before_change(target)
        write_text_atomic(target, expected)
        base_path = _record_base(bases_root, target, expected)
        _save_record(state, target, source_id, base_path, expected, "managed-section")
        return InstallResult(target, "updated", "已保留原内容并追加 ecc-init 管理区域")

    base_path = Path(record.get("base_path", ""))
    base = read_text(base_path)
    if not base:
        expected = _replace_managed_section(local, section, start_marker, end_marker)
        if expected == local:
            return InstallResult(target, "unchanged")
        backup.record_before_change(target)
        write_text_atomic(target, expected)
        stored = _record_base(bases_root, target, expected)
        _save_record(state, target, source_id, stored, expected, "managed-section")
        return InstallResult(target, "updated")

    incoming = _replace_managed_section(base, section, start_marker, end_marker)
    return _merge_install(
        target=target,
        local=local,
        base=base,
        incoming=incoming,
        source_id=source_id,
        kind="managed-section",
        state=state,
        bases_root=bases_root,
        backup=backup,
    )


def install_whole_file(
    *,
    target: Path,
    incoming: str,
    source_id: str,
    state: dict[str, Any],
    bases_root: Path,
    backup: BackupSession,
) -> InstallResult:
    local = read_text(target)
    record = _state_record(state, target)
    if not target.exists():
        backup.record_before_change(target)
        write_text_atomic(target, incoming)
        base_path = _record_base(bases_root, target, incoming)
        _save_record(state, target, source_id, base_path, incoming, "whole-file")
        return InstallResult(target, "created")

    if record is None:
        if local == incoming:
            base_path = _record_base(bases_root, target, incoming)
            _save_record(state, target, source_id, base_path, incoming, "whole-file")
            return InstallResult(target, "unchanged")
        _write_conflict_artifacts(target, local, incoming, backup)
        return InstallResult(target, "preserved", "文件已存在且不受 ecc-init 管理；保留本地版本并生成对比文件")

    base_path = Path(record.get("base_path", ""))
    base = read_text(base_path)
    if not base:
        _write_conflict_artifacts(target, local, incoming, backup)
        return InstallResult(target, "conflict", "缺少历史基线，已保留本地版本")

    return _merge_install(
        target=target,
        local=local,
        base=base,
        incoming=incoming,
        source_id=source_id,
        kind="whole-file",
        state=state,
        bases_root=bases_root,
        backup=backup,
    )


def _merge_install(
    *,
    target: Path,
    local: str,
    base: str,
    incoming: str,
    source_id: str,
    kind: str,
    state: dict[str, Any],
    bases_root: Path,
    backup: BackupSession,
) -> InstallResult:
    if local == incoming:
        stored = _record_base(bases_root, target, incoming)
        _save_record(state, target, source_id, stored, incoming, kind)
        return InstallResult(target, "unchanged")
    if incoming == base:
        return InstallResult(target, "unchanged")
    if local == base:
        backup.record_before_change(target)
        write_text_atomic(target, incoming)
        stored = _record_base(bases_root, target, incoming)
        _save_record(state, target, source_id, stored, incoming, kind)
        return InstallResult(target, "updated")

    merged, content = _run_git_merge(local, base, incoming)
    if merged:
        backup.record_before_change(target)
        write_text_atomic(target, content)
        stored = _record_base(bases_root, target, incoming)
        _save_record(state, target, source_id, stored, incoming, kind)
        return InstallResult(target, "updated", "已自动三方合并本地修改与新版模板")

    _write_conflict_artifacts(target, local, incoming, backup)
    return InstallResult(target, "conflict", "自动合并冲突：保留本地版本，并生成 .ecc-upstream 与 .ecc-diff")
