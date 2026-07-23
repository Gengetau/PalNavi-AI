"""Framework-independent contracts for official-source metadata snapshots."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$")
_MAX_NOTE_CHARS = 500
_MAX_HEADER_CHARS = 500
OFFICIAL_SOURCE_URLS_V1: Mapping[str, str] = MappingProxyType(
    {
        "palworld-mod-guideline": ("https://guideline.palworldgame.com/palworld-mod-guideline"),
        "palworld-news": "https://news.palworldgame.com/",
        "palworld-rest-info-doc": "https://docs.palworldgame.com/api/rest-api/info/",
        "palworld-rest-introduction": (
            "https://docs.palworldgame.com/api/rest-api/palwold-rest-api/"
        ),
        "palworld-rest-players-doc": ("https://docs.palworldgame.com/api/rest-api/players/"),
        "palworld-server-guide": "https://docs.palworldgame.com/",
        "palworld-server-mods": ("https://docs.palworldgame.com/settings-and-operation/mod/"),
        "palworld-technology-ids": (
            "https://docs.palworldgame.com/settings-and-operation/technologyids/"
        ),
        "pocketpair-derivative-work": (
            "https://www.pocketpair.jp/en/guidelines-derivativework-en/"
        ),
    }
)
OFFICIAL_SOURCE_IDS_V1 = tuple(sorted(OFFICIAL_SOURCE_URLS_V1))


class OfficialSourceKind(StrEnum):
    DOCUMENTATION = "documentation"
    POLICY = "policy"
    NEWS = "news"


class OfficialSourceSensitivity(StrEnum):
    STANDARD = "standard"
    POLICY = "policy"
    SENSITIVE_RUNTIME_FIELDS = "sensitive_runtime_fields"


class OfficialSourceCapturePolicy(StrEnum):
    METADATA_ONLY = "metadata_only"


class OfficialSourceUsageStatus(StrEnum):
    METADATA_ONLY = "metadata_only"
    SCOPE_REVIEW_REQUIRED = "scope_review_required"
    DOCUMENTATION_ONLY = "documentation_only"
    SENSITIVE_DOCUMENTATION_ONLY = "sensitive_documentation_only"
    COPYING_REQUIRES_REVIEW = "copying_requires_review"
    MANUAL_POLICY_REVIEW_REQUIRED = "manual_policy_review_required"
    POLICY_REFERENCE_ONLY = "policy_reference_only"


class SourceFetchOutcomeKind(StrEnum):
    SUCCESS = "success"
    NETWORK_RESTRICTED = "network_restricted"
    TIMEOUT = "timeout"
    REDIRECT_REJECTED = "redirect_rejected"
    CONTENT_TYPE_REJECTED = "content_type_rejected"
    RESPONSE_TOO_LARGE = "response_too_large"
    MALFORMED_ENCODING = "malformed_encoding"
    UNAVAILABLE = "unavailable"


class SnapshotAcquisitionMode(StrEnum):
    LIVE_METADATA = "live_metadata"
    SYNTHETIC_MOCK = "synthetic_mock"


@dataclass(frozen=True, slots=True, order=True)
class OfficialSourceEntry:
    source_id: str
    canonical_url: str
    publisher: str
    source_kind: OfficialSourceKind
    observed_version: str | None
    content_sensitivity: OfficialSourceSensitivity
    content_capture_policy: OfficialSourceCapturePolicy
    usage_review_status: OfficialSourceUsageStatus
    usage_note: str
    live_probe_permitted: bool
    verified_at: datetime

    def __post_init__(self) -> None:
        if _IDENTIFIER_PATTERN.fullmatch(self.source_id) is None:
            raise ValueError("invalid official source identifier")
        if not self.canonical_url or len(self.canonical_url) > 500:
            raise ValueError("official source URL must be bounded")
        if not self.publisher.strip() or len(self.publisher) > 100:
            raise ValueError("official source publisher must be bounded")
        if self.observed_version is not None and (
            not self.observed_version.strip() or len(self.observed_version) > 100
        ):
            raise ValueError("observed version must be null or bounded")
        if not self.usage_note.strip() or len(self.usage_note) > _MAX_NOTE_CHARS:
            raise ValueError("usage note must be bounded")
        _require_utc(self.verified_at, "source verification timestamp")


@dataclass(frozen=True, slots=True)
class OfficialSourceRegistry:
    schema_version: int
    sources: tuple[OfficialSourceEntry, ...]
    registry_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported official source registry schema")
        if not self.sources:
            raise ValueError("official source registry must not be empty")
        if tuple(sorted(self.sources, key=lambda source: source.source_id)) != self.sources:
            raise ValueError("official source registry must use canonical source order")
        if len({source.source_id for source in self.sources}) != len(self.sources):
            raise ValueError("duplicate official source identifier")
        if len({source.canonical_url for source in self.sources}) != len(self.sources):
            raise ValueError("duplicate official source URL")
        if {source.source_id: source.canonical_url for source in self.sources} != dict(
            OFFICIAL_SOURCE_URLS_V1
        ):
            raise ValueError("official source registry has an invalid source set")
        _require_sha256(self.registry_sha256, "registry identity")


@dataclass(frozen=True, slots=True)
class OfficialSourceFetchRequest:
    source_id: str
    canonical_url: str
    timeout_seconds: float = 10.0
    max_response_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        if _IDENTIFIER_PATTERN.fullmatch(self.source_id) is None:
            raise ValueError("invalid official source request identifier")
        if not 0.1 <= self.timeout_seconds <= 30:
            raise ValueError("official source timeout must be bounded")
        if not 1 <= self.max_response_bytes <= 2 * 1024 * 1024:
            raise ValueError("official source response limit must be bounded")


@dataclass(frozen=True, slots=True)
class SanitizedResponseMetadata:
    status_code: int
    media_type: str
    etag: str | None
    last_modified: str | None
    final_url: str

    def __post_init__(self) -> None:
        if self.status_code != 200:
            raise ValueError("successful source metadata requires HTTP 200")
        if _MEDIA_TYPE_PATTERN.fullmatch(self.media_type) is None:
            raise ValueError("invalid response media type")
        for value in (self.etag, self.last_modified):
            if value is not None and (
                not value.strip()
                or len(value) > _MAX_HEADER_CHARS
                or not value.isascii()
                or any(ord(character) < 32 and character != "\t" for character in value)
            ):
                raise ValueError("allowlisted response header must be bounded")
        if not self.final_url or len(self.final_url) > 500 or not self.final_url.isascii():
            raise ValueError("final URL must be bounded")


@dataclass(frozen=True, slots=True)
class SourceFetchSuccess:
    kind: SourceFetchOutcomeKind
    metadata: SanitizedResponseMetadata
    response_bytes: int
    content_sha256: str

    def __post_init__(self) -> None:
        if self.kind is not SourceFetchOutcomeKind.SUCCESS:
            raise ValueError("source fetch success has an invalid discriminant")
        if not 1 <= self.response_bytes <= 2 * 1024 * 1024:
            raise ValueError("source response byte length is invalid")
        _require_sha256(self.content_sha256, "source content identity")


@dataclass(frozen=True, slots=True)
class SourceFetchFailure:
    kind: SourceFetchOutcomeKind

    def __post_init__(self) -> None:
        if self.kind is SourceFetchOutcomeKind.SUCCESS:
            raise ValueError("source fetch failure cannot use success")


SourceFetchOutcome = SourceFetchSuccess | SourceFetchFailure


@dataclass(frozen=True, slots=True)
class OfficialSourceSnapshotRecord:
    source_id: str
    outcome: SourceFetchOutcomeKind
    status_code: int | None
    media_type: str | None
    etag: str | None
    last_modified: str | None
    final_url: str | None
    response_bytes: int | None
    content_sha256: str | None
    content_persisted: bool = False

    def __post_init__(self) -> None:
        if _IDENTIFIER_PATTERN.fullmatch(self.source_id) is None:
            raise ValueError("invalid snapshot source identifier")
        if self.source_id not in OFFICIAL_SOURCE_URLS_V1:
            raise ValueError("snapshot source identifier is not registered")
        if self.content_persisted:
            raise ValueError("official source bodies must not be persisted")
        success_fields = (
            self.status_code,
            self.media_type,
            self.final_url,
            self.response_bytes,
            self.content_sha256,
        )
        if self.outcome is SourceFetchOutcomeKind.SUCCESS:
            if any(value is None for value in success_fields):
                raise ValueError("successful snapshot record is incomplete")
            if self.status_code != 200:
                raise ValueError("successful snapshot record requires HTTP 200")
            assert self.response_bytes is not None
            if not 1 <= self.response_bytes <= 2 * 1024 * 1024:
                raise ValueError("snapshot response byte length is invalid")
            assert self.content_sha256 is not None
            _require_sha256(self.content_sha256, "snapshot content identity")
            assert self.media_type is not None
            if _MEDIA_TYPE_PATTERN.fullmatch(self.media_type) is None:
                raise ValueError("snapshot media type is invalid")
            assert self.final_url is not None
            if self.final_url != OFFICIAL_SOURCE_URLS_V1[self.source_id]:
                raise ValueError("snapshot final URL is invalid")
            for value in (self.etag, self.last_modified):
                if value is not None and (
                    not value.strip()
                    or len(value) > _MAX_HEADER_CHARS
                    or not value.isascii()
                    or any(ord(character) < 32 and character != "\t" for character in value)
                ):
                    raise ValueError("snapshot response header is invalid")
            return
        if any(value is not None for value in success_fields) or self.etag is not None:
            raise ValueError("failed snapshot record cannot expose response metadata")
        if self.last_modified is not None:
            raise ValueError("failed snapshot record cannot expose response metadata")


@dataclass(frozen=True, slots=True)
class OfficialSourceSnapshotManifest:
    schema_version: int
    registry_sha256: str
    acquisition_mode: SnapshotAcquisitionMode
    started_at: datetime
    completed_at: datetime
    records: tuple[OfficialSourceSnapshotRecord, ...]
    manifest_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported official source snapshot schema")
        _require_sha256(self.registry_sha256, "snapshot registry identity")
        _require_sha256(self.manifest_sha256, "snapshot manifest identity")
        _require_utc(self.started_at, "snapshot start timestamp")
        _require_utc(self.completed_at, "snapshot completion timestamp")
        if self.completed_at < self.started_at:
            raise ValueError("snapshot completion precedes its start")
        if not self.records:
            raise ValueError("snapshot manifest must not be empty")
        if tuple(sorted(self.records, key=lambda record: record.source_id)) != self.records:
            raise ValueError("snapshot records must use canonical source order")
        if len({record.source_id for record in self.records}) != len(self.records):
            raise ValueError("duplicate snapshot source identifier")
        if tuple(record.source_id for record in self.records) != OFFICIAL_SOURCE_IDS_V1:
            raise ValueError("snapshot source coverage is invalid")


class OfficialSourceTransport(Protocol):
    async def fetch(self, request: OfficialSourceFetchRequest) -> SourceFetchOutcome: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


def _require_sha256(value: str, name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value) or value.microsecond != 0:
        raise ValueError(f"{name} must be UTC")
