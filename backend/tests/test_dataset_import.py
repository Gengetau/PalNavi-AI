import copy
import json
from pathlib import Path
from typing import Any

import pytest

from palnavi.domain.data import (
    DatasetClassification,
    DatasetFound,
    DatasetInvalid,
    DatasetValidationCode,
    VersionScopeKind,
)
from palnavi.infrastructure.dataset_validation import BreedingDatasetImporter
from palnavi.infrastructure.json_dataset_repository import default_dataset_root


@pytest.fixture
def valid_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    dataset_directory = default_dataset_root() / "synthetic-v1"
    manifest = json.loads((dataset_directory / "manifest.json").read_text(encoding="utf-8"))
    relationships = json.loads(
        (dataset_directory / "relationships.json").read_text(encoding="utf-8")
    )
    return manifest, relationships


def import_documents(
    manifest: dict[str, Any],
    relationships: dict[str, Any],
) -> DatasetFound | DatasetInvalid:
    return BreedingDatasetImporter().import_documents(
        manifest_document=manifest,
        relationship_document=relationships,
        expected_dataset_id="synthetic-v1",
    )


def assert_invalid_code(
    result: DatasetFound | DatasetInvalid,
    code: DatasetValidationCode,
) -> None:
    assert isinstance(result, DatasetInvalid)
    assert code in {issue.code for issue in result.issues}


def test_valid_versioned_synthetic_dataset_loads(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = valid_documents

    result = import_documents(manifest, relationships)

    assert isinstance(result, DatasetFound)
    assert result.snapshot.metadata.dataset_id == "synthetic-v1"
    assert result.snapshot.metadata.classification is DatasetClassification.SYNTHETIC
    assert result.snapshot.metadata.game_version_scope.kind is VersionScopeKind.SYNTHETIC_TEST_ONLY
    assert result.snapshot.metadata.game_version_scope.value is None
    assert len(result.snapshot.metadata.provenance) == 1
    assert len(result.snapshot.metadata.content_identity.digest) == 64
    assert len(result.snapshot.relationships) == 6


def test_unsupported_schema_version_is_rejected(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    manifest["schema_version"] = 2

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.UNSUPPORTED_SCHEMA_VERSION,
    )


def test_missing_classification_is_rejected(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    del manifest["classification"]

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.MISSING_CLASSIFICATION,
    )


def test_missing_provenance_is_rejected(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    manifest["provenance"] = []

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.MISSING_PROVENANCE,
    )


def test_invalid_provenance_timestamp_is_rejected(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    manifest["provenance"][0]["retrieved_at"] = "not-a-timestamp"

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.INVALID_PROVENANCE,
    )


def test_production_classification_requires_explicit_game_version(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    manifest["classification"] = "production"

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.INVALID_VERSION_SCOPE,
    )


def test_synthetic_classification_rejects_real_game_version_scope(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    manifest["game_version_scope"] = {
        "kind": "explicit_game_version",
        "value": "real-version-not-authorized",
    }

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.INVALID_VERSION_SCOPE,
    )


def test_synthetic_dataset_cannot_claim_real_source_provenance(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    manifest["provenance"][0]["source_type"] = "official"
    manifest["provenance"][0]["evidence_quality"] = "primary"

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.INVALID_SYNTHETIC_CLAIM,
    )


def test_checksum_mismatch_is_rejected(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    relationships["relationships"][0]["child"] = "pal_changed"

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.CONTENT_IDENTITY_MISMATCH,
    )


def test_invalid_stable_identifier_is_rejected(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    relationships["relationships"][0]["parent_a"] = "Pal A"

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.INVALID_SPECIES_IDENTIFIER,
    )


def test_malformed_relationship_row_is_rejected(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    del relationships["relationships"][0]["parent_b"]

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.MALFORMED_RELATIONSHIP,
    )


def test_conflicting_unordered_parent_pair_is_rejected_during_import(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    manifest, relationships = copy.deepcopy(valid_documents)
    relationships["relationships"].append(
        {"parent_a": "pal_b", "parent_b": "pal_a", "child": "pal_d"}
    )

    assert_invalid_code(
        import_documents(manifest, relationships),
        DatasetValidationCode.CONFLICTING_RELATIONSHIP,
    )


def test_documents_are_read_without_network_or_external_paths(
    valid_documents: tuple[dict[str, Any], dict[str, Any]],
    tmp_path: Path,
) -> None:
    manifest, relationships = valid_documents
    fixture_copy = tmp_path / "snapshot.json"
    fixture_copy.write_text(json.dumps(relationships), encoding="utf-8")

    result = import_documents(manifest, json.loads(fixture_copy.read_text(encoding="utf-8")))

    assert isinstance(result, DatasetFound)
