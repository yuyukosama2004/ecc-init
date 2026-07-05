import json
import shutil
from pathlib import Path

from ecc_init.cli import main


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "projects"


class FakeGsdRuntimeAdapter:
    def status(self, paths, *, runtime="claude", scope="global"):
        from ecc_init.workflows.base import EnvironmentCheck, PlannedCommand, WorkflowResult

        return WorkflowResult(
            "gsd",
            "installed_verified",
            commands=[
                PlannedCommand(
                    ("npx", "-y", "@opengsd/gsd-core@1.6.1", "--claude", "--global"),
                    "fake GSD install",
                )
            ],
            checks=[EnvironmentCheck("fake-node", True, "Node.js executable", "fake")],
        )


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    project = tmp_path / "projects" / name
    shutil.copytree(FIXTURE_ROOT / name, project)
    return project


def _run_json(capsys, argv: list[str], expected: int = 0) -> dict:
    assert main(argv) == expected
    return json.loads(capsys.readouterr().out)


def _doctor_checks(payload: dict) -> dict[str, dict]:
    return {item["label"]: item for item in payload["checks"]}


def _apply_fixture(tmp_path: Path, monkeypatch, capsys, name: str) -> tuple[Path, dict, dict, dict, dict]:
    project = _copy_fixture(tmp_path, name)
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    monkeypatch.setattr("ecc_init.app.GsdWorkflowAdapter", lambda: FakeGsdRuntimeAdapter())
    plan_path = project / "ecc-plan.json"

    plan = _run_json(capsys, ["plan", str(project), "--output", str(plan_path), "--json"])
    assert plan_path.exists()

    monkeypatch.chdir(project)
    apply_payload = _run_json(capsys, ["apply", str(plan_path), "--yes", "--skip-gsd-check", "--json"])
    status_payload = _run_json(capsys, ["status", str(project), "--json"])
    doctor_payload = _run_json(capsys, ["doctor", str(project), "--json"])

    assert apply_payload["status"] == "applied"
    assert apply_payload["applied"] is True
    assert apply_payload["operation_id"]
    assert {item["source_id"] for item in apply_payload["sources_locked"]} == {"bundled"}
    assert not any(str(tmp_path / "claude-home") in item["path"] for item in apply_payload["files_written"])
    assert status_payload["source_lock"]["status"] == "present"
    assert status_payload["last_receipt"]["operation_id"] == apply_payload["operation_id"]
    assert status_payload["apply_readiness"]["ready"] is True
    assert status_payload["apply_readiness"]["plan_consistency"]["status"] == "matches"
    assert doctor_payload["summary"]["FAIL"] == 0
    for label in ("GSD runtime", "Project source lock", "Latest apply receipt", "Apply readiness"):
        assert _doctor_checks(doctor_payload)[label]["status"] == "PASS"

    return project, plan, apply_payload, status_payload, doctor_payload


def _rollback_applied_project(capsys, project: Path, operation_id: str) -> dict:
    rollback_payload = _run_json(
        capsys,
        ["rollback", str(project), "--operation-id", operation_id, "--json"],
    )
    assert rollback_payload["restored"] > 0
    assert not (project / ".claude" / "ecc-sources.lock.json").exists()
    assert not (project / ".claude" / "ecc-init-state.json").exists()
    return rollback_payload


def test_empty_project_plan_apply_status_doctor_and_rollback(tmp_path: Path, monkeypatch, capsys) -> None:
    project, plan, apply_payload, status_payload, _doctor_payload = _apply_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        "empty",
    )

    assert plan["packs"] == ["project-baseline", "quality-basic"]
    assert status_payload["detected_stacks"] == []
    assert set(status_payload["packs"]["installed"]) == {"project-baseline", "quality-basic"}
    assert not (project / ".claude" / "skills").exists()
    assert (project / "CLAUDE.md").exists()
    assert (project / "docs" / "PROJECT_OVERVIEW.md").exists()
    assert any("skipped non-project component" in warning for warning in apply_payload["warnings"])

    _rollback_applied_project(capsys, project, apply_payload["operation_id"])
    assert not (project / "CLAUDE.md").exists()
    assert not (project / "docs" / "PROJECT_OVERVIEW.md").exists()


