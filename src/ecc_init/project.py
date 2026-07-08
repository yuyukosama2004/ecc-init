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


def _agent_policy_text() -> str:
    """Generate natural-language agent usage constraints for CLAUDE.md.

    These rules are read by Claude Code and constrain sub-agent spawning
    in every session. The default limits are conservative and may be
    tightened further by editing CLAUDE.md directly.
    """
    return (
        "- **禁止使用子代理**：纯问答、单文件小修改、文档查阅、简单格式转换、"
        "已明确指定具体实现的单步操作。\n"
        "- **最多 1 个子代理**：涉及 2–5 个文件的局部重构、单模块 bug 修复、"
        "为单一接口补充测试。\n"
        "- **最多 3 个并发子代理**：跨模块架构调整、多表 schema 变更、"
        "涉及前后端协同的功能开发、需要同时验证多个独立假设的探索任务。\n"
        "- 上述并发上限为硬性约束，不得以\"提高效率\"为由突破。"
        "接近上限时必须串行复用而非新建代理。\n"
        "- 使用子代理前，先在回复中说明任务的复杂度级别和预计代理数，"
        "获得用户默许后再执行。"
    )


def render_project_section(template: str, detection: DetectionResult) -> str:
    stacks = "、".join(detection.stacks) if detection.stacks else "未识别（由 Claude 根据代码进一步判断）"
    skills = "\n".join(f"- `{stack}-patterns`（如已安装）" for stack in detection.stacks)
    if not skills:
        skills = "- 暂无自动匹配的技术栈 Skill"
    commands = "\n".join(f"- {label}：`{command}`" for label, command in detection.commands.items())
    if not commands:
        commands = "- 暂未从配置文件识别；执行前读取项目实际配置"
    return (
        template.replace("{{DETECTED_STACKS}}", stacks)
        .replace("{{PROJECT_SKILLS}}", skills)
        .replace("{{PROJECT_COMMANDS}}", commands)
        .replace("{{AGENT_POLICY}}", _agent_policy_text())
    )


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
