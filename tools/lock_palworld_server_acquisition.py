#!/usr/bin/env python3
"""Acquire and validate the pinned Palworld Linux server provenance lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "palnavi-native-acquisition-lock/v1"
LOCK_ID = "palworld-linux-server-build-24181105"
APP_ID = "2394010"
BRANCH = "public"
BUILD_ID = "24181105"
DEPOT_ID = "2394012"
MANIFEST_ID = "2167164727892555341"
MANIFEST_TIMESTAMP = "2026-07-13T09:20:38Z"
MANIFEST_BINARY_SHA256 = "3bab93b8c70d612ca5bd1a827be3d7f2d1bf92a2c1829507eca60c81a8f605ca"
MANIFEST_TEXT_SHA256 = "fbcadb5fc783a410adf72ce2d4f4145b50c1abfe12059d3457e82054d70e89e9"
MANIFEST_TOTAL_FILES = 31
MANIFEST_TOTAL_BYTES = 5_046_643_016
MANIFEST_COMPRESSED_BYTES = 4_726_439_856
PAK_PATH = "Pal/Content/Paks/Pal-LinuxServer.pak"
PAK_SIZE = 4_797_040_962
PAK_STEAM_SHA1 = "b81698aff4e50356b9c2672ecadc59a2dd840ea3"
PAK_SHA256 = "cad80fe15c38d74a795779fbab31f04bc2c15c37fb8a2188e4d89f3800fb0e68"

DEPOT_DOWNLOADER_VERSION = "3.4.0"
DEPOT_DOWNLOADER_INFORMATIONAL_VERSION = "3.4.0+c553ef4d60c00a4f5fd16c9fe017f569001589ff"
DEPOT_DOWNLOADER_RUNTIME = ".NET 9.0.0"
DEPOT_DOWNLOADER_ASSET = "DepotDownloader-linux-x64.zip"
DEPOT_DOWNLOADER_URL = (
    "https://github.com/SteamRE/DepotDownloader/releases/download/"
    "DepotDownloader_3.4.0/DepotDownloader-linux-x64.zip"
)
DEPOT_DOWNLOADER_ARCHIVE_SHA256 = "a999dec66b4850fc961bd50366696d23c2d0fad7b18790e6a5647b2f19097a53"
DEPOT_DOWNLOADER_EXECUTABLE_SHA256 = (
    "d62a1721564bdb96bacd9285bb5f96180a45202e82a9f85c6a88e5e8ee5f992c"
)

ATLAS_REPOSITORY = "https://github.com/Awy64/palworld-atlas-data.git"
ATLAS_COMMIT = "0385b3fd8bd757240d4a2c79615145122669abd5"
ATLAS_PROJECT = "src/PalworldAtlas.Extractor/PalworldAtlas.Extractor.csproj"
ATLAS_PROJECT_SHA256 = "3e40be050b850c887a9416c25d8be6d8b5cf437c7d0ca0cbf006588d86d9932a"
DOTNET_SDK_VERSION = "10.0.302"
DOTNET_SDK_ASSET = "dotnet-sdk-10.0.302-linux-x64.tar.gz"
DOTNET_SDK_URL = (
    "https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.302/dotnet-sdk-10.0.302-linux-x64.tar.gz"
)
DOTNET_SDK_ARCHIVE_SHA256 = "264a838d6f5d1a252489c7bb2e2946a579d6a881391d50ffd175a01e4d948c1c"
DEPENDENCY_LOCK_RECORD_SHA256 = "d2df63b2c44fbccd291bbfe99168d460e40dcf301e026b29c6a2e4e8648fb32b"
PROBE_RECORD_SHA256 = "5d6c8f7acb61e0e290681e260c197f19bfaee99349a0396b1ab0b904b2146b43"
SOURCE_RECORD_SHA256 = "4b711767a73660878ab442819874866eceb51f3acd23a0e55c468209235539bf"
GENERATED_RECORD_SHA256 = "fef729bdc7be39a1d670dd932bf28d3d6bcb646d6544ac3ca33568b704cc7c36"

REQUIRED_TABLES = {
    "pals",
    "breeding",
    "items",
    "wild-spawners",
    "spawner-placements",
    "alpha-spawners",
}
PROHIBITED_FRAGMENTS = (
    "/tmp/",
    "/workspace/",
    "\\users\\",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "credential",
    "access_token",
    "login_key",
)


class AcquisitionError(ValueError):
    """A sanitized acquisition-lock failure."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _pretty_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _hash_bytes(value: bytes, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    digest.update(value)
    return digest.hexdigest()


