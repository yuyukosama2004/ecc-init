from pathlib import Path

from ecc_init.paths import AppPaths
from ecc_init.workflows import GSD_PACKAGE, GSD_PINNED_VERSION, GsdInstallOptions, GsdWorkflowAdapter
from ecc_init.workflows.base import CommandResult


class FakeRunner:
    def __init__(self, node_version: str = "v22.0.0", npm_version: str = "10.0.0", install_returncode: int = 0):
        self.node_version = node_version
        self.npm_version = npm_version
        self.install_returncode = install_returncode
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: list[str], *, cwd: Path | None = None) -> CommandResult:
        self.calls.append(tuple(args))
        if args[-1] == "--version":
            tool = Path(args[0]).name.replace(".cmd", "") if args else ""
            if tool == "node":
                return CommandResult(tuple(args), 0, self.node_version + "\n", "")
            return CommandResult(tuple(args), 0, self.npm_version + "\n", "")
        return CommandResult(tuple(args), self.install_returncode, "installed\n", "")


def _which(name: str) -> str | None:
    normalized = name.removesuffix(".cmd")
    if normalized in {"node", "npx", "npm"}:
        return f"C:/tools/{name}"
    return None


def test_gsd_install_dry_run_plans_pinned_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    runner = FakeRunner()
    adapter = GsdWorkflowAdapter(runner)

    result = adapter.install(AppPaths.build(tmp_path), dry_run=True)

    assert result.status == "planned"
    command = result.commands[0].args
    assert command[0].replace("\\", "/").endswith(("npm", "npm.cmd"))
    assert command[1:] == ("install", "-g", f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}")
    assert result.logs == []
    assert runner.calls == []
    assert any(check.check_id == "node-version" and check.detail == "not checked during dry-run" for check in result.checks)
    assert any(check.check_id == "npm-version" and check.detail == "not checked during dry-run" for check in result.checks)
    assert any("install affects runtime configuration" in warning for warning in result.warnings)


