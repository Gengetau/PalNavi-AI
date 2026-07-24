"""Deterministic orchestration for content-free official-source snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from palnavi.domain.official_sources import (
    Clock,
    OfficialSourceFetchRequest,
    OfficialSourceRegistry,
    OfficialSourceSnapshotManifest,
    OfficialSourceSnapshotRecord,
    OfficialSourceTransport,
    SnapshotAcquisitionMode,
    SourceFetchFailure,
    SourceFetchOutcomeKind,
    SourceFetchSuccess,
)


@dataclass(frozen=True, slots=True)
class SystemUtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC).replace(microsecond=0)


@dataclass(frozen=True, slots=True)
class OfficialSourceAcquisitionService:
    registry: OfficialSourceRegistry
    transport: OfficialSourceTransport
    clock: Clock
    mode: SnapshotAcquisitionMode

    async def acquire(self) -> OfficialSourceSnapshotManifest:
        started_at = self.clock.now()
        records: list[OfficialSourceSnapshotRecord] = []
        for source in self.registry.sources:
            if source.live_probe_permitted:
                try:
                    outcome = await self.transport.fetch(
                        OfficialSourceFetchRequest(
                            source_id=source.source_id,
                            canonical_url=source.canonical_url,
                        )
                    )
                except Exception:
                    outcome = SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            else:
                outcome = SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            if (
                isinstance(outcome, SourceFetchSuccess)
                and outcome.metadata.final_url == source.canonical_url
            ):
                records.append(
                    OfficialSourceSnapshotRecord(
                        source_id=source.source_id,
                        outcome=outcome.kind,
                        status_code=outcome.metadata.status_code,
                        media_type=outcome.metadata.media_type,
                        etag=outcome.metadata.etag,
                        last_modified=outcome.metadata.last_modified,
                        final_url=outcome.metadata.final_url,
                        response_bytes=outcome.response_bytes,
                        content_sha256=outcome.content_sha256,
                    )
                )
            elif isinstance(outcome, SourceFetchFailure):
                records.append(
                    OfficialSourceSnapshotRecord(
                        source_id=source.source_id,
                        outcome=outcome.kind,
                        status_code=None,
                        media_type=None,
                        etag=None,
                        last_modified=None,
                        final_url=None,
                        response_bytes=None,
                        content_sha256=None,
                    )
                )
            else:
                records.append(
                    OfficialSourceSnapshotRecord(
                        source_id=source.source_id,
                        outcome=SourceFetchOutcomeKind.UNAVAILABLE,
                        status_code=None,
                        media_type=None,
                        etag=None,
                        last_modified=None,
                        final_url=None,
                        response_bytes=None,
                        content_sha256=None,
                    )
                )
        completed_at = self.clock.now()
        ordered_records = tuple(sorted(records, key=lambda record: record.source_id))
        unsigned = snapshot_manifest_payload(
            schema_version=1,
            registry_sha256=self.registry.registry_sha256,
            acquisition_mode=self.mode,
            started_at=started_at,
            completed_at=completed_at,
            records=ordered_records,
        )
        identity = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
        return OfficialSourceSnapshotManifest(
            schema_version=1,
            registry_sha256=self.registry.registry_sha256,
            acquisition_mode=self.mode,
            started_at=started_at,
            completed_at=completed_at,
            records=ordered_records,
            manifest_sha256=identity,
        )


def snapshot_manifest_document(manifest: OfficialSourceSnapshotManifest) -> dict[str, object]:
    payload = snapshot_manifest_payload(
        schema_version=manifest.schema_version,
        registry_sha256=manifest.registry_sha256,
        acquisition_mode=manifest.acquisition_mode,
        started_at=manifest.started_at,
        completed_at=manifest.completed_at,
        records=manifest.records,
    )
    return {**payload, "manifest_sha256": manifest.manifest_sha256}


def snapshot_manifest_sha256(manifest: OfficialSourceSnapshotManifest) -> str:
    payload = snapshot_manifest_payload(
        schema_version=manifest.schema_version,
        registry_sha256=manifest.registry_sha256,
        acquisition_mode=manifest.acquisition_mode,
        started_at=manifest.started_at,
        completed_at=manifest.completed_at,
        records=manifest.records,
    )
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def snapshot_manifest_payload(
    *,
    schema_version: int,
    registry_sha256: str,
    acquisition_mode: SnapshotAcquisitionMode,
    started_at: datetime,
    completed_at: datetime,
    records: tuple[OfficialSourceSnapshotRecord, ...],
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "registry_sha256": registry_sha256,
        "acquisition_mode": acquisition_mode.value,
        "started_at": format_utc(started_at),
        "completed_at": format_utc(completed_at),
        "records": [
            {
                "source_id": record.source_id,
                "outcome": record.outcome.value,
                "status_code": record.status_code,
                "media_type": record.media_type,
                "etag": record.etag,
                "last_modified": record.last_modified,
                "final_url": record.final_url,
                "response_bytes": record.response_bytes,
                "content_sha256": record.content_sha256,
                "content_persisted": record.content_persisted,
            }
            for record in records
        ],
    }


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value) or value.microsecond != 0:
        raise ValueError("timestamp must be UTC")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