def _hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise AcquisitionError("required content-addressed input is unreadable") from error
    return digest.hexdigest()


def _record_hash(value: object) -> str:
    return _hash_bytes(_canonical_bytes(value))


def _write_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _run(
    command: list[str],
    *,
    label: str,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
    timeout: int = 7_200,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AcquisitionError(f"{label} could not complete") from error
    if completed.returncode != 0:
        raise AcquisitionError(f"{label} failed with exit code {completed.returncode}")
    return completed


def _depot_environment(work_directory: Path) -> dict[str, str]:
    environment = os.environ.copy()
    data_home = work_directory / "depotdownloader-data"
    data_home.mkdir(parents=True, exist_ok=True)
    environment["XDG_DATA_HOME"] = str(data_home)
    return environment


def _offline_dotnet_environment(
    work_directory: Path,
    nuget_packages: Path,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment["DOTNET_CLI_HOME"] = str(work_directory / "dotnet-home")
    environment["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    environment["DOTNET_NOLOGO"] = "1"
    environment["NUGET_PACKAGES"] = str(nuget_packages)
    # CUE4Parse attempts an optional Oodle download during initialization. Run
    # the probe without connector-provided network routes, then require its
    # explicit download-failure warning before accepting the result.
    for key in tuple(environment):
        if key.casefold().endswith("proxy"):
            environment.pop(key)
    return environment


def _verify_depot_downloader(
    executable: Path,
    archive: Path,
    work_directory: Path,
) -> None:
    if _hash_file(archive) != DEPOT_DOWNLOADER_ARCHIVE_SHA256:
        raise AcquisitionError("DepotDownloader archive SHA-256 does not match the lock")
    if _hash_file(executable) != DEPOT_DOWNLOADER_EXECUTABLE_SHA256:
        raise AcquisitionError("DepotDownloader executable SHA-256 does not match the lock")
    completed = _run(
        [str(executable), "-V"],
        label="DepotDownloader identity check",
        environment=_depot_environment(work_directory),
        timeout=30,
    )
    expected = (
        f"DepotDownloader v{DEPOT_DOWNLOADER_INFORMATIONAL_VERSION}\n"
        f"Runtime: {DEPOT_DOWNLOADER_RUNTIME} on "
    )
    if not completed.stdout.startswith(expected):
        raise AcquisitionError("DepotDownloader version or runtime does not match the lock")


def _manifest_paths(live_directory: Path) -> tuple[Path, Path]:
    depot_root = live_directory / "depots" / DEPOT_ID
    build_directories = sorted(
        path for path in depot_root.glob("*") if path.is_dir() and path.name.isdecimal()
    )
    if [path.name for path in build_directories] != [BUILD_ID]:
        raise AcquisitionError("live public Steam Build ID does not match the pinned build")
    build_directory = build_directories[0]
    text_path = build_directory / f"manifest_{DEPOT_ID}_{MANIFEST_ID}.txt"
    binary_path = build_directory / ".DepotDownloader" / f"{DEPOT_ID}_{MANIFEST_ID}.manifest"
    if not text_path.is_file() or not binary_path.is_file():
        raise AcquisitionError("live AppInfo did not resolve the pinned depot manifest")
    return binary_path, text_path


def _query_live_manifest(
    executable: Path,
    work_directory: Path,
) -> tuple[Path, Path]:
    live_directory = work_directory / "live-appinfo"
    live_directory.mkdir(parents=True, exist_ok=False)
    _run(
        [
            str(executable),
            "-app",
            APP_ID,
            "-depot",
            DEPOT_ID,
            "-manifest-only",
            "-branch",
            BRANCH,
            "-os",
            "linux",
            "-osarch",
            "64",
        ],
        label="live Steam AppInfo query",
        cwd=live_directory,
        environment=_depot_environment(work_directory),
    )
    return _manifest_paths(live_directory)


def _parse_manifest(binary_path: Path, text_path: Path) -> dict[str, object]:
    binary_sha256 = _hash_file(binary_path)
    text_bytes = text_path.read_bytes()
    text_sha256 = _hash_bytes(text_bytes)
    if binary_sha256 != MANIFEST_BINARY_SHA256:
        raise AcquisitionError("live manifest binary identity does not match the lock")
    if text_sha256 != MANIFEST_TEXT_SHA256:
        raise AcquisitionError("live manifest text identity does not match the lock")
    try:
        text = text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AcquisitionError("live manifest text is not UTF-8") from error

    header_patterns = {
        "manifest_id": rf"Manifest ID / date\s+:\s+({MANIFEST_ID})\s+/",
        "total_files": r"Total number of files\s+:\s+(\d+)",
        "total_bytes": r"Total bytes on disk\s+:\s+(\d+)",
        "compressed_bytes": r"Total bytes compressed\s+:\s+(\d+)",
    }
    values: dict[str, str] = {}
    for name, pattern in header_patterns.items():
        match = re.search(pattern, text)
        if match is None:
            raise AcquisitionError("live manifest text is missing required metadata")
        values[name] = match.group(1)
    if (
        values["manifest_id"] != MANIFEST_ID
        or int(values["total_files"]) != MANIFEST_TOTAL_FILES
        or int(values["total_bytes"]) != MANIFEST_TOTAL_BYTES
        or int(values["compressed_bytes"]) != MANIFEST_COMPRESSED_BYTES
    ):
        raise AcquisitionError("live manifest summary does not match the pinned identity")

    pak_pattern = re.compile(
        rf"^\s*(\d+)\s+(\d+)\s+([0-9a-f]{{40}})\s+\d+\s+{re.escape(PAK_PATH)}$",
        re.MULTILINE,
    )
    pak_match = pak_pattern.search(text)
    if pak_match is None:
        raise AcquisitionError("live manifest does not contain the selected PAK")
    pak_size, pak_chunks, pak_sha1 = pak_match.groups()
    if int(pak_size) != PAK_SIZE or pak_sha1 != PAK_STEAM_SHA1:
        raise AcquisitionError("selected PAK manifest identity does not match the lock")

    return {
        "timestamp": MANIFEST_TIMESTAMP,
        "binary_sha256": binary_sha256,
        "text_sha256": text_sha256,
        "total_files": int(values["total_files"]),
        "total_bytes_on_disk": int(values["total_bytes"]),
        "total_bytes_compressed": int(values["compressed_bytes"]),
        "selected_file_chunks": int(pak_chunks),
    }


def _acquire_pak(
    executable: Path,
    work_directory: Path,
) -> Path:
    content_directory = work_directory / "content"
    content_directory.mkdir(parents=True, exist_ok=False)
    file_list = work_directory / "filelist.txt"
    file_list.write_text(f"{PAK_PATH}\n", encoding="utf-8")
    _run(
        [
            str(executable),
            "-app",
            APP_ID,
            "-depot",
            DEPOT_ID,
            "-manifest",
            MANIFEST_ID,
            "-branch",
            BRANCH,
            "-os",
            "linux",
            "-osarch",
            "64",
            "-filelist",
            str(file_list),
            "-dir",
            str(content_directory),
        ],
        label="exact depot manifest acquisition",
        environment=_depot_environment(work_directory),
    )

    pak_path = content_directory / PAK_PATH
    materialized_files = sorted(
        path.relative_to(content_directory).as_posix()
        for path in content_directory.rglob("*")
        if path.is_file() and ".DepotDownloader" not in path.parts
    )
    if materialized_files != [PAK_PATH]:
        raise AcquisitionError("exact acquisition materialized files outside the allowlist")
    try:
        size = pak_path.stat().st_size
    except OSError as error:
        raise AcquisitionError("selected PAK was not materialized") from error
    if size != PAK_SIZE:
        raise AcquisitionError("selected PAK byte count does not match the manifest")
    if _hash_file(pak_path, "sha1") != PAK_STEAM_SHA1:
        raise AcquisitionError("selected PAK SHA-1 does not match the Steam manifest")
    if _hash_file(pak_path) != PAK_SHA256:
        raise AcquisitionError("selected PAK SHA-256 does not match the published lock")
    return pak_path


def _dependency_lock(atlas_repository: Path) -> dict[str, object]:
    assets_path = (
        atlas_repository / "src" / "PalworldAtlas.Extractor" / "obj" / "project.assets.json"
    )
    try:
        assets = json.loads(assets_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError(
            "Atlas dependency assets are absent; restore the pinned project first"
        ) from error
    libraries = assets.get("libraries")
    if not isinstance(libraries, dict):
        raise AcquisitionError("Atlas dependency assets are malformed")

    packages: list[dict[str, str]] = []
    for identity, metadata in sorted(libraries.items()):
        if not isinstance(metadata, dict) or metadata.get("type") != "package":
            continue
        sha512 = metadata.get("sha512")
        if not isinstance(identity, str) or not isinstance(sha512, str):
            raise AcquisitionError("Atlas dependency asset lacks a content hash")
        packages.append({"identity": identity, "content_sha512": sha512})
    if not packages:
        raise AcquisitionError("Atlas dependency lock contains no packages")
    return {
        "format": "sanitized-nuget-project-assets/v1",
        "package_count": len(packages),
        "packages": packages,
        "record_sha256": _record_hash(packages),
    }


def _verify_atlas_repository(atlas_repository: Path) -> dict[str, object]:
    head = _run(
        ["git", "-C", str(atlas_repository), "rev-parse", "HEAD"],
        label="Atlas commit check",
        timeout=30,
    ).stdout.strip()
    if head != ATLAS_COMMIT:
        raise AcquisitionError("Atlas repository is not at the pinned commit")
    tracked_status = _run(
        [
            "git",
            "-C",
            str(atlas_repository),
            "status",
            "--short",
            "--untracked-files=no",
        ],
        label="Atlas tracked-worktree check",
        timeout=30,
    ).stdout
    if tracked_status:
        raise AcquisitionError("Atlas repository has tracked modifications")
    project_path = atlas_repository / ATLAS_PROJECT
    if _hash_file(project_path) != ATLAS_PROJECT_SHA256:
        raise AcquisitionError("Atlas project file does not match the pinned commit")
    return {
        "repository": ATLAS_REPOSITORY,
        "commit": ATLAS_COMMIT,
        "project": ATLAS_PROJECT,
        "project_sha256": ATLAS_PROJECT_SHA256,
        "dependency_lock": _dependency_lock(atlas_repository),
    }


def _sanitize_probe(report: dict[str, Any]) -> dict[str, object]:
    if report.get("steamBuildId") != BUILD_ID:
        raise AcquisitionError("Atlas probe reported the wrong Steam Build ID")
    if report.get("pakBytes") != PAK_SIZE:
        raise AcquisitionError("Atlas probe read an unexpected PAK byte count")
    if report.get("mappingsProvided") is not False:
        raise AcquisitionError("Atlas probe unexpectedly used a mappings file")
    if report.get("productionGatePassed") is not True:
        raise AcquisitionError("Atlas probe production gate did not pass")
    raw_tables = report.get("tables")
    if not isinstance(raw_tables, list):
        raise AcquisitionError("Atlas probe table evidence is malformed")

    tables: list[dict[str, object]] = []
    by_name: dict[str, dict[str, Any]] = {}
    for raw_table in raw_tables:
        if not isinstance(raw_table, dict) or not isinstance(raw_table.get("name"), str):
            raise AcquisitionError("Atlas probe contains a malformed table result")
        by_name[raw_table["name"]] = raw_table
        fields = raw_table.get("sampleFields")
        if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
            raise AcquisitionError("Atlas probe sample fields are malformed")
        table: dict[str, object] = {
            "name": raw_table["name"],
            "present": raw_table.get("present"),
            "parsed": raw_table.get("parsed"),
            "row_count": raw_table.get("rowCount"),
            "sample_field_count": len(fields),
            "sample_fields_sha256": _record_hash(fields),
        }
        package_path = raw_table.get("packagePath")
        if package_path is not None:
            table["package_path"] = package_path
        error = raw_table.get("error")
        if error is not None:
            table["error"] = error
        tables.append(table)

    if not by_name.keys() >= REQUIRED_TABLES:
        raise AcquisitionError("Atlas probe omitted a required table")
    if any(
        by_name[name].get("parsed") is not True
        or not isinstance(by_name[name].get("rowCount"), int)
        or by_name[name]["rowCount"] <= 0
        for name in REQUIRED_TABLES
    ):
        raise AcquisitionError("Atlas probe could not parse every required table")

    evidence = {
        "steam_build_id": BUILD_ID,
        "pak_bytes": PAK_SIZE,
        "mappings": {
            "status": "mappings_not_required",
            "identity": None,
            "sha256": None,
        },
        "production_gate_passed": True,
        "required_tables": sorted(REQUIRED_TABLES),
        "tables": tables,
    }
    evidence["record_sha256"] = _record_hash(evidence)
    return evidence


def _run_atlas_probe(
    atlas_repository: Path,
    dotnet: Path,
    dotnet_archive: Path,
    nuget_packages: Path,
    pak_path: Path,
    work_directory: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    if _hash_file(dotnet_archive) != DOTNET_SDK_ARCHIVE_SHA256:
        raise AcquisitionError(".NET SDK archive SHA-256 does not match the lock")
    version = _run(
        [str(dotnet), "--version"],
        label=".NET SDK identity check",
        environment=_offline_dotnet_environment(work_directory, nuget_packages),
        timeout=30,
    ).stdout.strip()
    if version != DOTNET_SDK_VERSION:
        raise AcquisitionError(".NET SDK version does not match the lock")

    atlas_identity = _verify_atlas_repository(atlas_repository)
    project_path = atlas_repository / ATLAS_PROJECT
    offline_environment = _offline_dotnet_environment(work_directory, nuget_packages)
    _run(
        [
            str(dotnet),
            "build",
            str(project_path),
            "--configuration",
            "Release",
            "--no-restore",
        ],
        label="offline Atlas build",
        cwd=atlas_repository,
        environment=offline_environment,
    )
    probe_path = work_directory / "atlas-probe.json"
    completed = _run(
        [
            str(dotnet),
            "run",
            "--project",
            str(project_path),
            "--configuration",
            "Release",
            "--no-build",
            "--",
            "probe",
            "--pak-dir",
            str(pak_path.parent),
            "--output",
            str(probe_path),
            "--build-id",
            BUILD_ID,
        ],
        label="offline Atlas no-mappings probe",
        cwd=atlas_repository,
        environment=offline_environment,
    )
    probe_diagnostics = f"{completed.stdout}\n{completed.stderr}".casefold()
    if "oodle decompression failed: unable to download oodle dll" not in probe_diagnostics:
        raise AcquisitionError(
            "Atlas probe did not prove that the optional unpinned Oodle binary was unavailable"
        )
    try:
        report = json.loads(probe_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError("Atlas probe did not emit valid JSON") from error
    if not isinstance(report, dict):
        raise AcquisitionError("Atlas probe root is malformed")
    runtime = {
        "name": ".NET SDK",
        "version": DOTNET_SDK_VERSION,
        "asset": DOTNET_SDK_ASSET,
        "asset_url": DOTNET_SDK_URL,
        "archive_sha256": DOTNET_SDK_ARCHIVE_SHA256,
    }
    return atlas_identity | {"runtime": runtime}, _sanitize_probe(report)


def _assemble_lock(
    *,
    observed_at: str,
    manifest: dict[str, object],
    atlas: dict[str, object],
    probe: dict[str, object],
) -> dict[str, object]:
    lock: dict[str, object] = {
        "schema": SCHEMA,
        "lock_id": LOCK_ID,
        "observed_at": observed_at,
        "scope": {
            "game": "Palworld",
            "platform": "Linux dedicated server",
            "source_patch_context": "v1.0.1",
            "runtime_status": "acquisition_provenance_only_not_activated",
            "claim_limits": [
                "This lock does not describe PC client-only assets or behavior.",
                "This lock does not activate or enrich the PalNavi runtime dataset.",
                "This lock contains no proprietary game bytes or extracted table rows.",
            ],
        },
        "steam": {
            "app_id": APP_ID,
            "branch": BRANCH,
            "build_id": BUILD_ID,
            "depot_id": DEPOT_ID,
            "manifest_id": MANIFEST_ID,
            "manifest": manifest,
            "selected_file": {
                "path": PAK_PATH,
                "size_bytes": PAK_SIZE,
                "steam_manifest_sha1": PAK_STEAM_SHA1,
                "local_sha256": PAK_SHA256,
            },
        },
        "acquisition_tool": {
            "name": "DepotDownloader",
            "version": DEPOT_DOWNLOADER_VERSION,
            "informational_version": DEPOT_DOWNLOADER_INFORMATIONAL_VERSION,
            "runtime": DEPOT_DOWNLOADER_RUNTIME,
            "asset": DEPOT_DOWNLOADER_ASSET,
            "asset_url": DEPOT_DOWNLOADER_URL,
            "archive_sha256": DEPOT_DOWNLOADER_ARCHIVE_SHA256,
            "executable_sha256": DEPOT_DOWNLOADER_EXECUTABLE_SHA256,
        },
        "extractor": atlas | {"probe": probe},
        "generation": {
            "tool": "tools/lock_palworld_server_acquisition.py",
            "serialization": "UTF-8 JSON, two-space indentation, LF terminator",
            "deterministic": True,
        },
    }
    lock["integrity"] = {
        "source_record_sha256": _record_hash(
            {
                "manifest": manifest,
                "selected_file_sha256": PAK_SHA256,
                "atlas_dependency_lock": atlas["dependency_lock"],
                "probe_record_sha256": probe["record_sha256"],
            }
        ),
        "generated_record_sha256": _record_hash(lock),
    }
    return lock


def _require_iso_utc_seconds(value: str) -> None:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None:
        raise AcquisitionError(
            "--observed-at must be an explicit UTC timestamp with second precision"
        )


def generate_lock(
    *,
    lock_path: Path,
    work_directory: Path,
    observed_at: str,
    depot_downloader: Path,
    depot_downloader_archive: Path,
    atlas_repository: Path,
    dotnet: Path,
    dotnet_archive: Path,
    nuget_packages: Path,
) -> dict[str, object]:
    _require_iso_utc_seconds(observed_at)
    if work_directory.exists():
        raise AcquisitionError("generation work directory must not already exist")
    work_directory.mkdir(parents=True)
    _verify_depot_downloader(
        depot_downloader,
        depot_downloader_archive,
        work_directory,
    )
    binary_manifest, text_manifest = _query_live_manifest(
        depot_downloader,
        work_directory,
    )
    manifest = _parse_manifest(binary_manifest, text_manifest)
    pak_path = _acquire_pak(depot_downloader, work_directory)
    atlas, probe = _run_atlas_probe(
        atlas_repository,
        dotnet,
        dotnet_archive,
        nuget_packages,
        pak_path,
        work_directory,
    )
    lock = _assemble_lock(
        observed_at=observed_at,
        manifest=manifest,
        atlas=atlas,
        probe=probe,
    )
    serialized_once = _pretty_bytes(lock)
    serialized_twice = _pretty_bytes(
        _assemble_lock(
            observed_at=observed_at,
            manifest=manifest,
            atlas=atlas,
            probe=probe,
        )
    )
    if serialized_once != serialized_twice:
        raise AcquisitionError("lock generation is not byte-deterministic")
    validate_lock(lock)
    _write_atomic(lock_path, serialized_once)
    return lock


def _expect(value: object, expected: object, message: str) -> None:
    if value != expected:
        raise AcquisitionError(message)


def validate_lock(lock: dict[str, Any]) -> None:
    _expect(lock.get("schema"), SCHEMA, "lock schema is unsupported")
    _expect(lock.get("lock_id"), LOCK_ID, "lock identifier is unexpected")
    observed_at = lock.get("observed_at")
    if not isinstance(observed_at, str):
        raise AcquisitionError("lock observation timestamp is missing")
    _require_iso_utc_seconds(observed_at)

    steam = lock.get("steam")
    if not isinstance(steam, dict):
        raise AcquisitionError("Steam identity is missing")
    for name, expected in (
        ("app_id", APP_ID),
        ("branch", BRANCH),
        ("build_id", BUILD_ID),
        ("depot_id", DEPOT_ID),
        ("manifest_id", MANIFEST_ID),
    ):
        _expect(steam.get(name), expected, f"Steam {name} is not pinned")
    selected_file = steam.get("selected_file")
    if not isinstance(selected_file, dict):
        raise AcquisitionError("selected PAK identity is missing")
    for name, expected in (
        ("path", PAK_PATH),
        ("size_bytes", PAK_SIZE),
        ("steam_manifest_sha1", PAK_STEAM_SHA1),
        ("local_sha256", PAK_SHA256),
    ):
        _expect(selected_file.get(name), expected, f"selected PAK {name} is not pinned")

    manifest = steam.get("manifest")
    expected_manifest = {
        "timestamp": MANIFEST_TIMESTAMP,
        "binary_sha256": MANIFEST_BINARY_SHA256,
        "text_sha256": MANIFEST_TEXT_SHA256,
        "total_files": MANIFEST_TOTAL_FILES,
        "total_bytes_on_disk": MANIFEST_TOTAL_BYTES,
        "total_bytes_compressed": MANIFEST_COMPRESSED_BYTES,
        "selected_file_chunks": 4622,
    }
    _expect(
        manifest,
        expected_manifest,
        "manifest evidence does not match the pinned record",
    )

    acquisition_tool = lock.get("acquisition_tool")
    if not isinstance(acquisition_tool, dict):
        raise AcquisitionError("acquisition tool identity is missing")
    for name, expected in (
        ("name", "DepotDownloader"),
        ("version", DEPOT_DOWNLOADER_VERSION),
        ("informational_version", DEPOT_DOWNLOADER_INFORMATIONAL_VERSION),
        ("runtime", DEPOT_DOWNLOADER_RUNTIME),
        ("asset", DEPOT_DOWNLOADER_ASSET),
        ("asset_url", DEPOT_DOWNLOADER_URL),
        ("archive_sha256", DEPOT_DOWNLOADER_ARCHIVE_SHA256),
        ("executable_sha256", DEPOT_DOWNLOADER_EXECUTABLE_SHA256),
    ):
        _expect(
            acquisition_tool.get(name),
            expected,
            f"acquisition tool {name} is not pinned",
        )

    extractor = lock.get("extractor")
    if not isinstance(extractor, dict):
        raise AcquisitionError("extractor identity is missing")
    for name, expected in (
        ("repository", ATLAS_REPOSITORY),
        ("commit", ATLAS_COMMIT),
        ("project", ATLAS_PROJECT),
        ("project_sha256", ATLAS_PROJECT_SHA256),
    ):
        _expect(extractor.get(name), expected, f"extractor {name} is not pinned")
    runtime = extractor.get("runtime")
    if not isinstance(runtime, dict):
        raise AcquisitionError("extractor runtime identity is missing")
    for name, expected in (
        ("name", ".NET SDK"),
        ("version", DOTNET_SDK_VERSION),
        ("asset", DOTNET_SDK_ASSET),
        ("asset_url", DOTNET_SDK_URL),
        ("archive_sha256", DOTNET_SDK_ARCHIVE_SHA256),
    ):
        _expect(runtime.get(name), expected, f"extractor runtime {name} is not pinned")

    dependency_lock = extractor.get("dependency_lock")
    if not isinstance(dependency_lock, dict):
        raise AcquisitionError("extractor dependency lock is missing")
    packages = dependency_lock.get("packages")
    if not isinstance(packages, list) or not packages:
        raise AcquisitionError("extractor dependency package graph is empty")
    _expect(
        dependency_lock.get("package_count"),
        len(packages),
        "extractor dependency package count is inconsistent",
    )
    _expect(
        dependency_lock.get("record_sha256"),
        _record_hash(packages),
        "extractor dependency package graph hash is invalid",
    )
    _expect(
        dependency_lock.get("record_sha256"),
        DEPENDENCY_LOCK_RECORD_SHA256,
        "extractor dependency package graph is not the reviewed graph",
    )

    probe = extractor.get("probe")
    if not isinstance(probe, dict):
        raise AcquisitionError("extractor probe evidence is missing")
    probe_without_hash = {key: value for key, value in probe.items() if key != "record_sha256"}
    _expect(
        probe.get("record_sha256"),
        _record_hash(probe_without_hash),
        "extractor probe evidence hash is invalid",
    )
    _expect(
        probe.get("record_sha256"),
        PROBE_RECORD_SHA256,
        "extractor probe evidence is not the reviewed result",
    )
    _expect(probe.get("steam_build_id"), BUILD_ID, "probe Build ID is unexpected")
    _expect(probe.get("pak_bytes"), PAK_SIZE, "probe PAK byte count is unexpected")
    _expect(probe.get("production_gate_passed"), True, "probe production gate did not pass")
    _expect(
        probe.get("required_tables"),
        sorted(REQUIRED_TABLES),
        "probe required table set is unexpected",
    )
    mappings = probe.get("mappings")
    _expect(
        mappings,
        {"status": "mappings_not_required", "identity": None, "sha256": None},
        "probe mappings result is not fail-closed",
    )

    integrity = lock.get("integrity")
    if not isinstance(integrity, dict):
        raise AcquisitionError("lock integrity record is missing")
    lock_without_integrity = {key: value for key, value in lock.items() if key != "integrity"}
    _expect(
        integrity.get("generated_record_sha256"),
        _record_hash(lock_without_integrity),
        "generated lock record hash is invalid",
    )
    _expect(
        integrity.get("generated_record_sha256"),
        GENERATED_RECORD_SHA256,
        "generated lock record is not the reviewed artifact",
    )
    expected_source_hash = _record_hash(
        {
            "manifest": manifest,
            "selected_file_sha256": PAK_SHA256,
            "atlas_dependency_lock": dependency_lock,
            "probe_record_sha256": probe["record_sha256"],
        }
    )
    _expect(
        integrity.get("source_record_sha256"),
        expected_source_hash,
        "source evidence record hash is invalid",
    )
    _expect(
        integrity.get("source_record_sha256"),
        SOURCE_RECORD_SHA256,
        "source evidence is not the reviewed record",
    )

    serialized = _canonical_bytes(lock).decode("utf-8").lower()
    if any(fragment in serialized for fragment in PROHIBITED_FRAGMENTS):
        raise AcquisitionError(
            "lock contains a prohibited path, environment value, or secret marker"
        )


def load_and_validate(lock_path: Path) -> dict[str, Any]:
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError("lock file is unreadable or malformed") from error
    if not isinstance(lock, dict):
        raise AcquisitionError("lock root must be an object")
    validate_lock(lock)
    if lock_path.read_bytes() != _pretty_bytes(lock):
        raise AcquisitionError("lock serialization is not canonical")
    return lock


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--observed-at")
    parser.add_argument("--depot-downloader", type=Path)
    parser.add_argument("--depot-downloader-archive", type=Path)
    parser.add_argument("--atlas-repo", type=Path)
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--dotnet-sdk-archive", type=Path)
    parser.add_argument("--nuget-packages", type=Path)
    return parser


def _resolve_cli_paths(arguments: argparse.Namespace) -> None:
    for name in (
        "lock",
        "work_dir",
        "depot_downloader",
        "depot_downloader_archive",
        "atlas_repo",
        "dotnet",
        "dotnet_sdk_archive",
        "nuget_packages",
    ):
        path = getattr(arguments, name)
        if path is not None:
            setattr(arguments, name, path.resolve())


def main() -> int:
    arguments = _parser().parse_args()
    _resolve_cli_paths(arguments)
    try:
        if arguments.validate_only:
            generation_values = (
                arguments.work_dir,
                arguments.observed_at,
                arguments.depot_downloader,
                arguments.depot_downloader_archive,
                arguments.atlas_repo,
                arguments.dotnet,
                arguments.dotnet_sdk_archive,
                arguments.nuget_packages,
            )
            if any(value is not None for value in generation_values):
                raise AcquisitionError("--validate-only does not accept generation inputs")
            load_and_validate(arguments.lock)
            print(f"native acquisition lock valid: {arguments.lock.name}")
            return 0

        required = {
            "--work-dir": arguments.work_dir,
            "--observed-at": arguments.observed_at,
            "--depot-downloader": arguments.depot_downloader,
            "--depot-downloader-archive": arguments.depot_downloader_archive,
            "--atlas-repo": arguments.atlas_repo,
            "--dotnet": arguments.dotnet,
            "--dotnet-sdk-archive": arguments.dotnet_sdk_archive,
            "--nuget-packages": arguments.nuget_packages,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise AcquisitionError(f"generation requires: {', '.join(missing)}")
        generate_lock(
            lock_path=arguments.lock,
            work_directory=arguments.work_dir,
            observed_at=arguments.observed_at,
            depot_downloader=arguments.depot_downloader,
            depot_downloader_archive=arguments.depot_downloader_archive,
            atlas_repository=arguments.atlas_repo,
            dotnet=arguments.dotnet,
            dotnet_archive=arguments.dotnet_sdk_archive,
            nuget_packages=arguments.nuget_packages,
        )
        print(f"native acquisition lock generated: {arguments.lock.name}")
        return 0
    except AcquisitionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
