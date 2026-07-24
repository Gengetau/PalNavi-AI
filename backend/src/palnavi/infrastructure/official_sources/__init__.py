"""Strict official-source registry, transport, mock, and snapshot adapters."""

from palnavi.infrastructure.official_sources.manifest_io import (
    SnapshotWriteError,
    write_snapshot_manifest,
)
from palnavi.infrastructure.official_sources.mock import (
    DeterministicMockClock,
    DeterministicMockOfficialSourceTransport,
)
from palnavi.infrastructure.official_sources.registry import (
    ALLOWED_OFFICIAL_HOSTS,
    AUTHORIZED_SOURCE_URLS,
    OfficialSourceRegistryError,
    default_official_source_registry_path,
    load_official_source_registry,
    official_source_registry_payload,
    official_source_registry_sha256,
    parse_official_source_registry,
    validate_official_source_request,
)
from palnavi.infrastructure.official_sources.transport import (
    HttpxOfficialSourceTransport,
)

__all__ = [
    "ALLOWED_OFFICIAL_HOSTS",
    "AUTHORIZED_SOURCE_URLS",
    "DeterministicMockClock",
    "DeterministicMockOfficialSourceTransport",
    "HttpxOfficialSourceTransport",
    "OfficialSourceRegistryError",
    "SnapshotWriteError",
    "default_official_source_registry_path",
    "load_official_source_registry",
    "official_source_registry_payload",
    "official_source_registry_sha256",
    "parse_official_source_registry",
    "validate_official_source_request",
    "write_snapshot_manifest",
]
