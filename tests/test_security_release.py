import io
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from ecc_init.backup import BackupSession, rollback_backup
from ecc_init.errors import SourceError
from ecc_init.packs import load_registry
from ecc_init.resources import read_resource_text
from ecc_init.sources import project_directory, safe_extract_zip
from ecc_init.workflows.base import SubprocessRunner


def _zip_bytes(path: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(path, content)
    return buffer.getvalue()


def test_safe_extract_zip_rejects_absolute_member(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    archive.write_bytes(_zip_bytes("/escape.txt", b"bad"))

    with pytest.raises(SourceError, match="unsafe archive member"):
        safe_extract_zip(archive, tmp_path / "out")


def test_safe_extract_zip_rejects_symlink_member(tmp_path: Path) -> None:
    archive = tmp_path / "bad-symlink.zip"
    info = zipfile.ZipInfo("link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(info, "target")

    with pytest.raises(SourceError, match="unsafe archive symlink"):
        safe_extract_zip(archive, tmp_path / "out")


def test_project_directory_rejects_symlink_escape(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlink is not available on this platform")
    source = tmp_path / "source"
    target = tmp_path / "target"
    outside = tmp_path / "outside.txt"
    source.mkdir()
    outside.write_text("outside\n", encoding="utf-8")
    try:
        os.symlink(outside, source / "escape.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this platform")

    with pytest.raises(SourceError, match="unsafe projection symlink"):
        project_directory(source, target, include=("*.md",))


def test_backup_rollback_deletes_created_symlink_without_following_target(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlink is not available on this platform")
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "external.txt"
    external.write_text("keep\n", encoding="utf-8")
    link = project / "link.txt"

    backup = BackupSession(tmp_path / "backups", project)
    backup.record_before_change(link)
    try:
        os.symlink(external, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this platform")
    backup_id = backup.finish()

    assert backup_id is not None
    restored_id, restored = rollback_backup(tmp_path / "backups", backup_id)

    assert restored_id == backup_id
    assert restored == 1
    assert not link.exists()
    assert external.read_text(encoding="utf-8") == "keep\n"


def test_subprocess_runner_uses_argument_list_without_shell(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SubprocessRunner().run(["tool", "literal;not-shell"], cwd=tmp_path)

    assert result.ok
    assert calls[0][0] == ["tool", "literal;not-shell"]
    assert "shell" not in calls[0][1]
    assert calls[0][1]["check"] is False


def test_registry_projection_resources_exist_and_no_redistributed_anthropic_content() -> None:
    registry = load_registry()
    for component in registry.components.values():
        for resource in component.projection_include:
            read_resource_text(resource)
    source = registry.sources["anthropic-frontend-policy"]

    assert source.kind == "optional_policy"
    assert not source.path
    assert source.repository == "https://docs.anthropic.com/claude-code"


def test_release_scripts_detect_required_wheel_contents(tmp_path: Path) -> None:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import check_wheel_contents

        wheel = tmp_path / "ecc_init-0.2.0a0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            for suffix in check_wheel_contents.REQUIRED_SUFFIXES:
                archive.writestr(suffix, "x")
            archive.writestr("ecc_init-0.2.0a0.dist-info/METADATA", "Name: ecc-init\n")
            archive.writestr("ecc_init-0.2.0a0.dist-info/entry_points.txt", "[console_scripts]\necc-init = ecc_init.cli:main\n")

        check_wheel_contents.check_wheel(wheel)
    finally:
        try:
            sys.path.remove(str(scripts_dir))
        except ValueError:
            pass


def test_cli_smoke_falls_back_to_module_when_console_script_is_absent(tmp_path: Path) -> None:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import cli_smoke

        venv_dir = tmp_path / "venv"
        python = cli_smoke._venv_python(venv_dir)
        python.parent.mkdir(parents=True)
        python.write_text("", encoding="utf-8")

        assert cli_smoke._ecc_command(venv_dir, python) == [str(python), "-m", "ecc_init.cli"]
    finally:
        try:
            sys.path.remove(str(scripts_dir))
        except ValueError:
            pass


def test_release_version_metadata_matches_package() -> None:
    import re
    import ecc_init

    content = Path("pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"$', content, flags=re.MULTILINE)

    assert version is not None
    assert version.group(1) == ecc_init.__version__ == "0.2.0a0"


def test_phase_11_release_docs_and_ci_files_exist() -> None:
    required = [
        ".github/workflows/ci.yml",
        ".github/workflows/nightly-network-e2e.yml",
        "ARCHITECTURE.md",
        "docs/e2e/0.2.0-alpha.md",
        "MIGRATION.md",
        "NOTICE.md",
        "SECURITY.md",
        "SOURCE_POLICY.md",
        "scripts/check_wheel_contents.py",
        "scripts/cli_smoke.py",
        "scripts/release_dry_run.py",
    ]

    for path in required:
        assert Path(path).is_file(), path

    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "windows-latest" in ci
    assert "ubuntu-latest" in ci
    assert "macos-latest" in ci
    assert "PYTHONPATH: src" in ci
    assert "ECC_INIT_NETWORK_E2E: \"0\"" in ci
    assert "PIPX_BIN_DIR" in ci
    assert "pytest==8.4.1" in ci
    assert "python -m pip install -e . --no-build-isolation" in ci
    assert "--ignore=tests/test_network_e2e.py" in ci
    assert "python -m pip wheel" in ci
    assert "scripts/cli_smoke.py" in ci

    dry_run = Path("scripts/release_dry_run.py").read_text(encoding="utf-8")
    assert "pip==25.1.1" in dry_run
    assert "setuptools==80.9.0" in dry_run
    assert "wheel==0.45.1" in dry_run
