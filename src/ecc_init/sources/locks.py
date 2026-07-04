from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pathlib import Path

from ..errors import ConfigError
from ..util import write_json_atomic


@dataclass(frozen=True)
class SourceLock:
    source_id: str
    repository: str | None
    resolved_ref: str
    integrity: str
    source_path: str | None
    license_id: str | None
    license_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "repository": self.repository,
            "resolved_ref": self.resolved_ref,
            "integrity": self.integrity,
            "source_path": self.source_path,
            "license_id": self.license_id,
            "license_path": self.license_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceLock":
        return cls(
            source_id=str(data["source_id"]),
            repository=data.get("repository"),
            resolved_ref=str(data["resolved_ref"]),
            integrity=str(data["integrity"]),
            source_path=data.get("source_path"),
            license_id=data.get("license_id"),
            license_path=data.get("license_path"),
        )


class SourceLockStore:
    def __init__(self, path: Path):
        self.path = path

    def load_all(self) -> dict[str, SourceLock]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"无法读取 source lock {self.path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ConfigError(f"source lock 必须是 JSON object: {self.path}")
        sources = payload.get("sources", {})
        if not isinstance(sources, dict):
            raise ConfigError(f"source lock sources 必须是 JSON object: {self.path}")
        return {source_id: SourceLock.from_dict(item) for source_id, item in sources.items()}

    def save_all(self, locks: dict[str, SourceLock]) -> None:
        payload = {
            "schema_version": 1,
            "sources": {source_id: lock.to_dict() for source_id, lock in sorted(locks.items())},
        }
        write_json_atomic(self.path, payload)

    def save(self, lock: SourceLock) -> None:
        locks = self.load_all()
        locks[lock.source_id] = lock
        self.save_all(locks)
