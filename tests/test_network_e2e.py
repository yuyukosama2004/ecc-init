import os
import urllib.request

import pytest

from ecc_init.packs import load_registry
from ecc_init.sources.providers import _github_archive_url
from ecc_init.workflows.gsd import GSD_PACKAGE, GSD_PINNED_VERSION


pytestmark = pytest.mark.skipif(
    os.environ.get("ECC_INIT_NETWORK_E2E") != "1",
    reason="network E2E is opt-in for nightly/manual CI",
)


def _read_url(url: str, *, limit: int = 2048) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ecc-init-network-e2e"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(limit)


def test_pinned_gsd_package_metadata_is_available() -> None:
    package = GSD_PACKAGE.replace("/", "%2f")
    payload = _read_url(f"https://registry.npmjs.org/{package}/{GSD_PINNED_VERSION}")

    assert GSD_PINNED_VERSION.encode() in payload


def test_pinned_ecc_archive_url_is_available() -> None:
    source = load_registry().sources["ecc-upstream-pinned"]
    url = _github_archive_url(source.repository or "", source.commit or "")
    payload = _read_url(url)

    assert payload
