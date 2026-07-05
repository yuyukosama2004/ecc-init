from pathlib import Path

from ecc_init.paths import AppPaths
from ecc_init.workflows import GSD_PACKAGE, GSD_PINNED_VERSION, GsdInstallOptions, GsdWorkflowAdapter
from ecc_init.workflows.base import CommandResult


class FakeRunner:
    def __init__(self, version: str = "v18.19.0", install_returncode: int = 0):
        self.version = version
        self.install_returncode = install_returncode
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: list[str], *, cwd: Path | None = None) -> CommandResult:
        self.calls.append(tuple(args))
        if args[-1] == "--version":
            return CommandResult(tuple(args), 0, self.version + "\n", "")
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
    assert command[0].replace("\\", "/").endswith(("npx", "npx.cmd"))
    assert command[1:] == ("-y", f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}", "--claude", "--global")
    assert result.logs == []
    assert runner.calls == []
    assert any(check.check_id == "node-version" and check.detail == "not checked during dry-run" for check in result.checks)
    assert any("install affects runtime configuration" in warning for warning in result.warnings)


def test_gsd_install_runs_only_after_environment_ok(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    runner = FakeRunner()
    adapter = GsdWorkflowAdapter(runner)

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "installed_unverified"
    assert result.logs[0].args[-3:] == (f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}", "--claude", "--global")


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
    adapter = GsdWorkflowAdapter(FakeRunner(version="v16.20.0"))

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked_environment"
    assert any(check.check_id == "node-version" and not check.ok for check in result.checks)


def test_gsd_local_project_command_uses_local_scope(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    adapter = GsdWorkflowAdapter(FakeRunner())

    result = adapter.install(
        AppPaths.build(tmp_path),
        GsdInstallOptions(scope="project", dry_run=True),
    )

    assert result.commands[0].args[-2:] == ("--claude", "--local")


def test_gsd_update_reuses_official_installer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    adapter = GsdWorkflowAdapter(FakeRunner())

    result = adapter.update(AppPaths.build(tmp_path), dry_run=True)

    assert result.commands[0].args[0].replace("\\", "/").endswith(("npx", "npx.cmd"))
    assert result.commands[0].args[-3:] == (f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}", "--claude", "--global")


def test_gsd_windows_command_suffix_is_preserved(monkeypatch) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.os.name", "nt")
    adapter = GsdWorkflowAdapter(FakeRunner())

    command = adapter.install_command()

    assert command.args[0] == "npx.cmd"


def test_gsd_inspect_and_remove_are_safe_strategy_only(tmp_path: Path) -> None:
    adapter = GsdWorkflowAdapter(FakeRunner())
    paths = AppPaths.build(tmp_path)

    missing = adapter.inspect(paths)
    remove = adapter.remove(paths)

    assert missing.status == "missing"
    assert remove.status == "planned"
    assert remove.logs == []
    assert any("strategy-only" in warning for warning in remove.warnings)
