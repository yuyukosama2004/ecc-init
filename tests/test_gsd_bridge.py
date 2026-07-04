import json
from pathlib import Path

import pytest

from ecc_init.core.models import ComponentSpec, PackSpec
from ecc_init.errors import ConfigError
from ecc_init.paths import AppPaths
from ecc_init.packs.gsd_bridge import (
    deep_merge_missing,
    merge_agent_skills,
    pack_agent_skill_additions,
    remove_pack_agent_skills,
    sync_gsd_config,
)
from ecc_init.packs.registry import Registry, load_registry


def _write_skill(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("skill\n", encoding="utf-8")


def test_deep_merge_missing_preserves_user_values() -> None:
    existing = {"parallelization": {"enabled": False}}
    defaults = {"parallelization": {"enabled": True, "max_concurrent_agents": 3}}

    merged = deep_merge_missing(existing, defaults)

    assert merged == {"parallelization": {"enabled": False, "max_concurrent_agents": 3}}


def test_merge_agent_skills_deduplicates() -> None:
    merged = merge_agent_skills(
        {"agent_skills": {"gsd-executor": [".claude/skills/python-patterns"]}},
        {"gsd-executor": [".claude/skills/python-patterns", ".claude/skills/fastapi-patterns"]},
    )

    assert merged["agent_skills"]["gsd-executor"] == [
        ".claude/skills/python-patterns",
        ".claude/skills/fastapi-patterns",
    ]


def test_sync_gsd_config_preserves_explicit_values_and_adds_agent_skills(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    config.write_text(
        json.dumps(
            {
                "parallelization": {"enabled": False},
                "workflow": {"use_worktrees": False},
                "agent_skills": {"gsd-executor": [".claude/skills/python-patterns"]},
            }
        ),
        encoding="utf-8",
    )
    _write_skill(project / ".claude" / "skills" / "python-patterns")
    _write_skill(project / ".claude" / "skills" / "fastapi-patterns")
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = sync_gsd_config(
        project,
        packs=["project-baseline", "python-fastapi"],
        dry_run=False,
    )
    written = json.loads(config.read_text(encoding="utf-8"))

    assert report.changed is True
    assert written["parallelization"]["enabled"] is False
    assert written["parallelization"]["max_concurrent_agents"] == 3
    assert written["workflow"]["use_worktrees"] is False
    assert written["agent_skills"]["gsd-executor"] == [
        ".claude/skills/python-patterns",
        ".claude/skills/fastapi-patterns",
    ]


def test_sync_gsd_uninitialized_does_not_create_config(tmp_path: Path) -> None:
    report = sync_gsd_config(tmp_path, dry_run=False)

    assert report.initialized is False
    assert not (tmp_path / ".planning" / "config.json").exists()
    assert any("not initialized" in warning for warning in report.warnings)


def test_sync_gsd_malformed_json_does_not_overwrite(tmp_path: Path) -> None:
    config = tmp_path / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text("{bad", encoding="utf-8")

    with pytest.raises(ConfigError, match="无法读取 GSD config"):
        sync_gsd_config(tmp_path)

    assert config.read_text(encoding="utf-8") == "{bad"


def test_missing_deleted_skill_is_skipped(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    (project / ".planning").mkdir(parents=True)
    (project / ".planning" / "config.json").write_text("{}", encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["pytest"]\n', encoding="utf-8")
    _write_skill(project / ".claude" / "skills" / "python-patterns")
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    report = sync_gsd_config(project, packs=["project-baseline", "python-fastapi"])

    assert report.after["agent_skills"]["gsd-executor"] == [".claude/skills/python-patterns"]
    assert not any("fastapi-patterns" in warning for warning in report.warnings)


def test_remove_pack_agent_skills_only_removes_pack_entries() -> None:
    registry = load_registry()
    config = {
        "agent_skills": {
            "gsd-executor": [
                ".claude/skills/python-patterns",
                ".claude/skills/fastapi-patterns",
                ".claude/skills/other",
            ]
        }
    }

    updated = remove_pack_agent_skills(config, registry, "python-fastapi")

    assert updated["agent_skills"]["gsd-executor"] == [".claude/skills/other"]


def test_agent_skill_path_traversal_is_rejected(tmp_path: Path) -> None:
    registry = Registry(
        sources={},
        workflows={},
        components={
            "bad-component": ComponentSpec(
                component_id="bad-component",
                source_id="bundled",
                install_name="bad-skill",
                target_scope="project",
                target_subdir="../bad-skill",
            )
        },
        packs={
            "bad-pack": PackSpec(
                pack_id="bad-pack",
                version=1,
                description="",
                components=("bad-component",),
                gsd_agent_skills={"executor": ("bad-skill",)},
            )
        },
        profiles={},
    )

    with pytest.raises(ConfigError, match="unsafe agent skill path"):
        pack_agent_skill_additions(AppPaths.build(tmp_path), registry, ["bad-pack"])
