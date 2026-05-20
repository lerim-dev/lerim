"""Tests for the release preflight script."""

from __future__ import annotations

import importlib.util
import urllib.error
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "release_preflight.py"
SPEC = importlib.util.spec_from_file_location("release_preflight", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
release_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_preflight)


def write_release_files(
    directory: Path,
    *,
    pyproject_version: str = "0.3.0",
    changelog_version: str = "0.3.0",
) -> None:
    """Write minimal release metadata files into a temporary directory."""
    (directory / "pyproject.toml").write_text(
        f"""
[project]
name = "lerim"
version = "{pyproject_version}"
""".lstrip(),
        encoding="utf-8",
    )
    (directory / "CHANGELOG.md").write_text(
        f"""
# Changelog

## [Unreleased]

## [{changelog_version}] - 2026-05-20
""".lstrip(),
        encoding="utf-8",
    )


def test_release_preflight_accepts_matching_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight passes when version, package metadata, and changelog agree."""
    write_release_files(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = release_preflight.main(["--version", "0.3.0", "--skip-pypi"])

    assert result == 0
    assert "release_preflight_ok 0.3.0" in capsys.readouterr().out


def test_release_preflight_rejects_tag_without_v(tmp_path: Path) -> None:
    """Release tags must keep the v prefix used by the publish workflow."""
    write_release_files(tmp_path)

    with pytest.raises(SystemExit, match="release tag must start with v"):
        release_preflight.main(
            [
                "--tag",
                "0.3.0",
                "--skip-pypi",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_rejects_prerelease_tag(tmp_path: Path) -> None:
    """Release tags that update latest must be final SemVer releases."""
    write_release_files(tmp_path, pyproject_version="0.3.0rc1", changelog_version="0.3.0rc1")

    with pytest.raises(SystemExit, match="final SemVer tag"):
        release_preflight.main(
            [
                "--tag",
                "v0.3.0rc1",
                "--skip-pypi",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_rejects_prerelease_version(tmp_path: Path) -> None:
    """Explicit release versions must also be final SemVer releases."""
    write_release_files(tmp_path, pyproject_version="0.3.0rc1", changelog_version="0.3.0rc1")

    with pytest.raises(SystemExit, match="final SemVer version"):
        release_preflight.main(
            [
                "--version",
                "0.3.0rc1",
                "--skip-pypi",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_rejects_tag_version_disagreement(tmp_path: Path) -> None:
    """Preflight fails when explicit tag and version disagree."""
    write_release_files(tmp_path)

    with pytest.raises(SystemExit, match="does not match --version"):
        release_preflight.main(
            [
                "--tag",
                "v0.3.0",
                "--version",
                "0.3.1",
                "--skip-pypi",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_uses_github_ref_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight defaults to the GitHub tag environment variable."""
    write_release_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REF_NAME", "v0.3.0")

    result = release_preflight.main(["--skip-pypi"])

    assert result == 0
    assert "release_preflight_ok 0.3.0" in capsys.readouterr().out


