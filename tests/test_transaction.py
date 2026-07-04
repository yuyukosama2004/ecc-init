from pathlib import Path

from ecc_init.core.receipt import ReceiptStore
from ecc_init.core.transaction import Transaction


def test_transaction_rolls_back_new_modified_and_deleted_files(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    deleted = tmp_path / "deleted.txt"
    created = tmp_path / "created.txt"
    existing.write_text("before\n", encoding="utf-8")
    deleted.write_text("keep\n", encoding="utf-8")
    transaction = Transaction(tmp_path / "backups", tmp_path)

    transaction.write_text(existing, "after\n", owner="test")
    transaction.write_text(created, "new\n", owner="test")
    transaction.delete_file(deleted, owner="test")
    report = transaction.rollback()

    assert report.partial is False
    assert report.restored == 3
    assert existing.read_text(encoding="utf-8") == "before\n"
    assert deleted.read_text(encoding="utf-8") == "keep\n"
    assert not created.exists()


def test_transaction_rollback_skips_concurrent_user_edit(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("before\n", encoding="utf-8")
    transaction = Transaction(tmp_path / "backups", tmp_path)

    transaction.write_text(existing, "after\n", owner="test")
    existing.write_text("user edit\n", encoding="utf-8")
    report = transaction.rollback()

    assert report.partial is True
    assert report.restored == 0
    assert report.skipped == 1
    assert existing.read_text(encoding="utf-8") == "user edit\n"


def test_transaction_receipt_records_files_and_config(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path / "operations")
    transaction = Transaction(tmp_path / "backups", tmp_path, receipt_store=store, workflow_id="test-workflow")
    target = tmp_path / "file.txt"

    transaction.write_text(target, "content\n", owner="pack:test")
    transaction.record_config(tmp_path / "config.json", "merge", {"a": 1}, {"a": 2})
    receipt = transaction.finish()
    loaded = store.load(receipt.operation_id)

    assert loaded.backup_id == receipt.backup_id
    assert loaded.workflow == {"id": "test-workflow", "status": "success"}
    assert loaded.files[0]["owner"] == "pack:test"
    assert loaded.config_changes[0]["action"] == "merge"
