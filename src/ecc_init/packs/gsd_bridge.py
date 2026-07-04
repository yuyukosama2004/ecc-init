from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from ..errors import ConfigError
from ..paths import AppPaths
from ..util import write_json_atomic
from .registry import Registry, load_registry
from .resolver import resolve_pack_order


AGENT_TYPE_MAP = {
    "executor": "gsd-executor",
    "reviewer": "gsd-code-reviewer",
    "security-reviewer": "gsd-code-reviewer",
    "explorer": "gsd-codebase-mapper",
    "planner": "gsd-planner",
    "verifier": "gsd-verifier",
}


@dataclass(frozen=True)
class AgentPolicyProfile:
    profile_id: str
    hard_config: dict[str, Any]
    advisory: dict[str, Any] = field(default_factory=dict)


POLICY_PROFILES: dict[str, AgentPolicyProfile] = {
    "minimal": AgentPolicyProfile(
        "minimal",
        {
            "parallelization": {
                "enabled": False,
                "plan_level": False,
                "task_level": False,
                "skip_checkpoints": False,
                "max_concurrent_agents": 1,
                "min_plans_for_parallel": 99,
            },
            "workflow": {
                "use_worktrees": False,
                "subagent_timeout": 300000,
                "node_repair_budget": 1,
            },
        },
        {"phase_agent_budget": 2, "token_budget": "user-defined"},
    ),
    "default": AgentPolicyProfile(
        "default",
        {
            "parallelization": {
                "enabled": True,
                "plan_level": True,
                "task_level": False,
                "skip_checkpoints": False,
                "max_concurrent_agents": 3,
                "min_plans_for_parallel": 2,
            },
            "workflow": {
                "use_worktrees": True,
                "subagent_timeout": 300000,
                "node_repair_budget": 1,
            },
        },
        {"phase_agent_budget": 8, "token_budget": "advisory-only"},
    ),
    "frontend": AgentPolicyProfile(
        "frontend",
        {
            "parallelization": {
                "enabled": True,
                "plan_level": True,
                "task_level": False,
                "skip_checkpoints": False,
                "max_concurrent_agents": 3,
                "min_plans_for_parallel": 2,
            },
            "workflow": {
                "use_worktrees": True,
                "subagent_timeout": 300000,
                "node_repair_budget": 1,
                "ui_review": True,
            },
        },
        {"phase_agent_budget": 8, "ui_review_budget": "advisory-only"},
    ),
    "high-assurance": AgentPolicyProfile(
        "high-assurance",
        {
            "parallelization": {
                "enabled": True,
                "plan_level": True,
                "task_level": False,
                "skip_checkpoints": False,
                "max_concurrent_agents": 2,
                "min_plans_for_parallel": 2,
            },
            "workflow": {
                "use_worktrees": True,
                "subagent_timeout": 300000,
                "node_repair_budget": 1,
                "security_enforcement": True,
                "security_block_on": "high",
            },
        },
        {"phase_agent_budget": 6, "review_rounds": 2},
    ),
}


@dataclass(frozen=True)
class ConfigSyncReport:
    config_path: Path
    initialized: bool
    changed: bool
    before: dict[str, Any]
    after: dict[str, Any]
    hard_config: dict[str, Any]
    advisory: dict[str, Any]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_path": str(self.config_path),
            "initialized": self.initialized,
            "changed": self.changed,
            "before": self.before,
            "after": self.after,
            "hard_config": self.hard_config,
            "advisory": self.advisory,
            "warnings": list(self.warnings),
        }


def deep_merge_missing(existing: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing)
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = deepcopy(value)
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge_missing(merged[key], value)
    return merged


def merge_agent_skills(existing: dict[str, Any], additions: dict[str, list[str]]) -> dict[str, Any]:
    merged = deepcopy(existing)
    current = merged.setdefault("agent_skills", {})
    if not isinstance(current, dict):
        raise ConfigError("agent_skills must be an object")
    for agent_type, entries in sorted(additions.items()):
        values = current.setdefault(agent_type, [])
        if not isinstance(values, list):
            raise ConfigError(f"agent_skills.{agent_type} must be a list")
        for entry in entries:
            if entry not in values:
                values.append(entry)
    return merged


def _safe_project_entry(entry: str) -> bool:
    path = PurePosixPath(entry)
    return not path.is_absolute() and ".." not in path.parts and bool(path.parts)


