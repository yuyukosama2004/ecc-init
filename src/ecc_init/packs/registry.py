from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..core.models import ComponentSpec, PackSpec, SourceSpec, WorkflowSpec
from ..errors import ConfigError
from ..resources import read_resource_text


@dataclass(frozen=True)
class ProfileSpec:
    profile_id: str
    workflow: str
    packs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "workflow": self.workflow,
            "packs": list(self.packs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileSpec":
        return cls(
            profile_id=str(data["profile_id"]),
            workflow=str(data["workflow"]),
            packs=tuple(str(item) for item in data.get("packs", [])),
        )


@dataclass(frozen=True)
class Registry:
    sources: dict[str, SourceSpec]
    workflows: dict[str, WorkflowSpec]
    components: dict[str, ComponentSpec]
    packs: dict[str, PackSpec]
    profiles: dict[str, ProfileSpec]


def _load_items(payload: dict[str, Any], key: str, id_key: str, factory) -> dict[str, Any]:
    raw_items = payload.get(key)
    if not isinstance(raw_items, list):
        raise ConfigError(f"registry.json: {key} must be a list")
    loaded: dict[str, Any] = {}
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            raise ConfigError(f"registry.json: {key}[{index}] must be an object")
        try:
            parsed = factory(item)
            item_id = str(item[id_key])
        except KeyError as exc:
            raise ConfigError(f"registry.json: {key}[{index}] missing {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"registry.json: invalid {key}[{index}]: {exc}") from exc
        if item_id in loaded:
            raise ConfigError(f"registry.json: duplicate {id_key} {item_id}")
        loaded[item_id] = parsed
    return loaded


def _validate_references(registry: Registry) -> Registry:
    for workflow in registry.workflows.values():
        if workflow.source_id and workflow.source_id not in registry.sources:
            raise ConfigError(f"workflow {workflow.workflow_id} references unknown source {workflow.source_id}")
    for component in registry.components.values():
        if component.source_id not in registry.sources:
            raise ConfigError(f"component {component.component_id} references unknown source {component.source_id}")
    for pack in registry.packs.values():
        for component_id in pack.components:
            if component_id not in registry.components:
                raise ConfigError(f"pack {pack.pack_id} references unknown component {component_id}")
        for required in pack.requires:
            if required not in registry.packs:
                raise ConfigError(f"pack {pack.pack_id} requires unknown pack {required}")
        for conflict in pack.conflicts:
            if conflict not in registry.packs:
                raise ConfigError(f"pack {pack.pack_id} conflicts with unknown pack {conflict}")
    for profile in registry.profiles.values():
        if profile.workflow not in registry.workflows:
            raise ConfigError(f"profile {profile.profile_id} references unknown workflow {profile.workflow}")
        for pack_id in profile.packs:
            if pack_id not in registry.packs:
                raise ConfigError(f"profile {profile.profile_id} references unknown pack {pack_id}")
    return registry


def parse_registry(payload: dict[str, Any]) -> Registry:
    if payload.get("schema_version") != 2:
        raise ConfigError("registry.json: schema_version must be 2")
    registry = Registry(
        sources=_load_items(payload, "sources", "source_id", SourceSpec.from_dict),
        workflows=_load_items(payload, "workflows", "workflow_id", WorkflowSpec.from_dict),
        components=_load_items(payload, "components", "component_id", ComponentSpec.from_dict),
        packs=_load_items(payload, "packs", "pack_id", PackSpec.from_dict),
        profiles=_load_items(payload, "profiles", "profile_id", ProfileSpec.from_dict),
    )
    return _validate_references(registry)


def load_registry() -> Registry:
    return parse_registry(json.loads(read_resource_text("registry/registry.json")))
