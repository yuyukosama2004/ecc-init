from pathlib import Path

from ecc_init.paths import AppPaths
from ecc_init.workflows import GSD_PACKAGE, GSD_PINNED_VERSION, GsdWorkflowAdapter
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
    assert result.commands[0].args[-1] == f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}"
    assert result.logs == []
    assert runner.calls == [("C:/tools/node.cmd", "--version")]
    assert any("Claude Home affected scope" in warning for warning in result.warnings)


def test_gsd_install_runs_only_after_environment_ok(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    runner = FakeRunner()
    adapter = GsdWorkflowAdapter(runner)

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "installed"
    assert result.logs[0].args[-1] == f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}"


def test_gsd_install_blocks_when_node_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", lambda name: None)
    runner = FakeRunner()
    adapter = GsdWorkflowAdapter(runner)

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked"
    assert runner.calls == []
    assert any(check.check_id == "node-present" and not check.ok for check in result.checks)


def test_gsd_install_blocks_when_node_too_old(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ecc_init.workflows.gsd.shutil.which", _which)
    adapter = GsdWorkflowAdapter(FakeRunner(version="v16.20.0"))

    result = adapter.install(AppPaths.build(tmp_path), dry_run=False)

    assert result.status == "blocked"
    assert any(check.check_id == "node-version" and not check.ok for check in result.checks)


def test_gsd_inspect_and_remove_are_safe_strategy_only(tmp_path: Path) -> None:
    adapter = GsdWorkflowAdapter(FakeRunner())
    paths = AppPaths.build(tmp_path)

    missing = adapter.inspect(paths)
    remove = adapter.remove(paths)

    assert missing.status == "missing"
    assert remove.status == "planned"
    assert remove.logs == []
    assert any("strategy-only" in warning for warning in remove.warnings)
