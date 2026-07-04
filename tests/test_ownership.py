from pathlib import Path

from ecc_init.core.ownership import add_owner, managed_file_statuses
from ecc_init.util import sha256_text


def test_add_owner_deduplicates_and_sorts() -> None:
    record = {"owners": ["pack:b"]}

    add_owner(record, "pack:a")
    add_owner(record, "pack:b")

    assert record["owners"] == ["pack:a", "pack:b"]


def test_managed_file_status_detects_modified_file(tmp_path: Path) -> None:
    target = tmp_path / "SKILL.md"
    target.write_text("base\n", encoding="utf-8")
    state = {
        "managed_files": {
            str(target): {
                "source_id": "skill:test",
                "base_hash": sha256_text("base\n"),
                "owners": ["pack:test"],
            }
        }
    }

    clean = managed_file_statuses(state)[0]
    target.write_text("changed\n", encoding="utf-8")
    dirty = managed_file_statuses(state)[0]

    assert clean.modified is False
    assert clean.owner == "pack:test"
    assert dirty.modified is True
