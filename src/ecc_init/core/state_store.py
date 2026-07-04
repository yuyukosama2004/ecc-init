from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..errors import ConfigError
from ..util import write_json_atomic


class StateStore:
    """Small atomic JSON object store for v2 state files."""

    def __init__(self, path: Path):
        self.path = path

    def load(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        fallback = {} if default is None else deepcopy(default)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return fallback
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"无法读取状态文件 {self.path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"状态文件必须是 JSON object: {self.path}")
        return data

    def save(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ConfigError("StateStore.save 只接受 dict")
        write_json_atomic(self.path, data)

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        data.update(values)
        self.save(data)
        return data
