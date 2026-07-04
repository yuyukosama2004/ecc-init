from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def _find_wheel(path: Path) -> Path:
    if path.is_file() and path.suffix == ".whl":
        return path
    wheels = sorted(path.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel in {path}, found {len(wheels)}")
    return wheels[0]


def _venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _venv_ecc(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "ecc-init.exe"
    return root / "bin" / "ecc-init"


def _ecc_command(root: Path, python: Path) -> list[str]:
    ecc = _venv_ecc(root)
    if ecc.exists():
        return [str(ecc)]
    return [str(python), "-m", "ecc_init.cli"]


def _run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"command failed: {' '.join(args)}", file=sys.stderr)
        if exc.stdout:
            print("stdout:\n" + exc.stdout, file=sys.stderr)
        if exc.stderr:
            print("stderr:\n" + exc.stderr, file=sys.stderr)
        raise


def _json_command(args: list[str], *, env: dict[str, str]) -> dict[str, object]:
    result = _run(args, env=env)
    return json.loads(result.stdout)


def smoke(wheel_or_dist: Path) -> None:
    wheel = _find_wheel(wheel_or_dist)
    with tempfile.TemporaryDirectory(prefix="ecc-init-smoke-") as temp_dir:
        root = Path(temp_dir).resolve()
        venv_dir = root / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = _venv_python(venv_dir)
        _run([str(python), "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", str(wheel)])
        ecc = _ecc_command(venv_dir, python)

        demo = root / "demo"
        demo.mkdir()
        (demo / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n', encoding="utf-8")
        (demo / ".planning").mkdir()
        (demo / ".planning" / "config.json").write_text(
            '{"agent_skills":{"gsd-executor":[".claude/skills/python-patterns"]}}\n',
            encoding="utf-8",
        )
        plan_file = root / "plan.json"
        env = {
            **os.environ,
            "ECC_INIT_HOME": str(root / "ecc-home"),
            "CLAUDE_HOME": str(root / "claude-home"),
        }

        _run([*ecc, "--version"], env=env)
        plan = _json_command([*ecc, "init", str(demo), "--json"], env=env)
        if plan.get("workflow") != "gsd":
            raise SystemExit("init did not default to the gsd workflow")
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        status = _json_command([*ecc, "status", str(demo), "--json"], env=env)
        if status.get("project_root") != str(demo.resolve()):
            raise SystemExit("status JSON used an unexpected project_root")
        update = _json_command([*ecc, "update", str(demo), "--check", "--json"], env=env)
        if not update.get("dry_run"):
            raise SystemExit("update --check was not dry-run")
        remove = _json_command([*ecc, "remove", str(demo), "--pack", "python-fastapi", "--json"], env=env)
        if not remove.get("dry_run"):
            raise SystemExit("remove preview was not dry-run")
        apply = _json_command([*ecc, "apply", str(plan_file), "--dry-run", "--json"], env=env)
        if apply.get("applied"):
            raise SystemExit("apply --dry-run reported applied=true")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: cli_smoke.py <wheel-or-dist-dir>", file=sys.stderr)
        return 2
    smoke(Path(args[0]))
    print("CLI smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
