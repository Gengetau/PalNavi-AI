"""Framework-independent contracts for versioned knowledge retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_CHUNK_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True, order=True)
class KnowledgeDocumentId:
    value: str

    def __post_init__(self) -> None:
        if _IDENTIFIER_PATTERN.fullmatch(self.value) is None:
            raise ValueError("invalid knowledge document identifier")


@dataclass(frozen=True, slots=True, order=True)
class KnowledgeChunkId:
    value: str

    def __post_init__(self) -> None:
        if _CHUNK_IDENTIFIER_PATTERN.fullmatch(self.value) is None:
            raise ValueError("invalid knowledge chunk identifier")


@dataclass(frozen=True, slots=True, order=True)
class LanguageIdentifier:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().replace("_", "-").lower()
        if _LANGUAGE_PATTERN.fullmatch(normalized) is None:
            raise ValueError("invalid language identifier")
        object.__setattr__(self, "value", normalized)


class KnowledgeClassification(StrEnum):
    SYNTHETIC = "synthetic"
    PRODUCTION = "production"


class KnowledgeVersionScopeKind(StrEnum):
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"
    EXPLICIT_GAME_VERSION = "explicit_game_version"


@dataclass(frozen=True, slots=True)
class KnowledgeVersionScope:
    kind: KnowledgeVersionScopeKind
    value: str | None

    def __post_init__(self) -> None:
        if self.kind is KnowledgeVersionScopeKind.SYNTHETIC_TEST_ONLY:
            if self.value is not None:
                raise ValueError("synthetic-only version scope cannot have a version value")
            return
        if self.value is None or not self.value.strip() or len(self.value) > 64:
            raise ValueError("explicit version scope requires a bounded value")


class KnowledgeSourceType(StrEnum):
    LOCAL_SYNTHETIC_FIXTURE = "local_synthetic_fixture"
    OFFICIAL = "official"
    COMMUNITY = "community"
    MAINTAINER_SUPPLIED = "maintainer_supplied"


class KnowledgeEvidenceQuality(StrEnum):
    SYNTHETIC_ONLY = "synthetic_only"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class KnowledgeProvenance:
    source_id: str
    source_type: KnowledgeSourceType
    locator: str
    retrieved_at: datetime
    license_or_usage_note: str
    evidence_quality: KnowledgeEvidenceQuality


class KnowledgeValidationStatus(StrEnum):
    VALIDATED = "validated"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class KnowledgeContentIdentity:
    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256" or _SHA256_PATTERN.fullmatch(self.digest) is None:
            raise ValueError("invalid knowledge content identity")


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentMetadata:
    document_id: KnowledgeDocumentId
    title: str
    language: LanguageIdentifier
    classification: KnowledgeClassification
    game_version_scope: KnowledgeVersionScope
    provenance: KnowledgeProvenance
    imported_at: datetime
    schema_version: int
    importer_version: str
    validation_status: KnowledgeValidationStatus
    content_identity: KnowledgeContentIdentity


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    chunk_id: KnowledgeChunkId
    document_id: KnowledgeDocumentId
    order: int
    section_path: tuple[str, ...]
    text: str


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    metadata: KnowledgeDocumentMetadata
    normalized_content: str
    chunks: tuple[KnowledgeChunk, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentInput:
    document_id: str
    title: str
    language: str
    classification: KnowledgeClassification
    game_version_scope: KnowledgeVersionScope
    provenance: KnowledgeProvenance
    imported_at: datetime
    schema_version: int
    importer_version: str
    content: str
    declared_content_sha256: str


class KnowledgeValidationCode(StrEnum):
    MALFORMED_MANIFEST = "malformed_manifest"
    INVALID_DOCUMENT_ID = "invalid_document_id"
    BLANK_TITLE = "blank_title"
    INVALID_LANGUAGE = "invalid_language"
    INVALID_VERSION_SCOPE = "invalid_version_scope"
    INVALID_PROVENANCE = "invalid_provenance"
    UNSAFE_SOURCE_LOCATOR = "unsafe_source_locator"
    INVALID_TIMESTAMP = "invalid_timestamp"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    INVALID_IMPORTER_VERSION = "invalid_importer_version"
    BLANK_CONTENT = "blank_content"
    INVALID_CONTENT_IDENTITY = "invalid_content_identity"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"


@dataclass(frozen=True, slots=True)
class KnowledgeValidationIssue:
    code: KnowledgeValidationCode
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class KnowledgeImportSuccess:
    document: KnowledgeDocument


@dataclass(frozen=True, slots=True)
class KnowledgeImportFailure:
    issues: tuple[KnowledgeValidationIssue, ...]


KnowledgeImportOutcome = KnowledgeImportSuccess | KnowledgeImportFailure


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    document_id: KnowledgeDocumentId
    chunk_id: KnowledgeChunkId
    title: str
    section_path: tuple[str, ...]
    source_id: str
    source_locator: str
    retrieved_at: datetime
    license_or_usage_note: str


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    text: str
    language: LanguageIdentifier | None = None
    exact_game_version: str | None = None
    synthetic_only: bool = False
    limit: int = 5

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("knowledge query must not be blank")
        if len(self.text) > 500:
            raise ValueError("knowledge query is too long")
        if self.exact_game_version is not None and (
            not self.exact_game_version.strip() or len(self.exact_game_version) > 64
        ):
            raise ValueError("exact game version must be bounded and nonblank")
        if not 1 <= self.limit <= 20:
            raise ValueError("knowledge result limit must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class KnowledgeSearchResult:
    score: float
    document_id: KnowledgeDocumentId
    chunk_id: KnowledgeChunkId
    title: str
    section_path: tuple[str, ...]
    text: str
    language: LanguageIdentifier
    classification: KnowledgeClassification
    game_version_scope: KnowledgeVersionScope
    citation: KnowledgeCitation


@dataclass(frozen=True, slots=True)
class KnowledgeSearchSuccess:
    results: tuple[KnowledgeSearchResult, ...]


class KnowledgeRepositoryFailureKind(StrEnum):
    UNAVAILABLE = "repository_unavailable"
    INVALID_STATE = "repository_invalid_state"


@dataclass(frozen=True, slots=True)
class KnowledgeRepositoryFailure:
    kind: KnowledgeRepositoryFailureKind
    message: str


KnowledgeSearchOutcome = KnowledgeSearchSuccess | KnowledgeRepositoryFailure


class KnowledgeStoreDisposition(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"
    REPLACED = "replaced"


@dataclass(frozen=True, slots=True)
class KnowledgeStoreSuccess:
    document_id: KnowledgeDocumentId
    content_identity: KnowledgeContentIdentity
    disposition: KnowledgeStoreDisposition


KnowledgeStoreOutcome = KnowledgeStoreSuccess | KnowledgeRepositoryFailure


class KnowledgeRepository(Protocol):
    """Write-on-import and read-only-search knowledge storage boundary."""

    def import_document(self, document: KnowledgeDocument) -> KnowledgeStoreOutcome: ...

    def search(self, query: KnowledgeQuery) -> KnowledgeSearchOutcome: ...
