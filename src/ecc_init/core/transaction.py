from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..backup import BackupSession
from ..util import now_iso, read_text, sha256_text, write_text_atomic
from .models import Receipt
from .plan import new_operation_id
from .receipt import ReceiptStore


@dataclass(frozen=True)
class FileJournalEntry:
    path: Path
    action: str
    owner: str
    before_hash: str | None
    expected_hash: str | None


@dataclass(frozen=True)
class ConfigJournalEntry:
    path: Path
    action: str
    before: dict[str, Any]
    after: dict[str, Any]


@dataclass(frozen=True)
class RollbackReport:
    backup_id: str | None
    restored: int = 0
    skipped: int = 0
    skipped_paths: tuple[str, ...] = ()

    @property
    def partial(self) -> bool:
        return self.skipped > 0


@dataclass
class Transaction:
    backups_root: Path
    project_root: Path
    receipt_store: ReceiptStore | None = None
    workflow_id: str = "transaction"
    operation_id: str = field(default_factory=new_operation_id)

    def __post_init__(self) -> None:
        self.backup = BackupSession(self.backups_root, self.project_root)
        self.file_journal: list[FileJournalEntry] = []
        self.config_journal: list[ConfigJournalEntry] = []
        self._journal_by_path: dict[str, FileJournalEntry] = {}
        self._finished_backup_id: str | None = None

    def _hash(self, path: Path) -> str | None:
        content = read_text(path)
        if content == "" and not path.exists():
            return None
        return sha256_text(content)

    def _remember_file(
        self,
        path: Path,
        action: str,
        owner: str,
        before_hash: str | None,
        expected_hash: str | None,
    ) -> None:
        key = str(path.resolve())
        if key in self._journal_by_path:
            entry = self._journal_by_path[key]
            updated = FileJournalEntry(
                path=entry.path,
                action=action,
                owner=owner,
                before_hash=entry.before_hash,
                expected_hash=expected_hash,
            )
            self._journal_by_path[key] = updated
            self.file_journal = [updated if str(item.path.resolve()) == key else item for item in self.file_journal]
            return
        entry = FileJournalEntry(
            path=path,
            action=action,
            owner=owner,
            before_hash=before_hash,
            expected_hash=expected_hash,
        )
        self._journal_by_path[key] = entry
        self.file_journal.append(entry)

    def write_text(self, path: Path, content: str, *, owner: str) -> None:
        before_hash = self._hash(path)
        self.backup.record_before_change(path)
        write_text_atomic(path, content)
        self._remember_file(path, "write", owner, before_hash, sha256_text(content))

    def delete_file(self, path: Path, *, owner: str) -> None:
        before_hash = self._hash(path)
        self.backup.record_before_change(path)
        if path.exists():
            path.unlink()
        self._remember_file(path, "delete", owner, before_hash, None)

    def record_config(self, path: Path, action: str, before: dict[str, Any], after: dict[str, Any]) -> None:
        self.config_journal.append(ConfigJournalEntry(path=path, action=action, before=before, after=after))

    def finish(
        self,
        *,
        result: str = "success",
        packs: list[dict[str, Any]] | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> Receipt:
        backup_id = self._finished_backup_id or self.backup.finish()
        self._finished_backup_id = backup_id
        receipt = Receipt(
            operation_id=self.operation_id,
            created_at=now_iso(),
            project_root=self.project_root.resolve(),
            workflow={"id": self.workflow_id, "status": result},
            packs=packs or [],
            sources=sources or [],
            files=[
                {
                    "path": str(entry.path),
                    "owner": entry.owner,
                    "sha256": entry.expected_hash,
                    "previous_sha256": entry.before_hash,
                    "action": entry.action,
                }
                for entry in self.file_journal
            ],
            config_changes=[
                {
                    "path": str(entry.path),
                    "action": entry.action,
                    "before": entry.before,
                    "after": entry.after,
                }
                for entry in self.config_journal
            ],
            backup_id=backup_id,
            result=result,
        )
        if self.receipt_store is not None:
            self.receipt_store.save(receipt)
        return receipt

    def rollback(self) -> RollbackReport:
        backup_id = self._finished_backup_id or self.backup.finish()
        self._finished_backup_id = backup_id
        if not backup_id:
            return RollbackReport(backup_id=None)

        manifest_path = self.backups_root / backup_id / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        restored = 0
        skipped_paths: list[str] = []
        for entry in reversed(manifest.get("entries", [])):
            target = Path(entry["path"])
            journal = self._journal_by_path.get(str(target.resolve()))
            expected_hash = journal.expected_hash if journal else self._hash(target)
            if self._hash(target) != expected_hash:
                skipped_paths.append(str(target))
                continue
            action = entry.get("action")
            if action == "restore":
                source = self.backups_root / backup_id / entry["backup"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                restored += 1
            elif action == "delete-created":
                if target.is_file() or target.is_symlink():
                    target.unlink(missing_ok=True)
                    restored += 1
        report = RollbackReport(
            backup_id=backup_id,
            restored=restored,
            skipped=len(skipped_paths),
            skipped_paths=tuple(skipped_paths),
        )
        self.finish(result="partial_rollback" if report.partial else "rolled_back")
        return report
