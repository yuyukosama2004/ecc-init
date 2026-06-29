from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .util import timestamp_id, write_json_atomic


class BackupSession:
    """记录一次 ecc-init 运行中被修改或新建的文件，以支持回滚。"""

    def __init__(self, backups_root: Path, project_root: Path):
        self.backups_root = backups_root
        self.project_root = project_root
        self.backup_id = timestamp_id()
        self.root = backups_root / self.backup_id
        self.entries: list[dict[str, Any]] = []
        self._recorded: set[str] = set()

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def record_before_change(self, path: Path) -> None:
        key = str(path.resolve())
        if key in self._recorded:
            return
        self._recorded.add(key)
        self._ensure_root()
        if path.exists():
            index = len(self.entries)
            backup_path = self.root / "files" / str(index) / path.name
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
            self.entries.append(
                {
                    "path": key,
                    "action": "restore",
                    "backup": str(backup_path.relative_to(self.root)),
                }
            )
        else:
            self.entries.append({"path": key, "action": "delete-created"})

    def finish(self) -> str | None:
        if not self.entries:
            return None
        manifest = {
            "backup_id": self.backup_id,
            "project_root": str(self.project_root),
            "entries": self.entries,
        }
        write_json_atomic(self.root / "manifest.json", manifest)
        return self.backup_id


def list_backups(backups_root: Path) -> list[Path]:
    if not backups_root.exists():
        return []
    candidates = [path for path in backups_root.iterdir() if path.is_dir() and (path / "manifest.json").exists()]
    return sorted(candidates, key=lambda path: path.name, reverse=True)


def rollback_backup(backups_root: Path, backup_id: str | None = None) -> tuple[str, int]:
    if backup_id:
        selected = backups_root / backup_id
        if not (selected / "manifest.json").exists():
            raise FileNotFoundError(f"未找到备份：{backup_id}")
    else:
        backups = list_backups(backups_root)
        if not backups:
            raise FileNotFoundError("没有可用备份")
        selected = backups[0]

    manifest = json.loads((selected / "manifest.json").read_text(encoding="utf-8"))
    restored = 0
    for entry in reversed(manifest.get("entries", [])):
        target = Path(entry["path"])
        action = entry.get("action")
        if action == "restore":
            source = selected / entry["backup"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            restored += 1
        elif action == "delete-created":
            if target.is_file() or target.is_symlink():
                target.unlink(missing_ok=True)
                restored += 1
            elif target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                restored += 1
    return selected.name, restored
