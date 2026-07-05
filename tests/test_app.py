import json
from pathlib import Path

from ecc_init.app import doctor, initialize_project, project_status, rollback
from ecc_init.core.receipt import ReceiptStore


def test_initialize_offline_creates_global_and_project_files(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi", "langgraph"]\n',
        encoding="utf-8",
    )
    existing = "# 原有项目说明\n\n这部分必须保留。\n"
    (project / "CLAUDE.md").write_text(existing, encoding="utf-8")

    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = initialize_project(project, offline=True)

    assert "fastapi" in report.detection.stacks
    assert (tmp_path / "claude-home" / "CLAUDE.md").exists()
    assert (tmp_path / "claude-home" / "skills" / "task-planning" / "SKILL.md").exists()
    assert (project / ".claude" / "skills" / "fastapi-patterns" / "SKILL.md").exists()
    assert (project / ".claude" / "skills" / "langgraph-patterns" / "SKILL.md").exists()
    assert (project / "docs" / "DEVELOPMENT_LOG.md").exists()
    assert "这部分必须保留" in (project / "CLAUDE.md").read_text(encoding="utf-8")

    state = json.loads((project / ".claude" / "ecc-init-state.json").read_text(encoding="utf-8"))
    assert state["code_tour_completed"] is False
    assert state["detected_stacks"] == ["python", "fastapi", "langgraph"]

    status = project_status(project)
    assert "fastapi-patterns" in status["project_skills"]
    assert status["modified_managed_files"] == []


def test_rollback_restores_latest_backup(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = initialize_project(project, offline=True)
    assert report.backup_id
    assert (project / "docs" / "DEVELOPMENT_LOG.md").exists()

    backup_id, restored = rollback(project)

    assert backup_id == report.backup_id
    assert restored > 0
    assert not (project / "docs" / "DEVELOPMENT_LOG.md").exists()


def test_rollback_can_use_operation_receipt(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = initialize_project(project, offline=True)
    receipts = list((tmp_path / "ecc-home" / "operations").glob("*/receipt.json"))
    assert report.backup_id
    assert len(receipts) == 1
    operation_id = receipts[0].parent.name
    receipt = ReceiptStore(tmp_path / "ecc-home" / "operations").load(operation_id)
    assert receipt.backup_id == report.backup_id

    backup_id, restored = rollback(project, operation_id=operation_id)

    assert backup_id == report.backup_id
    assert restored > 0
    assert not (project / "docs" / "DEVELOPMENT_LOG.md").exists()


def test_status_reports_modified_managed_files(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    initialize_project(project, offline=True)

    claude_md = project / "CLAUDE.md"
    claude_md.write_text(claude_md.read_text(encoding="utf-8") + "\n# local edit\n", encoding="utf-8")

    status = project_status(project)

    assert str(claude_md.resolve()) in status["modified_managed_files"]


def test_doctor_reports_resources_and_paths(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    checks = doctor(project)

    by_label = {check.label: (check.ok, check.detail) for check in checks}
    assert by_label["当前项目目录"][0] is True
    assert by_label["内置清单"] == (True, "manifest.json")