def _skill_entry_for_name(name: str, registry: Registry) -> tuple[str, str]:
    for component in registry.components.values():
        if component.install_name == name:
            if component.target_scope == "global":
                return f"global:{name}", component.target_scope
            if component.target_scope == "project":
                return str(PurePosixPath(component.target_subdir).parent), component.target_scope
    return f".claude/skills/{name}", "project"


def _entry_exists(paths: AppPaths, entry: str, scope: str) -> bool:
    if scope == "global" and entry.startswith("global:"):
        name = entry.removeprefix("global:")
        return (paths.global_skills / name / "SKILL.md").exists()
    if scope == "project":
        if not _safe_project_entry(entry):
            raise ConfigError(f"unsafe agent skill path: {entry}")
        return (paths.project_root / entry / "SKILL.md").exists()
    return False


def pack_agent_skill_additions(
    paths: AppPaths,
    registry: Registry,
    packs: list[str],
) -> tuple[dict[str, list[str]], tuple[str, ...]]:
    additions: dict[str, list[str]] = {}
    warnings: list[str] = []
    for pack_id in packs:
        pack = registry.packs[pack_id]
        for role, skill_names in pack.gsd_agent_skills.items():
            agent_type = AGENT_TYPE_MAP.get(role, role if role.startswith("gsd-") else f"gsd-{role}")
            for skill_name in skill_names:
                entry, scope = _skill_entry_for_name(skill_name, registry)
                if not _entry_exists(paths, entry, scope):
                    warnings.append(f"missing SKILL.md for {entry}; skipped {agent_type}")
                    continue
                additions.setdefault(agent_type, [])
                if entry not in additions[agent_type]:
                    additions[agent_type].append(entry)
    return additions, tuple(warnings)


def pack_config_defaults(registry: Registry, packs: list[str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for pack_id in packs:
        defaults = deep_merge_missing(defaults, registry.packs[pack_id].gsd_config_defaults)
    return defaults


def remove_pack_agent_skills(config: dict[str, Any], registry: Registry, pack_id: str) -> dict[str, Any]:
    if pack_id not in registry.packs:
        raise ConfigError(f"unknown pack: {pack_id}")
    remove_entries: set[str] = set()
    for skill_names in registry.packs[pack_id].gsd_agent_skills.values():
        for skill_name in skill_names:
            entry, _scope = _skill_entry_for_name(skill_name, registry)
            remove_entries.add(entry)
    updated = deepcopy(config)
    skills = updated.get("agent_skills")
    if not isinstance(skills, dict):
        return updated
    for agent_type, entries in list(skills.items()):
        if isinstance(entries, list):
            skills[agent_type] = [entry for entry in entries if entry not in remove_entries]
            if not skills[agent_type]:
                del skills[agent_type]
    return updated


def _load_config(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"无法读取 GSD config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"GSD config must be a JSON object: {path}")
    return payload


def build_gsd_config(
    project_root: Path | None = None,
    *,
    profile_id: str = "default",
    packs: list[str] | None = None,
) -> ConfigSyncReport:
    paths = AppPaths.build(project_root)
    config_path = paths.project_root / ".planning" / "config.json"
    initialized = config_path.exists()
    registry = load_registry()
    policy = POLICY_PROFILES.get(profile_id)
    if policy is None:
        raise ConfigError(f"unknown agent policy profile: {profile_id}")
    if packs is None:
        profile = registry.profiles.get(profile_id if profile_id in registry.profiles else "default")
        if profile is None:
            raise ConfigError(f"unknown profile: {profile_id}")
        packs = resolve_pack_order(registry, profile.packs)
    else:
        packs = resolve_pack_order(registry, packs)

    before = _load_config(config_path) if initialized else {}
    additions, warnings = pack_agent_skill_additions(paths, registry, packs)
    hard_config = deep_merge_missing(policy.hard_config, pack_config_defaults(registry, packs))
    with_defaults = deep_merge_missing(before, hard_config)
    after = merge_agent_skills(with_defaults, additions)
    if not initialized:
        warnings = ("GSD config not initialized; sync report generated without writing.", *warnings)
    return ConfigSyncReport(
        config_path=config_path,
        initialized=initialized,
        changed=after != before,
        before=before,
        after=after,
        hard_config=hard_config,
        advisory=policy.advisory,
        warnings=warnings,
    )


def sync_gsd_config(
    project_root: Path | None = None,
    *,
    profile_id: str = "default",
    packs: list[str] | None = None,
    dry_run: bool = False,
) -> ConfigSyncReport:
    report = build_gsd_config(project_root, profile_id=profile_id, packs=packs)
    if report.initialized and report.changed and not dry_run:
        write_json_atomic(report.config_path, report.after)
    return report
