import json
from pathlib import Path

from ecc_init.app import doctor
from ecc_init.frontend import FRONTEND_LIFECYCLE_COMMANDS, frontend_doctor_checks
from ecc_init.packs.gsd_bridge import sync_gsd_config
from ecc_init.packs.registry import load_registry
from ecc_init.packs.resolver import build_registry_install_plan
from ecc_init.resources import read_resource_text
from ecc_init.sources import verify_registry_sources


def _write_skill(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("skill\n", encoding="utf-8")


def test_frontend_pack_selected_for_react_without_typescript(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"react": "19.0.0", "react-dom": "19.0.0"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    plan = build_registry_install_plan(tmp_path)
    component_ids = {component.component_id for component in plan.resolved_components}

    assert "frontend-essential" in plan.packs
    assert {"skill-ui-ux-pro-max", "skill-vercel-platform", "skill-playwright-quality"} <= component_ids
    assert "frontend-lifecycle-doc" in component_ids


def test_frontend_pack_not_selected_for_non_frontend(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    plan = build_registry_install_plan(tmp_path)

    assert "frontend-essential" not in plan.packs


def test_frontend_gsd_config_defaults_and_ui_agents_preserve_user_values(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "demo"
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "workflow": {"ui_review": False},
                "ui": {"review_enabled": False},
                "agent_skills": {"gsd-ui-reviewer": [".claude/skills/custom-ui"]},
            }
        ),
        encoding="utf-8",
    )
    for name in (
        "typescript-patterns",
        "react-patterns",
        "ui-ux-pro-max",
        "vercel-platform",
        "playwright-quality",
    ):
        _write_skill(project / ".claude" / "skills" / name)
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = sync_gsd_config(project, profile_id="frontend", packs=["project-baseline", "frontend-essential"])
    written = json.loads(config.read_text(encoding="utf-8"))

    assert report.changed is True
    assert written["workflow"]["ui_review"] is False
    assert written["ui"]["review_enabled"] is False
    assert written["ui"]["visual_verification"] is True
    assert written["ui"]["lifecycle_commands"] == list(FRONTEND_LIFECYCLE_COMMANDS)
    assert written["agent_skills"]["gsd-ui-designer"] == [".claude/skills/ui-ux-pro-max"]
    assert written["agent_skills"]["gsd-ui-reviewer"] == [
        ".claude/skills/custom-ui",
        ".claude/skills/ui-ux-pro-max",
        ".claude/skills/playwright-quality",
    ]
    assert written["agent_skills"]["gsd-verifier"] == [".claude/skills/playwright-quality"]


def test_frontend_doctor_reports_tool_detection(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "dependencies": {"react": "19.0.0"},
                "devDependencies": {"@playwright/test": "1.0.0"},
                "scripts": {"deploy": "vercel deploy"},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"tools": {"gsd_browser": {"enabled": True}}}), encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    checks = {label: detail for label, _ok, detail in frontend_doctor_checks(tmp_path)}
    app_checks = {check.label: check.detail for check in doctor(tmp_path)}

    assert checks["Frontend project"] == "detected"
    assert checks["Frontend Playwright"] == "detected"
    assert checks["Frontend Vercel"] == "detected"
    assert checks["Frontend GSD Browser"] == "detected"
    assert app_checks["Frontend Playwright"] == "detected"


def test_frontend_optional_sources_are_declared() -> None:
    checks = {check.check_id: check for check in verify_registry_sources(load_registry())}

    assert checks["source:vercel-skills:declared"].ok is True
    assert checks["source:anthropic-frontend-policy:declared"].ok is True


def test_frontend_skills_do_not_duplicate_gsd_lifecycle_commands() -> None:
    skill_resources = [
        "project_skills/ui-ux-pro-max/SKILL.md",
        "project_skills/vercel-platform/SKILL.md",
        "project_skills/playwright-quality/SKILL.md",
    ]
    for resource in skill_resources:
        content = read_resource_text(resource)
        assert "/gsd-" not in content

    lifecycle_doc = read_resource_text("templates/FRONTEND_LIFECYCLE.md")
    for command in FRONTEND_LIFECYCLE_COMMANDS:
        assert command in lifecycle_doc
