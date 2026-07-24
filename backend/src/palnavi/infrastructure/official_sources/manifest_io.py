"""Atomic, content-free snapshot manifest persistence."""

from __future__ import annotations

import json
import os
import secrets
import stat
from contextlib import suppress
from pathlib import Path

from palnavi.application import snapshot_manifest_document, snapshot_manifest_sha256
from palnavi.domain.official_sources import OfficialSourceSnapshotManifest
from palnavi.infrastructure.official_sources.registry import (
    OfficialSourceRegistryError,
    load_official_source_registry,
)


class SnapshotWriteError(ValueError):
    """Sanitized local output rejection."""


def write_snapshot_manifest(
    path: Path,
    manifest: OfficialSourceSnapshotManifest,
    *,
    replace: bool = False,
) -> None:
    if not path.is_absolute():
        raise SnapshotWriteError("snapshot output path must be absolute")
    if path.suffix != ".json":
        raise SnapshotWriteError("snapshot output must use a JSON filename")
    parent = path.parent
    try:
        if not parent.is_dir() or parent.resolve(strict=True) != parent:
            raise SnapshotWriteError("snapshot output directory is unsafe")
    except OSError:
        raise SnapshotWriteError("snapshot output directory is unavailable") from None
    try:
        current_registry_identity = load_official_source_registry().registry_sha256
    except OfficialSourceRegistryError:
        raise SnapshotWriteError("snapshot registry identity is unavailable") from None
    if manifest.registry_sha256 != current_registry_identity:
        raise SnapshotWriteError("snapshot registry identity mismatch")
    if snapshot_manifest_sha256(manifest) != manifest.manifest_sha256:
        raise SnapshotWriteError("snapshot manifest identity mismatch")

    payload = (
        json.dumps(
            snapshot_manifest_document(manifest),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()

    parent_descriptor = -1
    temporary_descriptor = -1
    temporary_name: str | None = None
    try:
        parent_descriptor = _open_directory(parent)
        try:
            target_status = os.stat(
                path.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            target_status = None
        if target_status is not None:
            if not replace:
                raise SnapshotWriteError("snapshot output already exists")
            if not stat.S_ISREG(target_status.st_mode):
                raise SnapshotWriteError("snapshot output target is not a regular file")

        temporary_name = f".{path.name}.{secrets.token_hex(12)}.tmp"
        create_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            create_flags |= os.O_NOFOLLOW
        temporary_descriptor = os.open(
            temporary_name,
            create_flags,
            0o600,
            dir_fd=parent_descriptor,
        )
        handle = os.fdopen(temporary_descriptor, "wb")
        temporary_descriptor = -1
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if replace:
            os.replace(
                temporary_name,
                path.name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
            )
            temporary_name = None
        else:
            try:
                os.link(
                    temporary_name,
                    path.name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError:
                raise SnapshotWriteError("snapshot output already exists") from None
            os.unlink(temporary_name, dir_fd=parent_descriptor)
            temporary_name = None
        os.fsync(parent_descriptor)
    except SnapshotWriteError:
        raise
    except OSError:
        raise SnapshotWriteError("snapshot output could not be written") from None
    finally:
        if temporary_descriptor >= 0:
            with suppress(OSError):
                os.close(temporary_descriptor)
        if temporary_name is not None and parent_descriptor >= 0:
            with suppress(OSError):
                os.unlink(temporary_name, dir_fd=parent_descriptor)
        if parent_descriptor >= 0:
            with suppress(OSError):
                os.close(parent_descriptor)


def _open_directory(path: Path) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        with suppress(OSError):
            os.close(descriptor)
        raise
