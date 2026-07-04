import json
from pathlib import Path

import pytest

from ecc_init.core.models import (
    CheckResult,
    ComponentSpec,
    ConfigOperation,
    ExternalOperation,
    FileOperation,
    InstallPlan,
    Operation,
    PackSpec,
    Receipt,
    ResolvedComponent,
    SourceSpec,
    StateMigration,
    WorkflowSpec,
)
from ecc_init.core.plan import build_legacy_install_plan
from ecc_init.core.validation import validate_legacy_manifest
from ecc_init.errors import ConfigError


def test_model_round_trips() -> None:
    source = SourceSpec(
        source_id="gsd",
        kind="npm",
        repository="https://github.com/open-gsd/gsd-core",
        package="@opengsd/gsd-core",
        version="1.0.0",
        commit="abc",
        path=".",
        license_id="MIT",
        license_path="LICENSE",
        integrity="sha256:test",
        executable_surface=("npx",),
    )
    assert SourceSpec.from_dict(source.to_dict()) == source

    component = ComponentSpec(
        component_id="python-skill",
        source_id="bundled",
        install_name="python-patterns",
        target_scope="project",
        target_subdir=".claude/skills/python-patterns",
        projection_include=("SKILL.md",),
    )
    assert ComponentSpec.from_dict(component.to_dict()) == component

    pack = PackSpec(
        pack_id="python-basic",
        version=1,
        description="Python defaults",
        components=("python-skill",),
        requires=("project-baseline",),
        gsd_agent_skills={"executor": ("python-patterns",)},
        gsd_config_defaults={"parallelization": {"enabled": False}},
    )
    assert PackSpec.from_dict(pack.to_dict()) == pack

    workflow = WorkflowSpec(workflow_id="gsd", adapter="gsd", source_id="gsd-core", conflicts=("legacy",))
    assert WorkflowSpec.from_dict(workflow.to_dict()) == workflow

    operation = Operation(operation_id="op-1", kind="file", summary="write", target="CLAUDE.md")
    assert Operation.from_dict(operation.to_dict()) == operation

    file_operation = FileOperation(
        operation_id="file-1",
        action="merge",
        path=Path("CLAUDE.md"),
        source_id="project-claude",
        target_scope="project",
    )
    external_operation = ExternalOperation(operation_id="ext-1", command="npx", args=("--version",))
    config_operation = ConfigOperation(
        operation_id="cfg-1",
        path=Path(".planning/config.json"),
        action="default",
        description="set default",
    )
    plan = InstallPlan(
        project_root=Path("demo"),
        workflow="legacy-ecc",
        workflow_scope="global+project",
        packs=["legacy-global"],
        resolved_components=[
            ResolvedComponent(
                component_id="project-claude",
                install_name="CLAUDE.md",
                source_id="project-claude",
                target_scope="project",
                target_path=Path("CLAUDE.md"),
            )
        ],
        state_migrations=[StateMigration(from_schema=1, to_schema=2, description="future")],
        file_operations=[file_operation],
        external_operations=[external_operation],
        config_operations=[config_operation],
        warnings=["preview"],
    )
    assert InstallPlan.from_json(plan.to_json()).to_dict() == plan.to_dict()

    receipt = Receipt(
        operation_id="op-1",
        created_at="2026-07-03T00:00:00+08:00",
        project_root=Path("demo"),
        workflow={"id": "legacy-ecc", "status": "planned"},
        packs=[{"id": "legacy-global", "version": 1}],
    )
    assert Receipt.from_dict(receipt.to_dict()) == receipt

    check = CheckResult(check_id="manifest", ok=True, severity="info", message="ok")
    assert CheckResult.from_dict(check.to_dict()) == check


def test_legacy_plan_contains_detected_project_skill(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    plan = build_legacy_install_plan(tmp_path)
    payload = json.loads(plan.to_json())

    assert payload["workflow"] == "legacy-ecc"
    assert "legacy-stack:fastapi" in payload["packs"]
    assert any(item["install_name"] == "fastapi-patterns" for item in payload["resolved_components"])
    assert any(
        item["install_name"] == "DEVELOPMENT_LOG.md" and item["target_scope"] == "project"
        for item in payload["resolved_components"]
    )
    assert plan.external_operations == []


def test_invalid_manifest_has_clear_error() -> None:
    with pytest.raises(ConfigError, match="global_skills"):
        validate_legacy_manifest({"version": 1, "project_skills": []})
