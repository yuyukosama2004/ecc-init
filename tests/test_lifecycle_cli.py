import io
import json
import sys
from pathlib import Path

import pytest

from ecc_init.cli import main


@pytest.mark.parametrize(
    "argv",
    [
        ["init", "--help"],
        ["plan", "--help"],
        ["apply", "--help"],
        ["status", "--help"],
        ["update", "--help"],
        ["doctor", "--help"],
        ["rollback", "--help"],
        ["remove", "--help"],
        ["migrate", "--help"],
        ["sync-gsd", "--help"],
        ["packs", "--help"],
        ["sources", "--help"],
        ["workflow", "--help"],
    ],
)
def test_primary_commands_have_help(argv, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_status_json_is_machine_parseable(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["status", str(project), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["project_root"] == str(project.resolve())
    assert isinstance(payload["detected_stacks"], list)


def test_status_json_writes_utf8_when_stdout_text_encoding_is_limited(tmp_path: Path, monkeypatch) -> None:
    class CharmapStdout:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def write(self, text: str) -> int:
            text.encode("cp1252")
            return len(text)

        def flush(self) -> None:
            return None

    project = tmp_path / "demo"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
    stream = CharmapStdout()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))
    monkeypatch.setattr(sys, "stdout", stream)

    assert main(["status", str(project), "--json"]) == 0
    payload = json.loads(stream.buffer.getvalue().decode("utf-8"))

    assert "测试命令" in payload["commands"]


def test_doctor_json_uses_pass_warn_fail_statuses(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    result = main(["doctor", str(project), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert result in {0, 3}
    assert payload["summary"]["PASS"] >= 1
    assert {item["status"] for item in payload["checks"]} <= {"PASS", "WARN", "FAIL"}


def test_update_check_json_is_dry_run_and_does_not_write(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["update", str(project), "--check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["install_plan"]["workflow"] == "gsd"
    assert not (project / ".planning" / "config.json").exists()


def test_init_dry_run_json_example_does_not_write(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["init", str(project), "--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["workflow"] == "gsd"
    assert not (project / ".claude").exists()
    assert not (project / "docs").exists()


def test_init_defaults_to_gsd_preview_without_legacy_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["init", str(project), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["workflow"] == "gsd"
    assert not (project / ".claude").exists()
    assert not (project / "CLAUDE.md").exists()
    assert not (tmp_path / "claude-home" / "skills" / "task-planning").exists()


def test_legacy_init_requires_explicit_flag(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["init", str(project), "--legacy", "--offline"]) == 0

    assert (project / ".claude" / "ecc-init-state.json").exists()
    assert (tmp_path / "claude-home" / "skills" / "task-planning" / "SKILL.md").exists()


def test_remove_pack_json_defaults_to_dry_run(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    original = {
        "agent_skills": {
            "gsd-executor": [
                ".claude/skills/python-patterns",
                ".claude/skills/fastapi-patterns",
                ".claude/skills/other",
            ]
        }
    }
    config.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["remove", str(project), "--pack", "python-fastapi", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["dry_run"] is True
    assert payload["changed"] is True
    assert json.loads(config.read_text(encoding="utf-8")) == original


def test_remove_pack_yes_updates_config_and_receipt(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "demo"
    config = project / ".planning" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "agent_skills": {
                    "gsd-executor": [
                        ".claude/skills/python-patterns",
                        ".claude/skills/fastapi-patterns",
                        ".claude/skills/other",
                    ],
                    "gsd-planner": [
                        ".claude/skills/python-patterns",
                        ".claude/skills/fastapi-patterns",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ECC_INIT_HOME", str(tmp_path / "ecc-home"))
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-home"))

    assert main(["remove", str(project), "--pack", "python-fastapi", "--yes", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    written = json.loads(config.read_text(encoding="utf-8"))
    receipts = list((tmp_path / "ecc-home" / "operations").glob("*/receipt.json"))

    assert payload["dry_run"] is False
    assert payload["applied"] is True
    assert payload["operation_id"]
    assert written["agent_skills"]["gsd-executor"] == [".claude/skills/other"]
    assert "gsd-planner" not in written["agent_skills"]
    assert len(receipts) == 1


def test_default_errors_hide_traceback_and_debug_reraises(tmp_path: Path, capsys) -> None:
    assert main(["plan", str(tmp_path), "--profile", "missing"]) == 1
    err = capsys.readouterr().err

    assert "ecc-init failed:" in err
    assert "Traceback" not in err
    with pytest.raises(Exception):
        main(["--debug", "plan", str(tmp_path), "--profile", "missing"])