def test_fastapi_langgraph_project_e2e_installs_matching_bundled_skills(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project, plan, apply_payload, status_payload, _doctor_payload = _apply_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        "fastapi-langgraph",
    )

    assert status_payload["detected_stacks"] == ["python", "fastapi", "langchain", "langgraph"]
    assert {"project-baseline", "quality-basic", "python-fastapi", "rag-python"} <= set(plan["packs"])
    assert "frontend-essential" not in plan["packs"]
    assert "java-spring" not in plan["packs"]
    for skill in ("python-patterns", "fastapi-patterns", "langchain-patterns", "langgraph-patterns"):
        assert (project / ".claude" / "skills" / skill / "SKILL.md").exists()
    assert not (project / ".claude" / "skills" / "react-patterns").exists()
    assert set(status_payload["sources"]["locked"]) == {"bundled"}

    _rollback_applied_project(capsys, project, apply_payload["operation_id"])
    assert not (project / ".claude" / "skills" / "python-patterns" / "SKILL.md").exists()


def test_react_vite_project_e2e_installs_frontend_bundle_and_reports_tools(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project, plan, apply_payload, status_payload, doctor_payload = _apply_fixture(
        tmp_path,
        monkeypatch,
        capsys,
        "react-vite",
    )

    assert status_payload["detected_stacks"] == ["typescript", "react"]
    assert {"project-baseline", "quality-basic", "frontend-essential"} <= set(plan["packs"])
    assert "python-fastapi" not in plan["packs"]
    for skill in (
        "typescript-patterns",
        "react-patterns",
        "ui-ux-pro-max",
        "vercel-platform",
        "playwright-quality",
    ):
        assert (project / ".claude" / "skills" / skill / "SKILL.md").exists()
    assert (project / "docs" / "FRONTEND_LIFECYCLE.md").exists()
    by_label = _doctor_checks(doctor_payload)
    assert by_label["Frontend project"]["detail"] == "detected"
    assert by_label["Frontend Playwright"]["detail"] == "detected"
    assert by_label["Frontend Vercel"]["detail"] == "detected"

    _rollback_applied_project(capsys, project, apply_payload["operation_id"])
    assert not (project / "docs" / "FRONTEND_LIFECYCLE.md").exists()


def test_existing_gsd_config_e2e_syncs_and_rolls_back_config(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = _copy_fixture(tmp_path, "existing-gsd-config")
    config_path = project / ".planning" / "config.json"
    original_config = json.loads(config_path.read_text(encoding="utf-8"))
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    monkeypatch.setattr("ecc_init.app.GsdWorkflowAdapter", lambda: FakeGsdRuntimeAdapter())
    plan_path = project / "ecc-plan.json"

    plan = _run_json(capsys, ["plan", str(project), "--output", str(plan_path), "--json"])
    monkeypatch.chdir(project)
    apply_payload = _run_json(capsys, ["apply", str(plan_path), "--yes", "--skip-gsd-check", "--json"])
    status_payload = _run_json(capsys, ["status", str(project), "--json"])
    doctor_payload = _run_json(capsys, ["doctor", str(project), "--json"])
    written_config = json.loads(config_path.read_text(encoding="utf-8"))

    assert {"python-fastapi", "rag-python"} <= set(plan["packs"])
    assert apply_payload["status"] == "applied"
    assert apply_payload["config_report"]["initialized"] is True
    assert apply_payload["config_report"]["changed"] is True
    assert status_payload["apply_readiness"]["ready"] is True
    assert doctor_payload["summary"]["FAIL"] == 0
    assert written_config["parallelization"]["enabled"] is False
    assert written_config["workflow"]["use_worktrees"] is False
    assert written_config["agent_skills"]["gsd-executor"][0] == ".claude/skills/custom-existing"
    for entry in (
        ".claude/skills/python-patterns",
        ".claude/skills/fastapi-patterns",
        ".claude/skills/langchain-patterns",
        ".claude/skills/langgraph-patterns",
    ):
        assert entry in written_config["agent_skills"]["gsd-executor"]

    _rollback_applied_project(capsys, project, apply_payload["operation_id"])
    assert json.loads(config_path.read_text(encoding="utf-8")) == original_config
