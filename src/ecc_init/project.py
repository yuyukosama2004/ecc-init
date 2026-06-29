from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .detect import DetectionResult


IMPORTANT_FILES = (
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
)


def structure_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for name in IMPORTANT_FILES:
        path = root / name
        if path.exists() and path.is_file():
            stat = path.stat()
            digest.update(name.encode("utf-8"))
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
    top_dirs = sorted(path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))
    digest.update("|".join(top_dirs).encode("utf-8"))
    return digest.hexdigest()


def render_project_section(template: str, detection: DetectionResult) -> str:
    stacks = "、".join(detection.stacks) if detection.stacks else "未识别（由 Claude 根据代码进一步判断）"
    skills = "\n".join(f"- `{stack}-patterns`（如已安装）" for stack in detection.stacks)
    if not skills:
        skills = "- 暂无自动匹配的技术栈 Skill"
    commands = "\n".join(f"- {label}：`{command}`" for label, command in detection.commands.items())
    if not commands:
        commands = "- 暂未从配置文件识别；执行前读取项目实际配置"
    return template.replace("{{DETECTED_STACKS}}", stacks).replace("{{PROJECT_SKILLS}}", skills).replace("{{PROJECT_COMMANDS}}", commands)


def render_project_overview(template: str, detection: DetectionResult) -> str:
    stacks = "、".join(detection.stacks) if detection.stacks else "待分析"
    evidence_lines: list[str] = []
    for stack in detection.stacks:
        reasons = detection.evidence.get(stack, [])[:4]
        evidence_lines.append(f"- **{stack}**：" + "；".join(reasons))
    evidence = "\n".join(evidence_lines) if evidence_lines else "- 尚未完成代码导读。"
    commands = "\n".join(f"- {label}：`{command}`" for label, command in detection.commands.items())
    if not commands:
        commands = "- 待代码导读后补充。"
    return (
        template.replace("{{DETECTED_STACKS}}", stacks)
        .replace("{{DETECTION_EVIDENCE}}", evidence)
        .replace("{{PROJECT_COMMANDS}}", commands)
    )


def package_scripts(root: Path) -> dict[str, str]:
    path = root / "package.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}
