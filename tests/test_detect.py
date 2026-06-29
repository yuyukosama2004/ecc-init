from pathlib import Path

from ecc_init.detect import detect_project


def test_detect_fastapi_langgraph_react_typescript(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi", "langchain", "langgraph"]\n',
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"latest","typescript":"latest"},"scripts":{"test":"vitest"}}',
        encoding="utf-8",
    )
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")

    result = detect_project(tmp_path)

    assert result.stacks == ["python", "fastapi", "langchain", "langgraph", "typescript", "react"]
    assert result.commands["测试命令"] in {"pytest -q", "npm run test"}


def test_detect_spring_boot(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        '<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>',
        encoding="utf-8",
    )
    result = detect_project(tmp_path)
    assert "java" in result.stacks
    assert "spring-boot" in result.stacks
