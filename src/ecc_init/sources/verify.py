from __future__ import annotations

import urllib.parse

from ..core.models import CheckResult
from ..packs.registry import Registry
from .providers import ALLOWED_ARCHIVE_HOSTS, MUTABLE_REFS


def _is_fixed_commit(value: str | None) -> bool:
    if not value or value.lower() in MUTABLE_REFS:
        return False
    return len(value) == 40 and all(char in "0123456789abcdefABCDEF" for char in value)


def verify_registry_sources(registry: Registry) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for source in registry.sources.values():
        if source.kind == "bundled":
            checks.append(
                CheckResult(
                    check_id=f"source:{source.source_id}:bundled",
                    ok=True,
                    severity="info",
                    message="bundled source is local",
                    detail=source.path or "",
                )
            )
            continue
        if source.kind == "github_archive":
            host = urllib.parse.urlparse(source.repository or "").netloc.lower()
            host_ok = host in ALLOWED_ARCHIVE_HOSTS
            commit_ok = _is_fixed_commit(source.commit)
            checks.append(
                CheckResult(
                    check_id=f"source:{source.source_id}:host",
                    ok=host_ok,
                    severity="error" if not host_ok else "info",
                    message="github archive host allowlist",
                    detail=host or "missing host",
                )
            )
            checks.append(
                CheckResult(
                    check_id=f"source:{source.source_id}:ref",
                    ok=commit_ok,
                    severity="error" if not commit_ok else "info",
                    message="github archive uses fixed commit",
                    detail=source.commit or "",
                )
            )
            continue
        checks.append(
            CheckResult(
                check_id=f"source:{source.source_id}:declared",
                ok=True,
                severity="info",
                message=f"{source.kind} source is declaration-only in this phase",
                detail=source.repository or source.package or "",
            )
        )
    return checks
