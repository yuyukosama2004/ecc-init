from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


_ROOT = files("ecc_init").joinpath("resources")


def read_resource_text(relative_path: str) -> str:
    return _ROOT.joinpath(relative_path).read_text(encoding="utf-8")


def read_manifest() -> dict[str, Any]:
    return json.loads(read_resource_text("manifest.json"))
