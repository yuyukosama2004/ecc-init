from __future__ import annotations

import sys
import zipfile
from pathlib import Path


REQUIRED_SUFFIXES = {
    "ecc_init/resources/manifest.json",
    "ecc_init/resources/registry/registry.json",
    "ecc_init/resources/templates/project_CLAUDE.md",
    "ecc_init/resources/templates/FRONTEND_LIFECYCLE.md",
    "ecc_init/resources/global_skills/code-review/SKILL.md",
    "ecc_init/resources/global_skills/security-review/SKILL.md",
    "ecc_init/resources/project_skills/python-patterns/SKILL.md",
    "ecc_init/resources/project_skills/react-patterns/SKILL.md",
    "ecc_init/resources/project_skills/ui-ux-pro-max/SKILL.md",
}


def _find_wheel(path: Path) -> Path:
    if path.is_file() and path.suffix == ".whl":
        return path
    wheels = sorted(path.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel in {path}, found {len(wheels)}")
    return wheels[0]


def check_wheel(path: Path) -> None:
    wheel = _find_wheel(path)
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        entry_point_name = next((name for name in names if name.endswith(".dist-info/entry_points.txt")), None)
        entry_points = archive.read(entry_point_name).decode("utf-8") if entry_point_name else ""
    missing = sorted(suffix for suffix in REQUIRED_SUFFIXES if suffix not in names)
    if missing:
        raise SystemExit("wheel is missing package data:\n" + "\n".join(missing))
    if "ecc-init = ecc_init.cli:main" not in entry_points:
        raise SystemExit("wheel is missing ecc-init console entry point")
    redistributed_anthropic = sorted(name for name in names if "anthropic" in name.lower())
    if redistributed_anthropic:
        raise SystemExit("wheel includes redistributed Anthropic content:\n" + "\n".join(redistributed_anthropic))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: check_wheel_contents.py <wheel-or-dist-dir>", file=sys.stderr)
        return 2
    check_wheel(Path(args[0]))
    print("wheel package data check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
