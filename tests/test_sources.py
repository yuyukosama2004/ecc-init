import zipfile
from pathlib import Path

import pytest

from ecc_init.core.models import SourceSpec
from ecc_init.errors import IntegrityError, SourceError
from ecc_init.sources import (
    GitHubArchiveProvider,
    SourceLock,
    SourceLockStore,
    project_directory,
    safe_extract_zip,
    sha256_file,
)


COMMIT = "a" * 40


def _zip_bytes(path: str, content: bytes) -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(path, content)
    return buffer.getvalue()


def test_github_archive_provider_uses_fixed_commit_and_offline_cache(tmp_path: Path) -> None:
    payload = _zip_bytes(f"repo-{COMMIT}/skills/python/SKILL.md", b"skill\n")
    archive_path = tmp_path / "expected.zip"
    archive_path.write_bytes(payload)
    spec = SourceSpec(
        source_id="ecc-test",
        kind="github_archive",
        repository="https://github.com/affaan-m/ECC",
        version="1",
        commit=COMMIT,
        integrity=f"sha256:{sha256_file(archive_path)}",
        path="skills/python",
        license_id="MIT",
    )
    calls: list[str] = []
    provider = GitHubArchiveProvider(fetcher=lambda url: calls.append(url) or payload)

    resolved = provider.resolve(spec, tmp_path / "cache")
    cached = provider.resolve(spec, tmp_path / "cache", offline=True)

    assert len(calls) == 1
    assert resolved.lock.resolved_ref == COMMIT
    assert cached.root.exists()
    assert (cached.root / "skills" / "python" / "SKILL.md").read_text(encoding="utf-8") == "skill\n"


def test_github_archive_provider_rejects_mutable_ref(tmp_path: Path) -> None:
    spec = SourceSpec(
        source_id="bad",
        kind="github_archive",
        repository="https://github.com/affaan-m/ECC",
        commit="main",
    )

    with pytest.raises(SourceError, match="fixed 40-character commit"):
        GitHubArchiveProvider(fetcher=lambda url: b"").resolve(spec, tmp_path / "cache")


def test_github_archive_provider_rejects_unallowed_host(tmp_path: Path) -> None:
    spec = SourceSpec(
        source_id="bad-host",
        kind="github_archive",
        repository="https://example.com/owner/repo",
        commit=COMMIT,
    )

    with pytest.raises(SourceError, match="host is not allowed"):
        GitHubArchiveProvider(fetcher=lambda url: b"").resolve(spec, tmp_path / "cache")


def test_github_archive_provider_rejects_hash_mismatch(tmp_path: Path) -> None:
    spec = SourceSpec(
        source_id="bad-hash",
        kind="github_archive",
        repository="https://github.com/affaan-m/ECC",
        commit=COMMIT,
        integrity="sha256:" + ("0" * 64),
    )

    with pytest.raises(IntegrityError, match="hash mismatch"):
        GitHubArchiveProvider(fetcher=lambda url: _zip_bytes("repo/file.txt", b"x")).resolve(spec, tmp_path / "cache")


def test_safe_extract_zip_rejects_zip_slip(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    archive.write_bytes(_zip_bytes("../escape.txt", b"bad"))

    with pytest.raises(SourceError, match="unsafe archive member"):
        safe_extract_zip(archive, tmp_path / "out")


def test_project_directory_copies_selected_files_and_rejects_traversal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "skills" / "python").mkdir(parents=True)
    (source / "skills" / "python" / "SKILL.md").write_text("skill\n", encoding="utf-8")
    (source / "README.md").write_text("readme\n", encoding="utf-8")

    copied = project_directory(source, target, include=("skills/**/*.md",))

    assert [path.relative_to(target).as_posix() for path in copied] == ["skills/python/SKILL.md"]
    with pytest.raises(SourceError, match="unsafe projection include"):
        project_directory(source, target, include=("../*.md",))


def test_source_lock_store_round_trips(tmp_path: Path) -> None:
    store = SourceLockStore(tmp_path / "source-lock.json")
    lock = SourceLock(
        source_id="ecc",
        repository="https://github.com/affaan-m/ECC",
        resolved_ref=COMMIT,
        integrity="sha256:" + ("1" * 64),
        source_path="skills",
        license_id="MIT",
        license_path="LICENSE",
    )

    store.save(lock)

    assert store.load_all()["ecc"] == lock
