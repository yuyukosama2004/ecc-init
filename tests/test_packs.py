from pathlib import Path

import pytest

from ecc_init.core.models import PackSpec
from ecc_init.errors import ConfigError
from ecc_init.packs.registry import Registry, load_registry
from ecc_init.packs.resolver import build_registry_install_plan, resolve_pack_order


def test_default_plan_filters_by_stack_and_is_stable(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi", "langchain", "langgraph"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    first = build_registry_install_plan(tmp_path)
    second = build_registry_install_plan(tmp_path)

    assert first.packs == ["project-baseline", "quality-basic", "python-fastapi", "rag-python"]
    assert "frontend-essential" not in first.packs
    assert first.to_json() == second.to_json()
    assert first.external_operations[0].dry_run is True


def test_profile_and_without_pack_affect_plan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    minimal = build_registry_install_plan(tmp_path, profile_id="minimal")
    without_quality = build_registry_install_plan(tmp_path, exclude_packs=("quality-basic",))

    assert minimal.workflow == "none"
    assert minimal.packs == ["project-baseline"]
    assert without_quality.packs == ["project-baseline"]


def test_explicit_pack_requires_dependency(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="requires excluded or missing pack project-baseline"):
        build_registry_install_plan(
            tmp_path,
            profile_id="minimal",
            include_packs=("frontend-essential",),
            exclude_packs=("project-baseline",),
        )


def test_registry_contains_declared_workflows_and_packs() -> None:
    registry = load_registry()

    assert set(registry.workflows) >= {"none", "gsd"}
    assert set(registry.packs) >= {
        "project-baseline",
        "quality-basic",
        "python-fastapi",
        "rag-python",
        "java-spring",
        "frontend-essential",
    }


def test_pack_order_cycle_has_clear_error() -> None:
    registry = Registry(
        sources={},
        workflows={},
        components={},
        packs={
            "a": PackSpec(pack_id="a", version=1, description="", requires=("b",)),
            "b": PackSpec(pack_id="b", version=1, description="", requires=("a",)),
        },
        profiles={},
    )

    with pytest.raises(ConfigError, match="pack dependency cycle"):
        resolve_pack_order(registry, ("a", "b"))


def test_pack_conflict_has_clear_error() -> None:
    registry = Registry(
        sources={},
        workflows={},
        components={},
        packs={
            "a": PackSpec(pack_id="a", version=1, description="", conflicts=("b",)),
            "b": PackSpec(pack_id="b", version=1, description=""),
        },
        profiles={},
    )

    with pytest.raises(ConfigError, match="conflicts with pack b"):
        resolve_pack_order(registry, ("a", "b"))
