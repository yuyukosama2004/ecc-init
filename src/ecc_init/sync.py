from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .util import now_iso, read_text, write_text_atomic


GITHUB_API = "https://api.github.com/repos/affaan-m/ECC/releases/latest"
RAW_TEMPLATE = "https://raw.githubusercontent.com/affaan-m/ECC/{ref}/{path}"


@dataclass(frozen=True)
class SyncResult:
    content: str
    source: str
    ref: str | None
    warning: str | None = None


def _request_text(url: str, timeout: float = 5.0) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ecc-init/0.1",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def resolve_stable_ref(global_state: dict[str, Any], offline: bool = False) -> tuple[str, str | None]:
    previous = str(global_state.get("ecc_upstream_ref") or "main")
    if offline:
        return previous, "离线模式：使用上次记录的 ECC ref"
    try:
        payload = json.loads(_request_text(GITHUB_API))
        tag = payload.get("tag_name")
        if isinstance(tag, str) and tag.strip():
            global_state["ecc_upstream_ref"] = tag.strip()
            global_state["ecc_ref_checked_at"] = now_iso()
            return tag.strip(), None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return previous, f"无法检查 ECC 稳定版本：{exc}"
    return previous, "ECC 最新 release 未返回 tag，沿用已有 ref"


def fetch_upstream_skill(
    *,
    skill_name: str,
    upstream_path: str | None,
    fallback: str,
    cache_dir: Path,
    ref: str,
    offline: bool,
) -> SyncResult:
    if not upstream_path:
        return SyncResult(content=fallback, source="bundled", ref=None)

    cache_path = cache_dir / "ecc" / ref / upstream_path
    if offline:
        cached = read_text(cache_path)
        if cached:
            return SyncResult(cached, "cache", ref, "离线模式：使用上游缓存")
        return SyncResult(fallback, "bundled", None, "离线且无缓存：使用内置模板")

    url = RAW_TEMPLATE.format(ref=ref, path=upstream_path)
    try:
        content = _request_text(url)
        write_text_atomic(cache_path, content)
        return SyncResult(content, "upstream", ref)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        cached = read_text(cache_path)
        if cached:
            return SyncResult(cached, "cache", ref, f"上游同步失败，使用缓存：{exc}")
        return SyncResult(fallback, "bundled", None, f"上游同步失败，使用内置模板：{exc}")
