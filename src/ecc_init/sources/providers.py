from __future__ import annotations

import shutil
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Callable

from ..core.models import SourceSpec
from ..errors import IntegrityError, SourceError
from ..util import sha256_text
from .locks import SourceLock


ALLOWED_ARCHIVE_HOSTS = {"github.com"}
MUTABLE_REFS = {"main", "master", "latest", "next", "dev", "develop", "trunk", "head"}


@dataclass(frozen=True)
class ResolvedSource:
    source_id: str
    root: Path
    lock: SourceLock
    licenses: tuple[Path, ...]


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_integrity(path: Path, expected: str | None) -> str:
    actual = sha256_file(path)
    if expected:
        expected_hash = expected.removeprefix("sha256:")
        if actual != expected_hash:
            raise IntegrityError(f"hash mismatch for {path}: expected sha256:{expected_hash}, got sha256:{actual}")
    return f"sha256:{actual}"


def _assert_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise SourceError(f"path escapes target directory: {candidate}")
    return resolved_candidate


def safe_extract_zip(archive_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise SourceError(f"unsafe archive member: {member.filename}")
            mode = (member.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise SourceError(f"unsafe archive symlink: {member.filename}")
            _assert_inside(target_dir, target_dir / Path(*name.parts))
        archive.extractall(target_dir)


def _archive_root(extract_dir: Path) -> Path:
    children = [path for path in extract_dir.iterdir() if path.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extract_dir


def _license_files(root: Path) -> tuple[Path, ...]:
    names = {"license", "license.md", "license.txt", "copying", "notice", "notice.md"}
    return tuple(sorted(path for path in root.iterdir() if path.is_file() and path.name.lower() in names))


def project_directory(
    source_root: Path,
    target_root: Path,
    *,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> list[Path]:
    copied: list[Path] = []
    exclude_set = set(exclude)
    patterns = include or ("**/*",)
    for pattern in patterns:
        if PurePosixPath(pattern).is_absolute() or ".." in PurePosixPath(pattern).parts:
            raise SourceError(f"unsafe projection include: {pattern}")
        for source in source_root.glob(pattern):
            if source.is_symlink():
                raise SourceError(f"unsafe projection symlink: {source}")
            if not source.is_file():
                continue
            relative = source.relative_to(source_root).as_posix()
            if relative in exclude_set:
                continue
            target = _assert_inside(target_root, target_root / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def _fixed_commit(ref: str | None) -> str:
    value = (ref or "").strip()
    if value.lower() in MUTABLE_REFS or len(value) != 40 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise SourceError("GitHub archive sources must use a fixed 40-character commit SHA")
    return value


def _github_archive_url(repository: str, commit: str) -> str:
    parsed = urllib.parse.urlparse(repository)
    if parsed.netloc.lower() not in ALLOWED_ARCHIVE_HOSTS:
        raise SourceError(f"repository host is not allowed: {parsed.netloc}")
    path = parsed.path.strip("/")
    if path.count("/") != 1:
        raise SourceError(f"GitHub repository must be owner/name: {repository}")
    return f"https://github.com/{path}/archive/{commit}.zip"


class BundledProvider:
    def resolve(self, spec: SourceSpec) -> ResolvedSource:
        root = Path(str(files("ecc_init").joinpath("resources"))).resolve()
        integrity = f"sha256:{sha256_text(spec.source_id + ':' + (spec.version or 'bundled'))}"
        lock = SourceLock(
            source_id=spec.source_id,
            repository=spec.repository,
            resolved_ref=spec.version or "bundled",
            integrity=integrity,
            source_path=spec.path,
            license_id=spec.license_id,
            license_path=spec.license_path,
        )
        return ResolvedSource(spec.source_id, root, lock, _license_files(root))


class GitHubArchiveProvider:
    def __init__(self, fetcher: Callable[[str], bytes] | None = None):
        self.fetcher = fetcher or self._fetch

    def _fetch(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "ecc-init/0.2-source-provider"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read()

    def resolve(self, spec: SourceSpec, cache_dir: Path, *, offline: bool = False) -> ResolvedSource:
        if not spec.repository:
            raise SourceError(f"source {spec.source_id} is missing repository")
        commit = _fixed_commit(spec.commit or spec.version)
        url = _github_archive_url(spec.repository, commit)
        archive_path = cache_dir / "archives" / spec.source_id / f"{commit}.zip"
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        if not archive_path.exists():
            if offline:
                raise SourceError(f"offline and no cached archive for {spec.source_id}@{commit}")
            try:
                archive_path.write_bytes(self.fetcher(url))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if archive_path.exists():
                    pass
                else:
                    raise SourceError(f"failed to fetch {url}: {exc}") from exc

        integrity = _verify_integrity(archive_path, spec.integrity)
        extract_dir = cache_dir / "resolved" / spec.source_id / commit
        if not extract_dir.exists():
            temp_dir = cache_dir / "tmp" / spec.source_id / commit
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            safe_extract_zip(archive_path, temp_dir)
            extract_dir.parent.mkdir(parents=True, exist_ok=True)
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            temp_dir.replace(extract_dir)

        root = _archive_root(extract_dir)
        lock = SourceLock(
            source_id=spec.source_id,
            repository=spec.repository,
            resolved_ref=commit,
            integrity=integrity,
            source_path=spec.path,
            license_id=spec.license_id,
            license_path=spec.license_path,
        )
        return ResolvedSource(spec.source_id, root, lock, _license_files(root))
