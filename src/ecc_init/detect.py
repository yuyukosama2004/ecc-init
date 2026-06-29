from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STACK_ORDER = [
    "python",
    "fastapi",
    "langchain",
    "langgraph",
    "typescript",
    "react",
    "java",
    "spring-boot",
]

IGNORED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
}


@dataclass(frozen=True)
class DetectionResult:
    stacks: list[str]
    evidence: dict[str, list[str]]
    commands: dict[str, str]


def _add(evidence: dict[str, list[str]], stack: str, reason: str) -> None:
    values = evidence.setdefault(stack, [])
    if reason not in values:
        values.append(reason)


def _read_limited(path: Path, limit: int = 200_000) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def _iter_source_files(root: Path, suffixes: set[str], limit: int = 120) -> Iterable[Path]:
    count = 0
    for path in root.rglob("*"):
        if count >= limit:
            return
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        count += 1
        yield path


def _parse_package_json(path: Path, evidence: dict[str, list[str]], commands: dict[str, str]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    deps: dict[str, object] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = data.get(key, {})
        if isinstance(value, dict):
            deps.update(value)

    if any(name in deps for name in ("typescript", "ts-node", "tsx")) or path.parent.joinpath("tsconfig.json").exists():
        _add(evidence, "typescript", "package.json/tsconfig.json")
    if any(name in deps for name in ("react", "react-dom", "next", "@vitejs/plugin-react")):
        _add(evidence, "react", "package.json 中包含 React 依赖")
        _add(evidence, "typescript", "React 项目通常使用 TS/JS；检测到 React") if "typescript" in deps else None

    scripts = data.get("scripts", {})
    if isinstance(scripts, dict):
        for preferred, label in (
            ("dev", "启动命令"),
            ("start", "启动命令"),
            ("test", "测试命令"),
            ("lint", "Lint 命令"),
            ("typecheck", "类型检查"),
            ("build", "构建命令"),
        ):
            if preferred in scripts and label not in commands:
                commands[label] = f"npm run {preferred}"


def _parse_python_configs(root: Path, evidence: dict[str, list[str]], commands: dict[str, str]) -> str:
    texts: list[str] = []
    for name in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "Pipfile", "uv.lock", "poetry.lock"):
        path = root / name
        if path.exists():
            _add(evidence, "python", name)
            texts.append(_read_limited(path))
    combined = "\n".join(texts).lower()
    if "fastapi" in combined:
        _add(evidence, "fastapi", "Python 依赖中包含 fastapi")
    if "langchain" in combined:
        _add(evidence, "langchain", "Python 依赖中包含 langchain")
    if "langgraph" in combined:
        _add(evidence, "langgraph", "Python 依赖中包含 langgraph")

    if evidence.get("python"):
        commands.setdefault("测试命令", "pytest -q")
        if "ruff" in combined:
            commands.setdefault("Lint 命令", "ruff check .")
        if "pyright" in combined:
            commands.setdefault("类型检查", "pyright .")
        elif "mypy" in combined:
            commands.setdefault("类型检查", "mypy .")
    return combined


def _parse_java_configs(root: Path, evidence: dict[str, list[str]], commands: dict[str, str]) -> str:
    texts: list[str] = []
    config_names = ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
    for name in config_names:
        path = root / name
        if path.exists():
            _add(evidence, "java", name)
            texts.append(_read_limited(path))
    combined = "\n".join(texts).lower()
    if "spring-boot" in combined or "org.springframework.boot" in combined:
        _add(evidence, "spring-boot", "构建文件中包含 Spring Boot")
    if (root / "mvnw.cmd").exists() or (root / "mvnw").exists():
        commands.setdefault("测试命令", ".\\mvnw.cmd test" if (root / "mvnw.cmd").exists() else "./mvnw test")
    elif (root / "gradlew.bat").exists() or (root / "gradlew").exists():
        commands.setdefault("测试命令", ".\\gradlew.bat test" if (root / "gradlew.bat").exists() else "./gradlew test")
    elif (root / "pom.xml").exists():
        commands.setdefault("测试命令", "mvn test")
    return combined


def detect_project(root: Path) -> DetectionResult:
    evidence: dict[str, list[str]] = {}
    commands: dict[str, str] = {}

    python_config = _parse_python_configs(root, evidence, commands)
    java_config = _parse_java_configs(root, evidence, commands)

    package_json = root / "package.json"
    if package_json.exists():
        _parse_package_json(package_json, evidence, commands)

    if (root / "tsconfig.json").exists():
        _add(evidence, "typescript", "tsconfig.json")

    source_patterns = {
        "fastapi": re.compile(r"\bfrom\s+fastapi\b|\bimport\s+fastapi\b", re.I),
        "langchain": re.compile(r"\bfrom\s+langchain|\bimport\s+langchain", re.I),
        "langgraph": re.compile(r"\bfrom\s+langgraph|\bimport\s+langgraph", re.I),
    }
    for path in _iter_source_files(root, {".py"}):
        _add(evidence, "python", f"检测到 Python 源文件：{path.relative_to(root)}")
        text = _read_limited(path, 80_000)
        for stack, pattern in source_patterns.items():
            if pattern.search(text):
                _add(evidence, stack, f"源代码导入：{path.relative_to(root)}")

    for path in _iter_source_files(root, {".ts", ".tsx"}):
        _add(evidence, "typescript", f"检测到 TypeScript 源文件：{path.relative_to(root)}")
        if path.suffix.lower() == ".tsx" or re.search(r"from\s+['\"]react['\"]", _read_limited(path, 80_000)):
            _add(evidence, "react", f"检测到 React/TSX：{path.relative_to(root)}")

    for path in _iter_source_files(root, {".java"}):
        _add(evidence, "java", f"检测到 Java 源文件：{path.relative_to(root)}")
        if re.search(r"org\.springframework|@SpringBootApplication", _read_limited(path, 80_000)):
            _add(evidence, "spring-boot", f"检测到 Spring Boot 源码：{path.relative_to(root)}")

    # 避免只有依赖锁文件时漏掉顶层语言判断。
    if any(key in evidence for key in ("fastapi", "langchain", "langgraph")):
        _add(evidence, "python", "由 Python 框架依赖推断")
    if "spring-boot" in evidence:
        _add(evidence, "java", "由 Spring Boot 依赖推断")

    stacks = [stack for stack in STACK_ORDER if evidence.get(stack)]
    return DetectionResult(stacks=stacks, evidence=evidence, commands=commands)