def test_release_preflight_rejects_pyproject_mismatch(tmp_path: Path) -> None:
    """Preflight fails when the requested release version is not in pyproject."""
    write_release_files(tmp_path, pyproject_version="0.2.1")

    with pytest.raises(SystemExit, match="does not match pyproject version"):
        release_preflight.main(
            [
                "--version",
                "0.3.0",
                "--skip-pypi",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_rejects_missing_changelog_section(tmp_path: Path) -> None:
    """Preflight fails when the changelog section was not finalized."""
    write_release_files(tmp_path, changelog_version="0.2.1")

    with pytest.raises(SystemExit, match="missing a dated section"):
        release_preflight.main(
            [
                "--version",
                "0.3.0",
                "--skip-pypi",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_rejects_invalid_changelog_date(tmp_path: Path) -> None:
    """Preflight fails when the changelog release heading has an invalid date."""
    write_release_files(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        """
# Changelog

## [0.3.0] - 2026-99-99
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="invalid release date"):
        release_preflight.main(
            [
                "--version",
                "0.3.0",
                "--skip-pypi",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_rejects_existing_pypi_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preflight fails before publishing a version already present on PyPI."""
    write_release_files(tmp_path)
    monkeypatch.setattr(release_preflight, "pypi_version_exists", lambda *_args: True)

    with pytest.raises(SystemExit, match="already exists on PyPI"):
        release_preflight.main(
            [
                "--version",
                "0.3.0",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_accepts_missing_pypi_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preflight accepts a version absent from PyPI."""
    write_release_files(tmp_path)
    monkeypatch.setattr(release_preflight, "pypi_version_exists", lambda *_args: False)
    monkeypatch.setattr(release_preflight, "highest_pypi_final_version", lambda *_args: "0.2.9")

    result = release_preflight.main(
        [
            "--version",
            "0.3.0",
            "--pyproject",
            str(tmp_path / "pyproject.toml"),
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
        ]
    )

    assert result == 0


def test_release_preflight_rejects_lower_than_existing_pypi_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tag cannot move Docker latest backward after a newer final PyPI release."""
    write_release_files(tmp_path)
    monkeypatch.setattr(release_preflight, "pypi_version_exists", lambda *_args: False)
    monkeypatch.setattr(release_preflight, "highest_pypi_final_version", lambda *_args: "0.3.1")

    with pytest.raises(SystemExit, match="is not newer than the latest PyPI final release"):
        release_preflight.main(
            [
                "--version",
                "0.3.0",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_rejects_equal_to_existing_pypi_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The project-level PyPI check catches equal finals even if the version probe is stale."""
    write_release_files(tmp_path)
    monkeypatch.setattr(release_preflight, "pypi_version_exists", lambda *_args: False)
    monkeypatch.setattr(release_preflight, "highest_pypi_final_version", lambda *_args: "0.3.0")

    with pytest.raises(SystemExit, match="is not newer than the latest PyPI final release"):
        release_preflight.main(
            [
                "--version",
                "0.3.0",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )


def test_release_preflight_accepts_newer_than_existing_pypi_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A release newer than the highest existing final version can proceed."""
    write_release_files(tmp_path, pyproject_version="0.3.1", changelog_version="0.3.1")
    monkeypatch.setattr(release_preflight, "pypi_version_exists", lambda *_args: False)
    monkeypatch.setattr(release_preflight, "highest_pypi_final_version", lambda *_args: "0.3.0")

    result = release_preflight.main(
        [
            "--version",
            "0.3.1",
            "--pyproject",
            str(tmp_path / "pyproject.toml"),
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
        ]
    )

    assert result == 0


def test_release_preflight_ignores_prereleases_when_finding_highest_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only final SemVer releases participate in the monotonic release check."""

    class Response:
        """Tiny context manager for a PyPI JSON response."""

        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"releases":{"0.2.9":[],"0.3.0rc1":[],"0.3.0.dev1":[]}}'

    monkeypatch.setattr(release_preflight.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    assert release_preflight.highest_pypi_final_version("lerim", 1.0) == "0.2.9"


def test_pypi_version_exists_returns_false_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PyPI 404 means the release version is still available."""

    def raise_not_found(_url: str, *, timeout: float) -> object:
        """Simulate PyPI returning no release for the version."""
        raise urllib.error.HTTPError(
            url="https://pypi.org/pypi/lerim/0.3.0/json",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(release_preflight.urllib.request, "urlopen", raise_not_found)

    assert release_preflight.pypi_version_exists("lerim", "0.3.0", 1.0) is False


def test_pypi_version_exists_fails_on_non_404_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PyPI non-404 failures block the release instead of assuming availability."""

    def raise_server_error(_url: str, *, timeout: float) -> object:
        """Simulate a PyPI service error."""
        raise urllib.error.HTTPError(
            url="https://pypi.org/pypi/lerim/0.3.0/json",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(release_preflight.urllib.request, "urlopen", raise_server_error)

    with pytest.raises(SystemExit, match="HTTP 500"):
        release_preflight.pypi_version_exists("lerim", "0.3.0", 1.0)


def test_release_preflight_reports_pypi_check_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preflight surfaces PyPI errors instead of treating them as available."""
    write_release_files(tmp_path)

    def raise_pypi_failure(*_args: object) -> bool:
        """Simulate a non-404 PyPI lookup failure."""
        raise SystemExit("PyPI check failed")

    monkeypatch.setattr(release_preflight, "pypi_version_exists", raise_pypi_failure)

    with pytest.raises(SystemExit, match="PyPI check failed"):
        release_preflight.main(
            [
                "--version",
                "0.3.0",
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--changelog",
                str(tmp_path / "CHANGELOG.md"),
            ]
        )
