import json
from pathlib import Path

import pytest

from ecc_init.core.state_store import StateStore
from ecc_init.errors import ConfigError


def test_state_store_saves_atomically_loads_json_object(tmp_path: Path) -> None:
    path = tmp_path / ".claude" / "ecc-init-state.json"
    store = StateStore(path)

    store.save({"schema_version": 2, "value": "ok"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"schema_version": 2, "value": "ok"}
    assert store.load()["value"] == "ok"
    assert list(path.parent.glob(f".{path.name}.*")) == []


def test_state_store_reports_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{bad", encoding="utf-8")

    with pytest.raises(ConfigError, match="无法读取状态文件"):
        StateStore(path).load()
