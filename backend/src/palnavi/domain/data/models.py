"""Framework-independent contracts for validated breeding dataset snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from palnavi.domain.breeding import (
    BreedingRelationship,
    BreedingRule,
    SpeciesGenderFeasibility,
    SpeciesId,
)


class DatasetClassification(StrEnum):
    SYNTHETIC = "synthetic"
    PRODUCTION = "production"


class VersionScopeKind(StrEnum):
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"
    EXPLICIT_GAME_VERSION = "explicit_game_version"


class ValidationStatus(StrEnum):
    VALIDATED = "validated"


class ProvenanceSourceType(StrEnum):
    LOCAL_SYNTHETIC_FIXTURE = "local_synthetic_fixture"
    OFFICIAL = "official"
    COMMUNITY = "community"
    MAINTAINER_SUPPLIED = "maintainer_supplied"


class EvidenceQuality(StrEnum):
    SYNTHETIC_ONLY = "synthetic_only"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class GameVersionScope:
    kind: VersionScopeKind
    value: str | None


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    source_id: str
    source_type: ProvenanceSourceType
    locator: str
    retrieved_at: datetime
    license_or_usage_note: str
    evidence_quality: EvidenceQuality


@dataclass(frozen=True, slots=True)
class ContentIdentity:
    algorithm: str
    digest: str


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    dataset_id: str
    schema_version: int
    classification: DatasetClassification
    game_version_scope: GameVersionScope
    created_at: datetime
    importer_version: str
    validation_status: ValidationStatus
    provenance: tuple[ProvenanceRecord, ...]
    content_identity: ContentIdentity


@dataclass(frozen=True, slots=True)
class BreedingDatasetSnapshot:
    metadata: DatasetMetadata
    species_ids: frozenset[SpeciesId]
    relationships: tuple[BreedingRelationship, ...]


@dataclass(frozen=True, slots=True)
class GenderAwareBreedingDatasetSnapshot:
    """Exact production rule snapshot assembled from both accepted manifests."""

    dataset_id: str
    schema_version: int
    content_identity: ContentIdentity
    gender_data_identity: ContentIdentity
    species_ids: frozenset[SpeciesId]
    rules: tuple[BreedingRule, ...]
    gender_feasibility: tuple[SpeciesGenderFeasibility, ...]


class DatasetValidationCode(StrEnum):
    INVALID_DATASET_ID = "invalid_dataset_id"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    MALFORMED_DOCUMENT = "malformed_document"
    MISSING_CLASSIFICATION = "missing_classification"
    INVALID_CLASSIFICATION = "invalid_classification"
    INVALID_VERSION_SCOPE = "invalid_version_scope"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_IMPORTER_VERSION = "invalid_importer_version"
    INVALID_VALIDATION_STATUS = "invalid_validation_status"
    MISSING_PROVENANCE = "missing_provenance"
    INVALID_PROVENANCE = "invalid_provenance"
    INVALID_SYNTHETIC_CLAIM = "invalid_synthetic_claim"
    MALFORMED_RELATIONSHIP = "malformed_relationship"
    INVALID_SPECIES_IDENTIFIER = "invalid_species_identifier"
    CONFLICTING_RELATIONSHIP = "conflicting_relationship"
    INVALID_CONTENT_IDENTITY = "invalid_content_identity"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    INVALID_FILE_INVENTORY = "invalid_file_inventory"
    FILE_INTEGRITY_MISMATCH = "file_integrity_mismatch"
    MALFORMED_PALWORLD_RECORD = "malformed_palworld_record"
    CONFLICTING_BREEDING_RULE = "conflicting_breeding_rule"
    INVALID_GENDER_DATA = "invalid_gender_data"


@dataclass(frozen=True, slots=True)
class DatasetValidationIssue:
    code: DatasetValidationCode
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class DatasetFound:
    snapshot: BreedingDatasetSnapshot


@dataclass(frozen=True, slots=True)
class DatasetNotFound:
    dataset_id: str


@dataclass(frozen=True, slots=True)
class DatasetInvalid:
    dataset_id: str
    issues: tuple[DatasetValidationIssue, ...]


DatasetLoadResult = DatasetFound | DatasetNotFound | DatasetInvalid


@dataclass(frozen=True, slots=True)
class GenderAwareDatasetFound:
    snapshot: GenderAwareBreedingDatasetSnapshot


GenderAwareDatasetLoadResult = GenderAwareDatasetFound | DatasetNotFound | DatasetInvalid


class BreedingDatasetRepository(Protocol):
    """Read-only access to fully validated immutable breeding dataset snapshots."""

    def load(self, dataset_id: str) -> DatasetLoadResult: ...


class GenderAwareBreedingDatasetRepository(Protocol):
    """Read-only access to the exact accepted production rule snapshot."""

    def load(self, dataset_id: str) -> GenderAwareDatasetLoadResult: ...
