"""Release asset selection and extraction for the codebase-memory-mcp installer."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from headroom import binaries
from headroom.graph import installer


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _zip_archive(member_name: str, data: bytes = b"MZ fake binary") -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(member_name, data)
    return payload.getvalue()


@pytest.mark.parametrize(
    ("plat", "extension"),
    [
        ("darwin-arm64", ".tar.gz"),
        ("darwin-amd64", ".tar.gz"),
        ("linux-arm64", ".tar.gz"),
        ("linux-amd64", ".tar.gz"),
        ("windows-amd64", ".zip"),
    ],
)
def test_asset_filename_matches_the_registry_asset(plat: str, extension: str) -> None:
    filename = installer._asset_filename(plat)

    assert filename == f"codebase-memory-mcp-{plat}{extension}"
    pinned_urls = {
        asset["url"] for asset in binaries._tool_entry("codebase-memory-mcp")["assets"].values()
    }
    assert f"{installer.GITHUB_RELEASE_URL}/{installer.CBM_VERSION}/{filename}" in pinned_urls


@pytest.mark.parametrize("member_name", ["codebase-memory-mcp.exe", "codebase-memory-mcp"])
def test_download_cbm_on_windows_fetches_and_extracts_the_zip(
    monkeypatch, tmp_path: Path, member_name: str
) -> None:
    monkeypatch.setenv("HEADROOM_BINARIES_ALLOW_UNVERIFIED", "1")
    monkeypatch.setattr(installer, "CBM_BIN_DIR", tmp_path)
    monkeypatch.setattr(installer, "_detect_platform", lambda: "windows-amd64")
    requested: list[str] = []

    def fake_urlopen(url: str, timeout: int = 60) -> FakeResponse:
        requested.append(url)
        return FakeResponse(_zip_archive(member_name))

    monkeypatch.setattr(installer, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        "subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="")
    )

    path = installer.download_cbm()

    assert requested == [
        f"{installer.GITHUB_RELEASE_URL}/{installer.CBM_VERSION}/"
        "codebase-memory-mcp-windows-amd64.zip"
    ]
    assert path == tmp_path / installer.CBM_BIN_NAME
    assert path.read_bytes() == b"MZ fake binary"


def test_download_cbm_zip_errors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HEADROOM_BINARIES_ALLOW_UNVERIFIED", "1")
    monkeypatch.setattr(installer, "CBM_BIN_DIR", tmp_path)
    monkeypatch.setattr(installer, "_detect_platform", lambda: "windows-amd64")

    monkeypatch.setattr(
        installer, "urlopen", lambda url, timeout=60: FakeResponse(_zip_archive("README.md"))
    )
    with pytest.raises(RuntimeError, match="binary not found in archive"):
        installer.download_cbm()

    monkeypatch.setattr(installer, "urlopen", lambda url, timeout=60: FakeResponse(b"not a zip"))
    with pytest.raises(RuntimeError, match="Failed to extract archive"):
        installer.download_cbm()