def test_gsd_install_runs_only_after_environment_ok(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    # Isolate from real ~/.claude so _has_verified_markers does not
    # pick up a real GSD install on the developer's machine.
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude-isolated"))
    runner = FakeRunner()
    adapter = GsdWorkflowAdapter(runner)

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "installed_unverified"
    assert result.logs[0].args[1:3] == ("install", "-g")


def test_gsd_install_blocks_when_node_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", lambda name: None)
    runner = FakeRunner()
    adapter = GsdWorkflowAdapter(runner)

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked_environment"
    assert runner.calls == []
    assert any(check.check_id == "node-present" and not check.ok for check in result.checks)


def test_gsd_install_blocks_when_node_too_old(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    adapter = GsdWorkflowAdapter(FakeRunner(node_version="v20.0.0"))

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked_environment"
    assert any(check.check_id == "node-version" and not check.ok for check in result.checks)


def test_gsd_install_blocks_when_npm_too_old(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    adapter = GsdWorkflowAdapter(FakeRunner(npm_version="8.0.0"))

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked_environment"
    assert any(check.check_id == "npm-version" and not check.ok for check in result.checks)


def test_gsd_install_blocks_when_npm_missing(monkeypatch, tmp_path: Path) -> None:
    def _which_no_npm(name: str) -> str | None:
        normalized = name.removesuffix(".cmd")
        if normalized in {"node", "npx"}:
            return f"C:/tools/{name}"
        return None

    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which_no_npm)
    adapter = GsdWorkflowAdapter(FakeRunner())

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked_environment"
    assert any(check.check_id == "npm-present" and not check.ok for check in result.checks)


def test_gsd_install_blocks_when_npx_missing(monkeypatch, tmp_path: Path) -> None:
    def _which_no_npx(name: str) -> str | None:
        normalized = name.removesuffix(".cmd")
        if normalized in {"node", "npm"}:
            return f"C:/tools/{name}"
        return None

    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which_no_npx)
    adapter = GsdWorkflowAdapter(FakeRunner())

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked_environment"
    assert any(check.check_id == "npx-present" and not check.ok for check in result.checks)


def test_gsd_install_dry_run_does_not_execute_versions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    runner = FakeRunner()
    adapter = GsdWorkflowAdapter(runner)

    result = adapter.install(AppPaths.build(tmp_path), dry_run=True)

    assert result.status == "planned"
    assert runner.calls == []
    assert any(check.check_id == "node-version" and check.detail == "not checked during dry-run" for check in result.checks)
    assert any(check.check_id == "npm-version" and check.detail == "not checked during dry-run" for check in result.checks)


def test_gsd_local_project_command_uses_local_scope(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    adapter = GsdWorkflowAdapter(FakeRunner())

    result = adapter.install(
        AppPaths.build(tmp_path),
        GsdInstallOptions(scope="project", dry_run=True),
    )

    assert result.commands[0].args[1:4] == ("install", "-g", f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}")


def test_gsd_update_reuses_official_installer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    adapter = GsdWorkflowAdapter(FakeRunner())

    result = adapter.update(AppPaths.build(tmp_path), dry_run=True)

    assert result.commands[0].args[0].replace("\\", "/").endswith(("npm", "npm.cmd"))
    assert result.commands[0].args[1:3] == ("install", "-g")


def test_gsd_windows_command_suffix_is_preserved(monkeypatch) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.os.name", "nt")
    adapter = GsdWorkflowAdapter(FakeRunner())

    command = adapter.install_command()

    assert command.args[0] == "npm.cmd"


def test_gsd_inspect_and_remove_are_safe_strategy_only(tmp_path: Path) -> None:
    adapter = GsdWorkflowAdapter(FakeRunner())
    paths = AppPaths.build(tmp_path)

    missing = adapter.inspect(paths)
    remove = adapter.remove(paths)

    assert missing.status == "missing"
    assert remove.status == "planned"
    assert remove.logs == []
    assert any("strategy-only" in warning for warning in remove.warnings)


def test_gsd_status_global_verified_for_known_gsd_command_marker(tmp_path: Path, monkeypatch) -> None:
    """Global Claude GSD is verified when a known GSD command file exists."""
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    (claude_home / "commands").mkdir(parents=True)
    (claude_home / "commands" / "gsd-new-project.md").write_text("")
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    (tmp_path / "project").mkdir()
    paths = AppPaths.build(tmp_path / "project")

    adapter = GsdWorkflowAdapter(FakeRunner())
    result = adapter.status(paths, runtime="claude", scope="global")

    assert result.status == "installed_verified"


def test_gsd_status_not_verified_for_unrelated_files(tmp_path: Path, monkeypatch) -> None:
    """Random files in Claude home do not trigger verified status."""
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    (claude_home / "unrelated").mkdir(parents=True)
    (claude_home / "unrelated" / "notes.md").write_text("not gsd")
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    (tmp_path / "project").mkdir()
    paths = AppPaths.build(tmp_path / "project")

    adapter = GsdWorkflowAdapter(FakeRunner())
    result = adapter.status(paths, runtime="claude", scope="global")

    assert result.status == "not_installed"


def test_gsd_status_not_verified_for_unrelated_gsd_named_file(tmp_path: Path, monkeypatch) -> None:
    """A user-created commands/gsd-demo.md should NOT trigger verified status."""
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    (claude_home / "commands").mkdir(parents=True)
    (claude_home / "commands" / "gsd-demo.md").write_text("user file")
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    (tmp_path / "project").mkdir()
    paths = AppPaths.build(tmp_path / "project")

    adapter = GsdWorkflowAdapter(FakeRunner())
    result = adapter.status(paths, runtime="claude", scope="global")

    assert result.status == "not_installed"


def test_gsd_status_planning_alone_not_verified_global(tmp_path: Path, monkeypatch) -> None:
    """.planning directory alone does NOT prove GSD runtime installed in global scope."""
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    (claude_home / ".planning").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    (tmp_path / "project").mkdir()
    paths = AppPaths.build(tmp_path / "project")

    adapter = GsdWorkflowAdapter(FakeRunner())
    result = adapter.status(paths, runtime="claude", scope="global")

    assert result.status == "not_installed"


def test_gsd_status_project_scope_uses_project_claude_root(tmp_path: Path, monkeypatch) -> None:
    """Project-scope GSD verification checks project/.claude with command markers."""
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".claude" / "commands").mkdir(parents=True)
    (project / ".claude" / "commands" / "gsd-new-project.md").write_text("")
    global_home = tmp_path / "global-claude"
    global_home.mkdir()
    monkeypatch.setenv("CLAUDE_HOME", str(global_home))
    paths = AppPaths.build(project)

    adapter = GsdWorkflowAdapter(FakeRunner())
    result = adapter.status(paths, runtime="claude", scope="project")

    assert result.status == "installed_verified"


def test_gsd_status_project_config_alone_not_runtime_verified(tmp_path: Path, monkeypatch) -> None:
    """Project scope with only .planning/config.json is not runtime verified."""
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".claude" / ".planning").mkdir(parents=True)
    (project / ".claude" / ".planning" / "config.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "global-claude"))
    (tmp_path / "global-claude").mkdir()
    paths = AppPaths.build(project)

    adapter = GsdWorkflowAdapter(FakeRunner())
    result = adapter.status(paths, runtime="claude", scope="project")

    assert result.status == "not_installed"
