"""Typed validation and canonical identity for raw breeding dataset documents."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime

from palnavi.domain.data import (
    DATASET_ID_PATTERN,
    BreedingDatasetSnapshot,
    ContentIdentity,
    DatasetClassification,
    DatasetFound,
    DatasetInvalid,
    DatasetMetadata,
    DatasetValidationCode,
    DatasetValidationIssue,
    EvidenceQuality,
    GameVersionScope,
    ProvenanceRecord,
    ProvenanceSourceType,
    ValidationStatus,
    VersionScopeKind,
    dataset_content_sha256,
    validate_relationship_rows,
)

SUPPORTED_SCHEMA_VERSION = 1
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BreedingDatasetImporter:
    """Convert untrusted manifest and relationship documents into a validated snapshot."""

    def import_documents(
        self,
        manifest_document: object,
        relationship_document: object,
        expected_dataset_id: str,
    ) -> DatasetFound | DatasetInvalid:
        manifest = _as_mapping(manifest_document)
        if manifest is None:
            return self._invalid(
                expected_dataset_id,
                DatasetValidationCode.MALFORMED_DOCUMENT,
                "manifest",
                "manifest must be a JSON object",
            )

        schema_version = manifest.get("schema_version")
        if type(schema_version) is not int or schema_version != SUPPORTED_SCHEMA_VERSION:
            return self._invalid(
                expected_dataset_id,
                DatasetValidationCode.UNSUPPORTED_SCHEMA_VERSION,
                "schema_version",
                f"schema_version must equal {SUPPORTED_SCHEMA_VERSION}",
            )

        dataset_id = _nonempty_string(manifest.get("dataset_id"))
        if (
            dataset_id is None
            or DATASET_ID_PATTERN.fullmatch(dataset_id) is None
            or dataset_id != expected_dataset_id
        ):
            return self._invalid(
                expected_dataset_id,
                DatasetValidationCode.INVALID_DATASET_ID,
                "dataset_id",
                "dataset_id must be stable and match the requested dataset",
            )

        classification_value = manifest.get("classification")
        if classification_value is None:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.MISSING_CLASSIFICATION,
                "classification",
                "dataset classification is required",
            )
        try:
            classification = DatasetClassification(str(classification_value))
        except ValueError:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_CLASSIFICATION,
                "classification",
                "dataset classification is unsupported",
            )

        version_scope = self._parse_version_scope(manifest.get("game_version_scope"))
        if version_scope is None or not self._scope_matches(classification, version_scope):
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_VERSION_SCOPE,
                "game_version_scope",
                "game-version scope is missing or incompatible with classification",
            )

        created_at = _parse_timestamp(manifest.get("created_at"))
        if created_at is None:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_TIMESTAMP,
                "created_at",
                "created_at must be an ISO-8601 timestamp with timezone",
            )

        importer_version = _nonempty_string(manifest.get("importer_version"))
        if importer_version is None:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_IMPORTER_VERSION,
                "importer_version",
                "importer_version is required",
            )

        try:
            validation_status = ValidationStatus(str(manifest.get("validation_status")))
        except ValueError:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_VALIDATION_STATUS,
                "validation_status",
                "dataset must be explicitly marked validated",
            )

        provenance = self._parse_provenance(manifest.get("provenance"))
        if isinstance(provenance, DatasetValidationIssue):
            return DatasetInvalid(dataset_id=dataset_id, issues=(provenance,))
        if classification is DatasetClassification.SYNTHETIC and any(
            record.source_type is not ProvenanceSourceType.LOCAL_SYNTHETIC_FIXTURE
            or record.evidence_quality is not EvidenceQuality.SYNTHETIC_ONLY
            for record in provenance
        ):
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_SYNTHETIC_CLAIM,
                "provenance",
                "synthetic datasets may use only synthetic local-test provenance",
            )
        if classification is DatasetClassification.PRODUCTION and any(
            record.source_type is ProvenanceSourceType.LOCAL_SYNTHETIC_FIXTURE
            or record.evidence_quality is EvidenceQuality.SYNTHETIC_ONLY
            for record in provenance
        ):
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_PROVENANCE,
                "provenance",
                "production datasets cannot use synthetic-only provenance",
            )

        content_identity = self._parse_content_identity(manifest.get("content_identity"))
        if content_identity is None:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_CONTENT_IDENTITY,
                "content_identity",
                "content identity must contain a lowercase SHA-256 digest",
            )

        relationship_mapping = _as_mapping(relationship_document)
        if relationship_mapping is None or "relationships" not in relationship_mapping:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.MALFORMED_DOCUMENT,
                "relationships",
                "relationship document must contain a relationships array",
            )
        if relationship_mapping.get("dataset_id") != dataset_id:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_DATASET_ID,
                "relationships.dataset_id",
                "relationship document dataset_id must match the manifest",
            )
        if relationship_mapping.get("classification") != classification.value:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.INVALID_CLASSIFICATION,
                "relationships.classification",
                "relationship document classification must match the manifest",
            )
        relationships, relationship_issues = validate_relationship_rows(
            relationship_mapping["relationships"]
        )
        if relationship_issues:
            return DatasetInvalid(dataset_id=dataset_id, issues=relationship_issues)

        actual_digest = dataset_content_sha256(
            dataset_id=dataset_id,
            schema_version=schema_version,
            classification=classification,
            game_version_scope=version_scope,
            created_at=created_at,
            importer_version=importer_version,
            validation_status=validation_status,
            provenance=provenance,
            relationships=relationships,
        )
        if actual_digest != content_identity.digest:
            return self._invalid(
                dataset_id,
                DatasetValidationCode.CONTENT_IDENTITY_MISMATCH,
                "content_identity.digest",
                "dataset content does not match the declared identity",
            )

        species_ids = frozenset(
            species
            for relationship in relationships
            for species in (relationship.parent_a, relationship.parent_b, relationship.child)
        )
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            schema_version=schema_version,
            classification=classification,
            game_version_scope=version_scope,
            created_at=created_at,
            importer_version=importer_version,
            validation_status=validation_status,
            provenance=provenance,
            content_identity=content_identity,
        )
        return DatasetFound(
            snapshot=BreedingDatasetSnapshot(
                metadata=metadata,
                species_ids=species_ids,
                relationships=relationships,
            )
        )

    @staticmethod
    def _parse_version_scope(raw: object) -> GameVersionScope | None:
        value = _as_mapping(raw)
        if value is None:
            return None
        try:
            kind = VersionScopeKind(str(value.get("kind")))
        except ValueError:
            return None
        scope_value = value.get("value")
        if scope_value is not None and not isinstance(scope_value, str):
            return None
        return GameVersionScope(kind=kind, value=scope_value)

    @staticmethod
    def _scope_matches(
        classification: DatasetClassification,
        scope: GameVersionScope,
    ) -> bool:
        if classification is DatasetClassification.SYNTHETIC:
            return scope.kind is VersionScopeKind.SYNTHETIC_TEST_ONLY and scope.value is None
        return (
            scope.kind is VersionScopeKind.EXPLICIT_GAME_VERSION
            and scope.value is not None
            and bool(scope.value.strip())
        )

    @staticmethod
    def _parse_provenance(
        raw: object,
    ) -> tuple[ProvenanceRecord, ...] | DatasetValidationIssue:
        if not isinstance(raw, list) or not raw:
            return _issue(
                DatasetValidationCode.MISSING_PROVENANCE,
                "provenance",
                "at least one structured provenance record is required",
            )

        records: list[ProvenanceRecord] = []
        for index, item in enumerate(raw):
            value = _as_mapping(item)
            field = f"provenance[{index}]"
            if value is None:
                return _issue(
                    DatasetValidationCode.INVALID_PROVENANCE,
                    field,
                    "provenance record must be an object",
                )
            source_id = _nonempty_string(value.get("source_id"))
            locator = _nonempty_string(value.get("locator"))
            license_note = _nonempty_string(value.get("license_or_usage_note"))
            retrieved_at = _parse_timestamp(value.get("retrieved_at"))
            try:
                source_type = ProvenanceSourceType(str(value.get("source_type")))
                evidence_quality = EvidenceQuality(str(value.get("evidence_quality")))
            except ValueError:
                return _issue(
                    DatasetValidationCode.INVALID_PROVENANCE,
                    field,
                    "provenance source type or evidence quality is unsupported",
                )
            if source_id is None or locator is None or license_note is None or retrieved_at is None:
                return _issue(
                    DatasetValidationCode.INVALID_PROVENANCE,
                    field,
                    "provenance metadata fields are required and must be valid",
                )
            records.append(
                ProvenanceRecord(
                    source_id=source_id,
                    source_type=source_type,
                    locator=locator,
                    retrieved_at=retrieved_at,
                    license_or_usage_note=license_note,
                    evidence_quality=evidence_quality,
                )
            )
        return tuple(records)

    @staticmethod
    def _parse_content_identity(raw: object) -> ContentIdentity | None:
        value = _as_mapping(raw)
        if value is None or value.get("algorithm") != "sha256":
            return None
        digest = value.get("digest")
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            return None
        return ContentIdentity(algorithm="sha256", digest=digest)

    @staticmethod
    def _invalid(
        dataset_id: str,
        code: DatasetValidationCode,
        field: str,
        message: str,
    ) -> DatasetInvalid:
        return DatasetInvalid(dataset_id=dataset_id, issues=(_issue(code, field, message),))


def _as_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return value
    return None


def _nonempty_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _issue(
    code: DatasetValidationCode,
    field: str,
    message: str,
) -> DatasetValidationIssue:
    return DatasetValidationIssue(code=code, field=field, message=message)
