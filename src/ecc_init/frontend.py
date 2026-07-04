from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .detect import detect_project


FRONTEND_LIFECYCLE_COMMANDS = (
    "/gsd-discuss-phase N",
    "/gsd-ui-phase N",
    "/gsd-plan-phase N",
    "/gsd-execute-phase N",
    "/gsd-verify-work N",
    "/gsd-ui-review N",
)


@dataclass(frozen=True)
class FrontendToolStatus:
    tool_id: str
    detected: bool
    detail: str


def _load_package_json(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _dependency_names(package_json: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = package_json.get(key, {})
        if isinstance(value, dict):
            names.update(str(name) for name in value)
    return names


def _script_values(package_json: dict[str, Any]) -> list[str]:
    scripts = package_json.get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    return [str(value) for value in scripts.values()]


def is_frontend_project(project_root: Path | None = None) -> bool:
    root = (project_root or Path.cwd()).resolve()
    stacks = set(detect_project(root).stacks)
    return bool({"react", "typescript"} & stacks)


def _has_gsd_browser_config(root: Path) -> bool:
    config_path = root / ".planning" / "config.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    tools = payload.get("tools")
    has_tools_entry = isinstance(tools, dict) and "gsd_browser" in tools
    return any(key in payload for key in ("browser", "gsd_browser")) or has_tools_entry


def detect_frontend_tools(project_root: Path | None = None) -> list[FrontendToolStatus]:
    root = (project_root or Path.cwd()).resolve()
    package_json = _load_package_json(root)
    deps = _dependency_names(package_json)
    scripts = _script_values(package_json)

    playwright_config = any(
        (root / name).exists()
        for name in (
            "playwright.config.ts",
            "playwright.config.js",
            "playwright.config.mjs",
            "playwright.config.cjs",
        )
    )
    playwright = "@playwright/test" in deps or "playwright" in deps or playwright_config
    vercel = "vercel" in deps or (root / "vercel.json").exists() or any("vercel" in script for script in scripts)
    gsd_browser = _has_gsd_browser_config(root)

    return [
        FrontendToolStatus(
            "playwright",
            playwright,
            "detected" if playwright else "not detected; optional visual verification tool",
        ),
        FrontendToolStatus("vercel", vercel, "detected" if vercel else "not detected; optional deployment adapter"),
        FrontendToolStatus(
            "gsd-browser",
            gsd_browser,
            "detected" if gsd_browser else "not detected; configure through GSD when available",
        ),
    ]


def frontend_doctor_checks(project_root: Path | None = None) -> list[tuple[str, bool, str]]:
    root = (project_root or Path.cwd()).resolve()
    frontend = is_frontend_project(root)
    checks: list[tuple[str, bool, str]] = [
        ("Frontend project", True, "detected" if frontend else "not detected"),
    ]
    for status in detect_frontend_tools(root):
        label = {
            "playwright": "Frontend Playwright",
            "vercel": "Frontend Vercel",
            "gsd-browser": "Frontend GSD Browser",
        }[status.tool_id]
        checks.append((label, True, status.detail if frontend else "not applicable"))
    return checks
