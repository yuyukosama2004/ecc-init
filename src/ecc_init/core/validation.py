from __future__ import annotations

from typing import Any

from ..errors import ConfigError


def validate_legacy_manifest(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigError("manifest.json 必须是 JSON object")
    if data.get("version") != 1:
        raise ConfigError("manifest.json: version 必须为 1")
    for key in ("global_skills", "project_skills"):
        if not isinstance(data.get(key), list):
            raise ConfigError(f"manifest.json: {key} 必须是 list")
    for index, item in enumerate(data["global_skills"]):
        if not isinstance(item, dict) or not item.get("name") or not item.get("resource"):
            raise ConfigError(f"manifest.json: global_skills[{index}] 缺少 name/resource")
    for index, item in enumerate(data["project_skills"]):
        missing = [key for key in ("stack", "name", "resource") if not item.get(key)] if isinstance(item, dict) else []
        if not isinstance(item, dict) or missing:
            fields = ", ".join(missing) if missing else "stack/name/resource"
            raise ConfigError(f"manifest.json: project_skills[{index}] 缺少 {fields}")
    return data
