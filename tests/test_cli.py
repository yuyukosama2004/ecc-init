import json
from pathlib import Path

from ecc_init.cli import _normalize_argv, main


def test_default_command_accepts_offline_flag() -> None:
    assert _normalize_argv(["--offline"]) == ["init", "--offline"]


def test_explicit_status_is_preserved() -> None:
    assert _normalize_argv(["status", "."]) == ["status", "."]


def test_explicit_plan_is_preserved() -> None:
    assert _normalize_argv(["plan", "."]) == ["plan", "."]


def test_explicit_packs_is_preserved() -> None:
    assert _normalize_argv(["packs", "list"]) == ["packs", "list"]


def test_explicit_sources_is_preserved() -> None:
    assert _normalize_argv(["sources", "verify"]) == ["sources", "verify"]


def test_explicit_workflow_is_preserved() -> None:
    assert _normalize_argv(["workflow", "status"]) == ["workflow", "status"]


def test_explicit_sync_gsd_is_preserved() -> None:
    assert _normalize_argv(["sync-gsd", "."]) == ["sync-gsd", "."]


def test_explicit_lifecycle_commands_are_preserved() -> None:
    assert _normalize_argv(["apply", "plan.json"]) == ["apply", "plan.json"]
    assert _normalize_argv(["remove", "."]) == ["remove", "."]
    assert _normalize_argv(["--debug", "update", "--check"]) == ["--debug", "update", "--check"]
    assert _normalize_argv(["--debug", "--offline"]) == ["--debug", "init", "--offline"]


def test_plan_json_does_not_write_project_files(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    result = main(["plan", str(project), "--json"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 2
    assert payload["workflow"] == "gsd"
    assert "python-fastapi" in payload["packs"]
    assert payload["external_operations"][0]["args"] == ["-y", "@opengsd/gsd-core@1.6.1"]
    assert not (project / ".claude").exists()
    assert not (project / "docs").exists()


def test_packs_list_and_show(capsys) -> None:
    assert main(["packs", "list"]) == 0
    assert "project-baseline" in capsys.readouterr().out

    assert main(["packs", "show", "frontend-essential", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pack_id"] == "frontend-essential"


def test_sources_list_and_verify(capsys) -> None:
    assert main(["sources", "list"]) == 0
    assert "bundled" in capsys.readouterr().out

    assert main(["sources", "verify", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(item["check_id"] == "source:bundled:bundled" for item in payload)


def test_workflow_status_json_uses_adapter(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeAdapter:
        def verify(self, paths):
            from ecc_init.workflows.base import EnvironmentCheck, WorkflowResult

            return WorkflowResult("gsd", "ok", checks=[EnvironmentCheck("fake", True, "ok")])

    monkeypatch.setattr("ecc_init.cli.GsdWorkflowAdapter", lambda: FakeAdapter())

    assert main(["workflow", "status", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["workflow"] == "gsd"
    assert payload["checks"][0]["check_id"] == "fake"


def test_sync_gsd_dry_run_does_not_write(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"parallelization":{"enabled":false}}\n', encoding="utf-8")
    (project / ".claude" / "skills" / "python-patterns").mkdir(parents=True)
    (project / ".claude" / "skills" / "python-patterns" / "SKILL.md").write_text("skill\n", encoding="utf-8")
    (project / ".claude" / "skills" / "fastapi-patterns").mkdir(parents=True)
    (project / ".claude" / "skills" / "fastapi-patterns" / "SKILL.md").write_text("skill\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["sync-gsd", str(project), "--pack", "project-baseline", "--pack", "python-fastapi", "--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["changed"] is True
    assert json.loads(config.read_text(encoding="utf-8")) == {"parallelization": {"enabled": False}}
