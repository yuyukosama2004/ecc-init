import json
from pathlib import Path

from ecc_init.app import initialize_project, project_status


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
