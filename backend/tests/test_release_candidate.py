import json
import shutil
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.verify_v1_release_candidate import (  # noqa: E402
    EXPECTED_API_SURFACE,
    PUBLIC_VERSION,
    VerificationError,
    _load_runtime_api,
    verify,
)

REQUIRED_FIXTURE_PATHS = (
    "README.md",
    "backend/pyproject.toml",
    "backend/src/palnavi/__init__.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "release/v1.0.0-rc.1.json",
    "datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/manifest.json",
    "datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/pals.json",
    "docs/v1-acceptance.md",
    "reports/codex/loop-016-v1-release-candidate-codex-report.md",
)


def candidate_fixture(tmp_path: Path) -> Path:
    for relative in REQUIRED_FIXTURE_PATHS:
        source = REPOSITORY_ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return tmp_path


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_release_candidate_verifies_exact_repository_tree() -> None:
    api_version, api_surface = _load_runtime_api(REPOSITORY_ROOT)

    result = verify(
        REPOSITORY_ROOT,
        api_version=api_version,
        api_surface=api_surface,
    )

    assert result["status"] == "verified"
    assert result["product_version"] == PUBLIC_VERSION
    assert result["network_required"] is False


def test_release_candidate_rejects_version_drift(tmp_path: Path) -> None:
    root = candidate_fixture(tmp_path)
    package_path = root / "frontend" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "1.0.0"
    write_json(package_path, package)

    with pytest.raises(VerificationError, match="frontend package version"):
        verify(
            root,
            api_version=PUBLIC_VERSION,
            api_surface=EXPECTED_API_SURFACE,
        )


def test_release_candidate_rejects_dataset_drift(tmp_path: Path) -> None:
    root = candidate_fixture(tmp_path)
    manifest_path = (
        root / "datasets" / "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_identity"]["digest"] = "0" * 64
    write_json(manifest_path, manifest)

    with pytest.raises(VerificationError, match="dataset content identity"):
        verify(
            root,
            api_version=PUBLIC_VERSION,
            api_surface=EXPECTED_API_SURFACE,
        )


def test_release_candidate_rejects_release_manifest_drift(tmp_path: Path) -> None:
    root = candidate_fixture(tmp_path)
    manifest_path = root / "release" / "v1.0.0-rc.1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unsupported_capabilities"] = []
    write_json(manifest_path, manifest)

    with pytest.raises(VerificationError, match="unsupported capabilities"):
        verify(
            root,
            api_version=PUBLIC_VERSION,
            api_surface=EXPECTED_API_SURFACE,
        )


def test_release_candidate_rejects_api_surface_drift(tmp_path: Path) -> None:
    root = candidate_fixture(tmp_path)
    reduced_surface = dict(EXPECTED_API_SURFACE)
    reduced_surface.pop("/api/v1/breeding/capture-ranked-routes")

    with pytest.raises(VerificationError, match="runtime API surface"):
        verify(
            root,
            api_version=PUBLIC_VERSION,
            api_surface=reduced_surface,
        )


def test_release_candidate_rejects_missing_acceptance_document(tmp_path: Path) -> None:
    root = candidate_fixture(tmp_path)
    (root / "docs" / "v1-acceptance.md").unlink()

    with pytest.raises(VerificationError, match="required file missing"):
        verify(
            root,
            api_version=PUBLIC_VERSION,
            api_surface=EXPECTED_API_SURFACE,
        )
