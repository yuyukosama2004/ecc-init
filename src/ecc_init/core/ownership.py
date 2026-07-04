from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..util import read_text, sha256_text


@dataclass(frozen=True)
class ManagedFileStatus:
    path: Path
    owner: str
    source_id: str
    exists: bool
    modified: bool
    current_hash: str | None
    expected_hash: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "owner": self.owner,
            "source_id": self.source_id,
            "exists": self.exists,
            "modified": self.modified,
            "current_hash": self.current_hash,
            "expected_hash": self.expected_hash,
        }


def add_owner(record: dict[str, Any], owner: str) -> dict[str, Any]:
    owners = [str(item) for item in record.get("owners", []) if str(item)]
    if owner not in owners:
        owners.append(owner)
    record["owners"] = sorted(owners)
    return record


def _current_hash(path: Path) -> str | None:
    content = read_text(path)
    if content == "" and not path.exists():
        return None
    return sha256_text(content)


def managed_file_statuses(state: dict[str, Any]) -> list[ManagedFileStatus]:
    records = state.get("managed_files", {})
    if not isinstance(records, dict):
        return []
    statuses: list[ManagedFileStatus] = []
    for raw_path, raw_record in sorted(records.items()):
        if not isinstance(raw_record, dict):
            continue
        path = Path(raw_path)
        expected = raw_record.get("base_hash")
        current = _current_hash(path)
        source_id = str(raw_record.get("source_id") or "")
        owners = raw_record.get("owners")
        owner = ", ".join(str(item) for item in owners) if isinstance(owners, list) and owners else source_id
        statuses.append(
            ManagedFileStatus(
                path=path,
                owner=owner,
                source_id=source_id,
                exists=path.exists(),
                modified=current != expected,
                current_hash=current,
                expected_hash=str(expected) if expected else None,
            )
        )
    return statuses
