from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

import check_wheel_contents
import cli_smoke


ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOLS = ("pip==25.1.1", "setuptools==80.9.0", "wheel==0.45.1")


def _run(args: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def _venv_python(root: Path) -> Path:
    if sys.platform.startswith("win"):
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ecc-init-release-") as temp_dir:
        root = Path(temp_dir).resolve()
        build_env = root / "build-env"
        dist = root / "dist"
        venv.EnvBuilder(with_pip=True).create(build_env)
        python = _venv_python(build_env)
        _run([str(python), "-m", "pip", "install", "--upgrade", *BUILD_TOOLS])
        _run([str(python), "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "-w", str(dist)])
        check_wheel_contents.check_wheel(dist)
        cli_smoke.smoke(dist)
        shutil.copytree(dist, ROOT / "dist", dirs_exist_ok=True)
    print("release dry-run passed; review dist/ and tag v0.2.0-alpha.1 after final approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
