import json
from pathlib import Path

from ecc_init.cli import main
from ecc_init.workflows import GSD_PACKAGE, GSD_PINNED_VERSION
from ecc_init.workflows.base import EnvironmentCheck, PlannedCommand, WorkflowResult


class FakeGsdAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def _result(self, status: str, command: PlannedCommand) -> WorkflowResult:
        return WorkflowResult(
            "gsd",
            status,
            commands=[command],
            checks=[EnvironmentCheck("node-present", True, "Node.js executable", "fake-node")],
        )

    def status(self, paths, *, runtime="claude", scope="global"):
        self.calls.append(("status", runtime, scope))
        return self._result(
            "not_installed",
            PlannedCommand(("npx", "-y", f"{GSD_PACKAGE}@{GSD_PINNED_VERSION}", "--claude", "--global"), "status"),
        )

    def verify(self, paths, *, runtime="claude", scope="global"):
        self.calls.append(("verify", runtime, scope))
        return self.status(paths, runtime=runtime, scope=scope)

    def install(self, paths, options):
        self.calls.append(("install", options.runtime, options.scope))
        return self._result(
            "planned",
            PlannedCommand(
                (
                    "npx",
                    "-y",
                    f"{GSD_PACKAGE}@{options.version}",
                    f"--{options.runtime}",
                    "--global" if options.scope == "global" else "--local",
                ),
                "install",
                dry_run=options.dry_run,
            ),
        )

    def update(self, paths, options):
        self.calls.append(("update", options.runtime, options.scope))
        return self.install(paths, options)


def test_gsd_install_dry_run_json_uses_runtime_and_scope(tmp_path: Path, monkeypatch, capsys) -> None:
    adapter = FakeGsdAdapter()
    monkeypatch.setattr("ecc_init.cli.GsdWorkflowAdapter", lambda: adapter)

    assert main(["gsd", "install", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert adapter.calls == [("install", "claude", "global")]
    assert payload["status"] == "planned"
    assert payload["commands"][0]["dry_run"] is True
    assert payload["commands"][0]["args"] == [
        "npx",
        "-y",
        "@opengsd/gsd-core@1.6.1",
        "--claude",
        "--global",
    ]


def test_gsd_status_json_reports_device_level_status(tmp_path: Path, monkeypatch, capsys) -> None:
    adapter = FakeGsdAdapter()
    monkeypatch.setattr("ecc_init.cli.GsdWorkflowAdapter", lambda: adapter)

    assert main(["gsd", "status", str(tmp_path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)

    assert adapter.calls == [("status", "claude", "global")]
    assert payload["status"] == "not_installed"


def test_gsd_update_project_scope_uses_local_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    adapter = FakeGsdAdapter()
    monkeypatch.setattr("ecc_init.cli.GsdWorkflowAdapter", lambda: adapter)

    assert main(["gsd", "update", str(tmp_path), "--scope", "project", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert adapter.calls == [("update", "claude", "project"), ("install", "claude", "project")]
    assert payload["commands"][0]["args"][-1] == "--local"
