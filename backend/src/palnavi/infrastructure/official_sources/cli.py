"""Narrow CLI for metadata-only official-source snapshot manifests."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from palnavi.application import OfficialSourceAcquisitionService, SystemUtcClock
from palnavi.domain.official_sources import (
    OfficialSourceSnapshotManifest,
    SnapshotAcquisitionMode,
)
from palnavi.infrastructure.official_sources.manifest_io import (
    SnapshotWriteError,
    write_snapshot_manifest,
)
from palnavi.infrastructure.official_sources.mock import (
    DeterministicMockClock,
    DeterministicMockOfficialSourceTransport,
)
from palnavi.infrastructure.official_sources.registry import (
    OfficialSourceRegistryError,
    load_official_source_registry,
)
from palnavi.infrastructure.official_sources.transport import (
    HttpxOfficialSourceTransport,
)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a content-free official-source metadata manifest"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live-metadata", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(arguments)

    try:
        manifest = asyncio.run(_acquire(live_metadata=args.live_metadata))
        write_snapshot_manifest(args.output, manifest, replace=args.replace)
    except (
        OfficialSourceRegistryError,
        SnapshotWriteError,
        OSError,
        RuntimeError,
        ValueError,
    ):
        print("official source snapshot failed safely", file=sys.stderr)
        return 2

    counts = Counter(record.outcome.value for record in manifest.records)
    summary: dict[str, object] = {
        "mode": manifest.acquisition_mode.value,
        "record_count": len(manifest.records),
        "outcomes": dict(sorted(counts.items())),
        "manifest_sha256": manifest.manifest_sha256,
    }
    print(json.dumps(summary, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    return 0


async def _acquire(
    *,
    live_metadata: bool,
) -> OfficialSourceSnapshotManifest:
    registry = load_official_source_registry()
    if not live_metadata:
        return await OfficialSourceAcquisitionService(
            registry=registry,
            transport=DeterministicMockOfficialSourceTransport(),
            clock=DeterministicMockClock(),
            mode=SnapshotAcquisitionMode.SYNTHETIC_MOCK,
        ).acquire()

    transport = HttpxOfficialSourceTransport()
    try:
        return await OfficialSourceAcquisitionService(
            registry=registry,
            transport=transport,
            clock=SystemUtcClock(),
            mode=SnapshotAcquisitionMode.LIVE_METADATA,
        ).acquire()
    finally:
        await transport.aclose()


if __name__ == "__main__":
    raise SystemExit(main())
