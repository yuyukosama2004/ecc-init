from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import ConfigError
from ..util import now_iso, write_text_atomic
from .models import Receipt
from .plan import new_operation_id


def create_receipt(
    *,
    project_root: Path,
    workflow: dict[str, Any],
    result: str = "success",
    backup_id: str | None = None,
) -> Receipt:
    return Receipt(
        operation_id=new_operation_id(),
        created_at=now_iso(),
        project_root=project_root.resolve(),
        workflow=workflow,
        backup_id=backup_id,
        result=result,
    )


class ReceiptStore:
    def __init__(self, root: Path):
        self.root = root

    def receipt_path(self, operation_id: str) -> Path:
        return self.root / operation_id / "receipt.json"

    def save(self, receipt: Receipt) -> Path:
        path = self.receipt_path(receipt.operation_id)
        write_text_atomic(path, json.dumps(receipt.to_dict(), ensure_ascii=False, indent=2) + "\n")
        return path

    def load(self, operation_id: str) -> Receipt:
        path = self.receipt_path(operation_id)
        if not path.exists():
            raise ConfigError(f"未找到 operation receipt: {operation_id}")
        return self.load_path(path)

    def load_path(self, path: Path) -> Receipt:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"无法读取 receipt {path}: {exc}") from exc
        return Receipt.from_dict(payload)

    def latest(self) -> Receipt:
        receipts = sorted(self.root.glob("*/receipt.json"), key=lambda path: path.parent.name, reverse=True)
        if not receipts:
            raise ConfigError("没有可用 operation receipt")
        return self.load_path(receipts[0])
