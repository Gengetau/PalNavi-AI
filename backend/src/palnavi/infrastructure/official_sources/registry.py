"""Strict loading and canonical identity for the official-source registry."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from palnavi.application import canonical_json_bytes
from palnavi.domain.official_sources import (
    OFFICIAL_SOURCE_URLS_V1,
    OfficialSourceCapturePolicy,
    OfficialSourceEntry,
    OfficialSourceKind,
    OfficialSourceRegistry,
    OfficialSourceSensitivity,
    OfficialSourceUsageStatus,
)

MAX_REGISTRY_BYTES = 128 * 1024
ALLOWED_OFFICIAL_HOSTS = frozenset(
    {
        "docs.palworldgame.com",
        "news.palworldgame.com",
        "guideline.palworldgame.com",
        "www.pocketpair.jp",
    }
)
AUTHORIZED_SOURCE_URLS: Mapping[str, str] = OFFICIAL_SOURCE_URLS_V1
_ROOT_FIELDS = frozenset({"schema_version", "sources", "registry_sha256"})
_ENTRY_FIELDS = frozenset(
    {
        "source_id",
        "canonical_url",
        "publisher",
        "source_kind",
        "observed_version",
        "content_sensitivity",
        "content_capture_policy",
        "usage_review_status",
        "usage_note",
        "live_probe_permitted",
        "verified_at",
    }
)
_UTC_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class OfficialSourceRegistryError(ValueError):
    """Sanitized registry rejection without raw document or path details."""


def load_official_source_registry(path: Path | None = None) -> OfficialSourceRegistry:
    registry_path = path or default_official_source_registry_path()
    descriptor = -1
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_NONBLOCK"):
            flags |= os.O_NONBLOCK
        descriptor = os.open(registry_path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OfficialSourceRegistryError("official source registry is unavailable")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read(MAX_REGISTRY_BYTES + 1)
    except OSError:
        raise OfficialSourceRegistryError("official source registry is unavailable") from None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
    if len(raw) > MAX_REGISTRY_BYTES:
        raise OfficialSourceRegistryError("official source registry is too large")
    try:
        text = raw.decode("utf-8", errors="strict")
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise OfficialSourceRegistryError("official source registry is malformed") from None
    return parse_official_source_registry(document)


def parse_official_source_registry(document: object) -> OfficialSourceRegistry:
    root = _strict_mapping(document, _ROOT_FIELDS, "registry")
    schema_version = _exact_int(root["schema_version"], "schema_version")
    source_documents = root["sources"]
    if not isinstance(source_documents, list) or not source_documents:
        raise OfficialSourceRegistryError("registry sources must be a nonempty array")
    sources = tuple(_parse_source(value) for value in source_documents)
    if {source.source_id: source.canonical_url for source in sources} != dict(
        AUTHORIZED_SOURCE_URLS
    ):
        raise OfficialSourceRegistryError("registry source set is invalid")
    declared_identity = _bounded_string(root["registry_sha256"], "registry_sha256", maximum=64)
    try:
        registry = OfficialSourceRegistry(
            schema_version=schema_version,
            sources=sources,
            registry_sha256=declared_identity,
        )
    except ValueError:
        raise OfficialSourceRegistryError("official source registry is invalid") from None
    calculated_identity = official_source_registry_sha256(registry)
    if calculated_identity != declared_identity:
        raise OfficialSourceRegistryError("official source registry identity mismatch")
    return registry


def official_source_registry_payload(registry: OfficialSourceRegistry) -> dict[str, object]:
    return {
        "schema_version": registry.schema_version,
        "sources": [
            {
                "source_id": source.source_id,
                "canonical_url": source.canonical_url,
                "publisher": source.publisher,
                "source_kind": source.source_kind.value,
                "observed_version": source.observed_version,
                "content_sensitivity": source.content_sensitivity.value,
                "content_capture_policy": source.content_capture_policy.value,
                "usage_review_status": source.usage_review_status.value,
                "usage_note": source.usage_note,
                "live_probe_permitted": source.live_probe_permitted,
                "verified_at": source.verified_at.isoformat(timespec="seconds").replace(
                    "+00:00", "Z"
                ),
            }
            for source in registry.sources
        ],
    }


def official_source_registry_sha256(registry: OfficialSourceRegistry) -> str:
    return hashlib.sha256(
        canonical_json_bytes(official_source_registry_payload(registry))
    ).hexdigest()


def validate_official_source_request(source_id: str, canonical_url: str) -> None:
    expected = AUTHORIZED_SOURCE_URLS.get(source_id)
    if expected is None or canonical_url != expected:
        raise ValueError("official source request is not registered")
    try:
        parsed = urlsplit(canonical_url)
        port = parsed.port
    except ValueError as error:
        raise ValueError("official source URL is invalid") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_OFFICIAL_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
        or "\\" in parsed.path
        or any(part in {".", ".."} for part in parsed.path.split("/"))
        or parsed.netloc != parsed.hostname
    ):
        raise ValueError("official source URL is unsafe")


def default_official_source_registry_path() -> Path:
    return Path(__file__).resolve().parents[5] / "config" / "official-sources-v1.json"


def _parse_source(value: object) -> OfficialSourceEntry:
    source = _strict_mapping(value, _ENTRY_FIELDS, "source")
    source_id = _bounded_string(source["source_id"], "source_id", maximum=64)
    canonical_url = _bounded_string(source["canonical_url"], "canonical_url", maximum=500)
    try:
        validate_official_source_request(source_id, canonical_url)
    except ValueError:
        raise OfficialSourceRegistryError("official source entry is invalid") from None
    observed = source["observed_version"]
    if observed is not None:
        observed = _bounded_string(observed, "observed_version", maximum=100)
    timestamp = _parse_utc_timestamp(source["verified_at"])
    live_probe = source["live_probe_permitted"]
    if type(live_probe) is not bool:
        raise OfficialSourceRegistryError("live_probe_permitted must be boolean")
    try:
        return OfficialSourceEntry(
            source_id=source_id,
            canonical_url=canonical_url,
            publisher=_bounded_string(source["publisher"], "publisher", maximum=100),
            source_kind=OfficialSourceKind(
                _bounded_string(source["source_kind"], "source_kind", maximum=32)
            ),
            observed_version=observed,
            content_sensitivity=OfficialSourceSensitivity(
                _bounded_string(
                    source["content_sensitivity"],
                    "content_sensitivity",
                    maximum=64,
                )
            ),
            content_capture_policy=OfficialSourceCapturePolicy(
                _bounded_string(
                    source["content_capture_policy"],
                    "content_capture_policy",
                    maximum=32,
                )
            ),
            usage_review_status=OfficialSourceUsageStatus(
                _bounded_string(
                    source["usage_review_status"],
                    "usage_review_status",
                    maximum=64,
                )
            ),
            usage_note=_bounded_string(source["usage_note"], "usage_note", maximum=500),
            live_probe_permitted=live_probe,
            verified_at=timestamp,
        )
    except ValueError:
        raise OfficialSourceRegistryError("official source entry is invalid") from None


def _strict_mapping(
    value: object,
    expected_fields: frozenset[str],
    name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise OfficialSourceRegistryError(f"{name} fields are invalid")
    if not all(isinstance(key, str) for key in value):
        raise OfficialSourceRegistryError(f"{name} keys are invalid")
    return value


def _bounded_string(value: object, name: str, *, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or value.strip() != value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise OfficialSourceRegistryError(f"{name} must be a bounded string")
    return value


def _exact_int(value: object, name: str) -> int:
    if type(value) is not int:
        raise OfficialSourceRegistryError(f"{name} must be an integer")
    return value


def _parse_utc_timestamp(value: object) -> datetime:
    text = _bounded_string(value, "verified_at", maximum=20)
    if _UTC_TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise OfficialSourceRegistryError("verified_at must use canonical UTC seconds")
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        raise OfficialSourceRegistryError("verified_at is invalid") from None


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _reject_nonfinite_number(value: str) -> object:
    raise _DuplicateKeyError(value)
