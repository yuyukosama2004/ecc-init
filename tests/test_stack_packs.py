import json
from pathlib import Path

from ecc_init.packs.gsd_bridge import sync_gsd_config
from ecc_init.packs.registry import load_registry
from ecc_init.packs.resolver import build_registry_install_plan
from ecc_init.resources import read_resource_text
from ecc_init.sources import verify_registry_sources


def _write_skill(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("skill\n", encoding="utf-8")


def _component_ids(project: Path) -> set[str]:
    return {component.component_id for component in build_registry_install_plan(project).resolved_components}


def test_ecc_upstream_source_is_fixed_commit() -> None:
    registry = load_registry()
    source = registry.sources["ecc-upstream-pinned"]
    checks = {check.check_id: check for check in verify_registry_sources(registry)}

    assert source.kind == "github_archive"
    assert source.repository == "https://github.com/affaan-m/ECC"
    assert source.commit is not None
    assert len(source.commit) == 40
    assert source.commit == source.version
    assert checks["source:ecc-upstream-pinned:host"].ok is True
    assert checks["source:ecc-upstream-pinned:ref"].ok is True


def test_project_skill_frontmatter_has_version_and_source() -> None:
    for path in sorted(Path("src/ecc_init/resources/project_skills").glob("*/SKILL.md")):
        content = path.read_text(encoding="utf-8")
        frontmatter = content.split("---", 2)[1]

        assert "name:" in frontmatter
        assert "description:" in frontmatter
        assert "metadata:" in frontmatter
        assert "  source_id:" in frontmatter
        assert "  content_version: 1" in frontmatter
        assert "/gsd-" not in content


def test_stack_skill_resources_are_bundled_for_offline_fallback() -> None:
    registry = load_registry()
    stack_components = [
        component
        for component in registry.components.values()
        if component.install_name
        in {
            "python-patterns",
            "fastapi-patterns",
            "langchain-patterns",
            "langgraph-patterns",
            "java-patterns",
            "springboot-patterns",
        }
    ]

    assert len(stack_components) == 6
    for component in stack_components:
        for resource in component.projection_include:
            assert read_resource_text(resource)


def test_python_and_fastapi_components_filter_independently(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["pytest"]\n', encoding="utf-8")

    python_only = _component_ids(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    fastapi = _component_ids(tmp_path)

    assert "skill-python-patterns" in python_only
    assert "skill-fastapi-patterns" not in python_only
    assert {"skill-python-patterns", "skill-fastapi-patterns"} <= fastapi


def test_rag_components_filter_independently(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["langchain"]\n', encoding="utf-8")

    langchain_only = _component_ids(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["langchain", "langgraph"]\n',
        encoding="utf-8",
    )
    both = _component_ids(tmp_path)

    assert "skill-langchain-patterns" in langchain_only
    assert "skill-langgraph-patterns" not in langchain_only
    assert {"skill-langchain-patterns", "skill-langgraph-patterns"} <= both


def test_java_and_spring_components_filter_independently(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")

    java_only = _component_ids(tmp_path)
    (tmp_path / "pom.xml").write_text(
        '<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>',
        encoding="utf-8",
    )
    spring = _component_ids(tmp_path)

    assert "skill-java-patterns" in java_only
    assert "skill-springboot-patterns" not in java_only
    assert {"skill-java-patterns", "skill-springboot-patterns"} <= spring


def test_stack_agent_injection_filters_missing_stack_components(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["pytest"]\n', encoding="utf-8")
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text("{}", encoding="utf-8")
    _write_skill(project / ".claude" / "skills" / "python-patterns")
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = sync_gsd_config(project, packs=["project-baseline", "python-fastapi"])

    assert report.after["agent_skills"]["gsd-executor"] == [".claude/skills/python-patterns"]
    assert "gsd-verifier" in report.after["agent_skills"]
    assert not any("fastapi-patterns" in warning for warning in report.warnings)


def test_rag_agent_mapping_includes_researcher_planner_executor_and_reviewer(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\ndependencies = ["langchain", "langgraph"]\n',
        encoding="utf-8",
    )
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({}), encoding="utf-8")
    for name in ("langchain-patterns", "langgraph-patterns"):
        _write_skill(project / ".claude" / "skills" / name)
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = sync_gsd_config(project, packs=["project-baseline", "rag-python"])

    assert report.after["agent_skills"]["gsd-phase-researcher"] == [
        ".claude/skills/langchain-patterns",
        ".claude/skills/langgraph-patterns",
    ]
    assert "gsd-planner" in report.after["agent_skills"]
    assert "gsd-executor" in report.after["agent_skills"]
    assert "gsd-code-reviewer" in report.after["agent_skills"]
