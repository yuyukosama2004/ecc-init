import json
import zipfile
from io import BytesIO
from pathlib import Path

from ecc_init.apply import ApplyOptions, apply_install_plan
from ecc_init.cli import main
from ecc_init.core.models import (
    ComponentSpec,
    FileOperation,
    InstallPlan,
    PackSpec,
    ResolvedComponent,
    SourceSpec,
    WorkflowSpec,
)
from ecc_init.packs import build_registry_install_plan
from ecc_init.packs.registry import Registry


COMMIT = "b" * 40


def _zip_bytes(path: str, content: bytes) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(path, content)
    return buffer.getvalue()


class FakeStatusAdapter:
    def status(self, paths, *, runtime="claude", scope="global"):
        from ecc_init.workflows.base import EnvironmentCheck, PlannedCommand, WorkflowResult

        return WorkflowResult(
            "gsd",
            "not_installed",
            commands=[
                PlannedCommand(
                    ("npx", "-y", "@opengsd/gsd-core@1.6.1", "--claude", "--global"),
                    "fake GSD install",
                )
            ],
            checks=[EnvironmentCheck("fake-node", True, "Node.js executable", "fake")],
            warnings=["fake not installed"],
        )


def test_apply_dry_run_report_is_stable_and_does_not_write(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    plan = build_registry_install_plan(project)
    plan_path = project / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["apply", str(plan_path), "--dry-run", "--json", "--skip-gsd-check"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "dry_run"
    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["files_planned"]
    assert payload["files_written"] == []
    assert payload["sources_locked"] == []
    assert payload["sources_planned"]
    assert not (project / ".claude").exists()
    assert not (project / "docs").exists()


def test_apply_blocks_project_root_mismatch(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    other = tmp_path / "other"
    project.mkdir()
    other.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    plan = build_registry_install_plan(project)

    report = apply_install_plan(
        plan,
        ApplyOptions(dry_run=True, expected_project_root=other, skip_gsd_check=True),
    )

    assert report.status == "blocked"
    assert any("does not match current project root" in error for error in report.errors)


def test_init_yes_uses_apply_not_workflow_update(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    def fail_update_project(*args, **kwargs):
        raise AssertionError("init --yes must not call lifecycle update as GSD install")

    monkeypatch.setattr("ecc_init.cli.update_project", fail_update_project)
    monkeypatch.setattr("ecc_init.apply.GsdWorkflowAdapter", lambda: FakeStatusAdapter())

    assert main(["init", str(project), "--yes", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["gsd_install"] is None
    assert payload["apply"]["status"] in {"applied", "applied_with_warnings"}
    assert payload["apply"]["applied"] is True
    assert (project / "docs" / "PROJECT_OVERVIEW.md").exists()


def test_apply_yes_installs_bundled_project_files_state_lock_and_receipt(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    plan = build_registry_install_plan(project)
    plan_path = project / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["apply", str(plan_path), "--yes", "--skip-gsd-check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    receipts = list((tmp_path / "ecc-home" / "operations").glob("*/receipt.json"))
    state = json.loads((project / ".claude" / "ecc-init-state.json").read_text(encoding="utf-8"))
    source_lock = json.loads((project / ".claude" / "ecc-sources.lock.json").read_text(encoding="utf-8"))

    assert payload["status"] in {"applied", "applied_with_warnings"}
    assert payload["applied"] is True
    assert payload["operation_id"]
    assert payload["backup_id"]
    assert (project / ".claude" / "skills" / "python-patterns" / "SKILL.md").exists()
    assert (project / ".claude" / "skills" / "fastapi-patterns" / "SKILL.md").exists()
    assert source_lock["sources"]["bundled"]["source_id"] == "bundled"
    assert state["schema_version"] == 2
    assert "python-fastapi" in state["packs"]
    assert state["managed_files"]
    assert not (project / ".planning" / "config.json").exists()
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["result"] == "success"
    assert any(item["owner"].startswith("pack:") for item in receipt["files"])


def test_apply_yes_can_be_rolled_back_by_operation_id(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    plan = build_registry_install_plan(project)
    plan_path = project / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["apply", str(plan_path), "--yes", "--skip-gsd-check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert (project / "docs" / "PROJECT_OVERVIEW.md").exists()

    assert main(["rollback", str(project), "--operation-id", payload["operation_id"], "--json"]) == 0
    rollback_payload = json.loads(capsys.readouterr().out)

    assert rollback_payload["restored"] > 0
    assert not (project / "docs" / "PROJECT_OVERVIEW.md").exists()
    assert not (project / ".claude" / "ecc-sources.lock.json").exists()


def test_apply_yes_syncs_existing_gsd_config_and_rollback_restores_it(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    original_config = {
        "parallelization": {"enabled": False},
        "workflow": {"use_worktrees": False},
    }
    config.write_text(json.dumps(original_config), encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    plan = build_registry_install_plan(project)
    plan_path = project / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["apply", str(plan_path), "--yes", "--skip-gsd-check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    written = json.loads(config.read_text(encoding="utf-8"))
    receipts = list((tmp_path / "ecc-home" / "operations").glob("*/receipt.json"))

    assert payload["status"] in {"applied", "applied_with_warnings"}
    assert payload["config_report"]["initialized"] is True
    assert payload["config_report"]["changed"] is True
    assert written["parallelization"]["enabled"] is False
    assert written["parallelization"]["max_concurrent_agents"] == 3
    assert written["workflow"]["use_worktrees"] is False
    assert ".claude/skills/python-patterns" in written["agent_skills"]["gsd-executor"]
    assert ".claude/skills/fastapi-patterns" in written["agent_skills"]["gsd-executor"]
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["config_changes"][0]["action"] == "sync-gsd"

    assert main(["rollback", str(project), "--operation-id", payload["operation_id"], "--json"]) == 0
    rollback_payload = json.loads(capsys.readouterr().out)

    assert rollback_payload["restored"] > 0
    assert json.loads(config.read_text(encoding="utf-8")) == original_config


def test_apply_yes_no_sync_gsd_leaves_existing_config_unchanged(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    original_config = {"parallelization": {"enabled": False}}
    config.write_text(json.dumps(original_config), encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    plan = build_registry_install_plan(project)
    plan_path = project / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["apply", str(plan_path), "--yes", "--skip-gsd-check", "--no-sync-gsd", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] in {"applied", "applied_with_warnings"}
    assert payload["config_report"] is None
    assert json.loads(config.read_text(encoding="utf-8")) == original_config


def test_apply_preserves_existing_unowned_files(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    target = project / ".claude" / "skills" / "python-patterns" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("user skill\n", encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    plan = build_registry_install_plan(project)
    plan_path = project / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["apply", str(plan_path), "--yes", "--skip-gsd-check", "--json"]) == 4
    payload = json.loads(capsys.readouterr().out)

    assert target.read_text(encoding="utf-8") == "user skill\n"
    assert payload["status"] == "partial"
    assert any(item["component_id"] == "skill-python-patterns" for item in payload["files_skipped"])
    assert any("preserved existing unowned file" in warning for warning in payload["warnings"])
    assert (project / ".claude" / "skills" / "fastapi-patterns" / "SKILL.md").exists()
    receipts = list((tmp_path / "ecc-home" / "operations").glob("*/receipt.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["result"] == "partial_success"


def test_apply_yes_installs_fixed_github_archive_component_from_offline_cache(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    target = project / ".claude" / "skills" / "github-python" / "SKILL.md"
    archive = tmp_path / "ecc-home" / "cache" / "archives" / "github-test" / f"{COMMIT}.zip"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(_zip_bytes(f"repo-{COMMIT}/skills/python/SKILL.md", b"github skill\n"))
    source = SourceSpec(
        source_id="github-test",
        kind="github_archive",
        repository="https://github.com/affaan-m/ECC",
        version=COMMIT,
        commit=COMMIT,
        path="skills/python",
        license_id="MIT",
    )
    component = ComponentSpec(
        component_id="github-component",
        source_id="github-test",
        install_name="github-python",
        target_scope="project",
        target_subdir=".claude/skills/github-python/SKILL.md",
        projection_include=("SKILL.md",),
        required=True,
    )
    registry = Registry(
        sources={"github-test": source},
        workflows={"none": WorkflowSpec("none", "none", None, "project", ())},
        components={"github-component": component},
        packs={"github-pack": PackSpec("github-pack", 1, "GitHub archive test", ("github-component",))},
        profiles={},
    )
    monkeypatch.setattr("ecc_init.apply.load_registry", lambda: registry)
    plan = InstallPlan(
        project_root=project,
        workflow="none",
        workflow_scope="project",
        packs=["github-pack"],
        resolved_components=[
            ResolvedComponent("github-component", "github-python", "github-test", "project", target, True)
        ],
        file_operations=[
            FileOperation("file:github-component", "plan-install", target, "github-test", "project")
        ],
    )

    report = apply_install_plan(
        plan,
        ApplyOptions(dry_run=False, yes=True, expected_project_root=project, offline=True),
    )

    receipts = list((tmp_path / "ecc-home" / "operations").glob("*/receipt.json"))
    source_lock = json.loads((project / ".claude" / "ecc-sources.lock.json").read_text(encoding="utf-8"))

    assert report.status in {"applied", "applied_with_warnings"}
    assert target.read_text(encoding="utf-8") == "github skill\n"
    assert source_lock["sources"]["github-test"]["resolved_ref"] == COMMIT
    assert source_lock["sources"]["github-test"]["source_path"] == "skills/python"
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["sources"][0]["source_id"] == "github-test"


def test_apply_yes_skips_missing_optional_github_archive_without_locking_source(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    bundled_target = project / "docs" / "PROJECT_OVERVIEW.md"
    optional_target = project / ".claude" / "skills" / "optional-github" / "SKILL.md"
    bundled_source = SourceSpec(
        source_id="bundled",
        kind="bundled",
        version="0.2.0a0",
        path="resources",
        license_id="MIT",
    )
    github_source = SourceSpec(
        source_id="github-optional",
        kind="github_archive",
        repository="https://github.com/affaan-m/ECC",
        version=COMMIT,
        commit=COMMIT,
        path="skills/python",
        license_id="MIT",
    )
    bundled_component = ComponentSpec(
        component_id="bundled-overview",
        source_id="bundled",
        install_name="PROJECT_OVERVIEW.md",
        target_scope="project",
        target_subdir="docs/PROJECT_OVERVIEW.md",
        projection_include=("templates/PROJECT_OVERVIEW.md",),
        required=True,
    )
    optional_component = ComponentSpec(
        component_id="optional-github-component",
        source_id="github-optional",
        install_name="optional-github",
        target_scope="project",
        target_subdir=".claude/skills/optional-github/SKILL.md",
        projection_include=("SKILL.md",),
        required=False,
    )
    registry = Registry(
        sources={"bundled": bundled_source, "github-optional": github_source},
        workflows={"none": WorkflowSpec("none", "none", None, "project", ())},
        components={
            "bundled-overview": bundled_component,
            "optional-github-component": optional_component,
        },
        packs={
            "mixed-pack": PackSpec(
                "mixed-pack",
                1,
                "Mixed bundled and optional GitHub archive test",
                ("bundled-overview", "optional-github-component"),
            )
        },
        profiles={},
    )
    monkeypatch.setattr("ecc_init.apply.load_registry", lambda: registry)
    plan = InstallPlan(
        project_root=project,
        workflow="none",
        workflow_scope="project",
        packs=["mixed-pack"],
        resolved_components=[
            ResolvedComponent("bundled-overview", "PROJECT_OVERVIEW.md", "bundled", "project", bundled_target, True),
            ResolvedComponent(
                "optional-github-component",
                "optional-github",
                "github-optional",
                "project",
                optional_target,
                False,
            ),
        ],
        file_operations=[
            FileOperation("file:bundled-overview", "plan-install", bundled_target, "bundled", "project"),
            FileOperation("file:optional-github-component", "plan-install", optional_target, "github-optional", "project"),
        ],
    )

    report = apply_install_plan(
        plan,
        ApplyOptions(dry_run=False, yes=True, expected_project_root=project, offline=True),
    )

    source_lock = json.loads((project / ".claude" / "ecc-sources.lock.json").read_text(encoding="utf-8"))

    assert report.status in {"applied", "applied_with_warnings"}
    assert bundled_target.exists()
    assert not optional_target.exists()
    assert any("skipped optional component optional-github-component" in warning for warning in report.warnings)
    assert sorted(source_lock["sources"]) == ["bundled"]
    assert [item["source_id"] for item in report.sources_locked] == ["bundled"]
