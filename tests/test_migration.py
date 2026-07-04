import json
from pathlib import Path

from ecc_init.app import initialize_project, rollback
from ecc_init.cli import _normalize_argv, main
from ecc_init.migration import detect_legacy_v1, migrate_legacy_v1
from ecc_init.migration.legacy_v1 import (
    DEPRECATED_WORKFLOW_SKILLS,
    GLOBAL_START,
    PROJECT_START,
)


def _prepare_legacy_v1(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path]:
    project = tmp_path / "demo"
    project.mkdir()
    ecc_home = tmp_path / "ecc-home"
    claude_home = tmp_path / "claude-home"
    monkeypatch.setenv("ECC_INIT_HOME", str(ecc_home))
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    initialize_project(project, offline=True)
    return project, ecc_home, claude_home


def test_init_warns_about_legacy_migration(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = initialize_project(project, offline=True)

    assert any("ecc-init migrate --dry-run" in warning for warning in report.warnings)


def test_migrate_dry_run_does_not_write_files(tmp_path: Path, monkeypatch) -> None:
    project, _, claude_home = _prepare_legacy_v1(tmp_path, monkeypatch)
    project_state = project / ".claude" / "ecc-init-state.json"
    before_state = project_state.read_text(encoding="utf-8")

    report = migrate_legacy_v1(project, dry_run=True)

    assert report.detected is True
    assert report.applied is False
    assert any(action.action == "write-state-v2" for action in report.actions)
    assert project_state.read_text(encoding="utf-8") == before_state
    assert (claude_home / "skills" / "task-planning" / "SKILL.md").exists()
    assert not (project / "docs" / "ecc-init-migration-report.md").exists()


def test_migrate_clean_v1_removes_legacy_workflow_and_writes_state_v2(tmp_path: Path, monkeypatch) -> None:
    project, ecc_home, claude_home = _prepare_legacy_v1(tmp_path, monkeypatch)

    report = migrate_legacy_v1(project)

    assert report.applied is True
    assert report.backup_id
    assert report.operation_id
    for skill in DEPRECATED_WORKFLOW_SKILLS:
        assert not (claude_home / "skills" / skill).exists()
    assert GLOBAL_START not in (claude_home / "CLAUDE.md").read_text(encoding="utf-8")
    assert PROJECT_START not in (project / "CLAUDE.md").read_text(encoding="utf-8")

    state = json.loads((project / ".claude" / "ecc-init-state.json").read_text(encoding="utf-8"))
    assert state["schema_version"] == 2
    assert state["workflow"]["id"] == "gsd"
    assert state["migration"]["legacy_workflow_removed"] is True
    assert "ecc-init/legacy-v1" in state["packs"]
    assert detect_legacy_v1(project) is False
    assert (project / "docs" / "DEVELOPMENT_LOG.md").exists()
    assert (project / "docs" / "ecc-init-migration-report.md").exists()
    assert (ecc_home / "operations" / report.operation_id / "receipt.json").exists()


def test_migrate_preserves_user_modified_legacy_skill(tmp_path: Path, monkeypatch) -> None:
    project, _, claude_home = _prepare_legacy_v1(tmp_path, monkeypatch)
    modified = claude_home / "skills" / "task-planning" / "SKILL.md"
    modified.write_text(modified.read_text(encoding="utf-8") + "\n# local edit\n", encoding="utf-8")

    report = migrate_legacy_v1(project)

    assert modified.exists()
    assert any(
        action.action == "preserve-modified-skill" and action.path == modified.parent
        for action in report.actions
    )
    state = json.loads((project / ".claude" / "ecc-init-state.json").read_text(encoding="utf-8"))
    assert state["migration"]["legacy_workflow_removed"] is False
    assert report.warnings


def test_migrate_clean_v1_is_repeatable(tmp_path: Path, monkeypatch) -> None:
    project, _, _ = _prepare_legacy_v1(tmp_path, monkeypatch)
    first = migrate_legacy_v1(project)

    second = migrate_legacy_v1(project)

    assert first.applied is True
    assert second.detected is False
    assert second.applied is False
    assert second.actions == []


def test_migration_rollback_restores_legacy_v1_files(tmp_path: Path, monkeypatch) -> None:
    project, _, claude_home = _prepare_legacy_v1(tmp_path, monkeypatch)
    report = migrate_legacy_v1(project)

    backup_id, restored = rollback(project, operation_id=report.operation_id)

    state = json.loads((project / ".claude" / "ecc-init-state.json").read_text(encoding="utf-8"))
    assert backup_id == report.backup_id
    assert restored > 0
    assert state["version"] == 1
    assert (claude_home / "skills" / "task-planning" / "SKILL.md").exists()
    assert detect_legacy_v1(project) is True


def test_cli_migrate_dry_run_json(tmp_path: Path, monkeypatch, capsys) -> None:
    project, _, _ = _prepare_legacy_v1(tmp_path, monkeypatch)

    result = main(["migrate", str(project), "--dry-run", "--json"])

    assert _normalize_argv(["migrate", "."]) == ["migrate", "."]
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["detected"] is True
    assert payload["applied"] is False
    assert any(action["action"] == "write-migration-report" for action in payload["actions"])
