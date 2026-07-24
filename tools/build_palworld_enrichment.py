#!/usr/bin/env python3
"""Build and validate the stored-but-inactive Palworld record enrichment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import lock_palworld_server_acquisition as acquisition

DATASET_ID = "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47"
ENRICHMENT_ID = f"{DATASET_ID}-deterministic-enrichment-v1"
CREATED_AT = "2026-07-24T09:54:00Z"
PALCALC_REPOSITORY = "https://github.com/tylercamp/palcalc"
PALCALC_COMMIT = "8b7e2f779e47fddae16ddcb973e828ba20c02b80"
ATLAS_REPOSITORY = "https://github.com/Awy64/palworld-atlas-data.git"
ATLAS_COMMIT = "0385b3fd8bd757240d4a2c79615145122669abd5"
ATLAS_PROJECT = "src/PalworldAtlas.Extractor/PalworldAtlas.Extractor.csproj"
ATLAS_PROJECT_SHA256 = "3e40be050b850c887a9416c25d8be6d8b5cf437c7d0ca0cbf006588d86d9932a"
ATLAS_LICENSE_SOURCE_SHA256 = "46c6b7eae9ee308e80c8876a72cc277e8ef32891dea4e2c4eb440e43c2b4dbeb"
ATLAS_LICENSE_SOURCE_GIT_BLOB_SHA1 = "1e40d35969c34af2e3f1c762f330d98b2f23476e"
ATLAS_LICENSE_OUTPUT_SHA256 = "b88ccccdda36c466e1f74db2c5d97edac73edffa382ec7c92fbc8651daca6694"
ATLAS_PATCH_SHA256 = "462761bdb29e8992f21af050d563d2f8a32bb02ce4b4724499518c699b7e3feb"
NATIVE_SNAPSHOT_SHA256 = "5a9aa34bf870fa6270fedacc7dbc3a991d83ef7907ab1a301766fd8fd52f1da9"
ACQUISITION_LOCK_SHA256 = "57e19c299c805995b3efa3b8b442f12040fdd2396d761d638677098388223307"
ROSTER_CLASSIFICATION_SHA256 = "4a9de3ea0560f7053366c2bcfa053f059c7b2aaaffc46bb355e0774ab841d61c"
PALCALC_DB_SHA256 = "803d891afdb18bd00e24332844a7276bbe5c0855170ef90ef142f2f4d7698ed1"
PALCALC_DB_GIT_BLOB_SHA1 = "82ef55ab1f26a8c4fd032eb29a9aab0ddb1532eb"
PALCALC_CSV_SHA256 = "01eb3aae31c82c9ed2160bb1d08ec5230516698f50a4025725e36cb5ded52561"
PALCALC_CSV_GIT_BLOB_SHA1 = "6ae6fca1ecd13984ee42fac1ad63605c5d0cd58a"
PAL_TABLE_PATH = "Pal/Content/Pal/DataTable/Character/DT_PalMonsterParameter"
ACTIVE_SKILL_TABLE_PATH = "Pal/Content/Pal/DataTable/Waza/DT_WazaMasterLevel"
PAL_FIELDS = [
    "ElementType1",
    "ElementType2",
    "MaleProbability",
    "PassiveSkill1",
    "PassiveSkill2",
    "PassiveSkill3",
    "PassiveSkill4",
]
ACTIVE_SKILL_FIELDS = ["PalID", "WazaID", "Level"]
PAL_TABLE_HASH = "c967739d5da54e14362a7e09e71b6edc8d6d69ab9c2231f0a41c17c632454b96"
ACTIVE_SKILL_TABLE_HASH = "f4ec51af9d46b997e54fe597461c650012cc04dbbc588817c2818f81f172e341"
ENRICHMENT_FIELDS = {
    "canonical_paldeck_member",
    "roster_class",
    "elements",
    "male_probability",
    "female_probability",
    "active_skill_learnset",
    "guaranteed_passive_skill_ids",
}
EXPECTED_COUNTS = {
    "pal_records": 299,
    "canonical_paldeck": 287,
    "terraria_collaboration_entity": 11,
    "internal_duplicate_form": 1,
    "native_pal_rows": 753,
    "native_pal_rows_joined": 299,
    "native_pal_rows_excluded": 454,
    "native_active_skill_rows": 5_772,
    "native_active_skill_rows_joined": 2_356,
    "native_active_skill_rows_excluded": 3_416,
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
OUTPUT_NAMES = (
    "ATLAS-LICENSE.txt",
    "native-pal-fields.json",
    "pal-enrichment.json",
    "palcalc-native-diff.json",
    "roster-classification.json",
)


class EnrichmentError(ValueError):
    """A sanitized deterministic enrichment failure."""


def _canonical_bytes(value: object, *, sort_keys: bool = True) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=sort_keys,
    ).encode("utf-8")


def _pretty_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EnrichmentError("required content-addressed input is unreadable") from error
    return digest.hexdigest()


def _git_blob_sha1(value: bytes) -> str:
    header = f"blob {len(value)}\0".encode()
    return hashlib.sha1(header + value, usedforsecurity=False).hexdigest()


def _record_hash(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _native_record_hash(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value, sort_keys=False))


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


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise EnrichmentError(f"{label} is unreadable") from error


def _read_json(path: Path, label: str) -> dict[str, Any]:
    value = _read_bytes(path, label)
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EnrichmentError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(parsed, dict):
        raise EnrichmentError(f"{label} root must be an object")
    return parsed


def _run(command: list[str], label: str) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EnrichmentError(f"{label} could not complete") from error
    if completed.returncode != 0:
        raise EnrichmentError(f"{label} failed with exit code {completed.returncode}")
    return completed.stdout.strip()


def _verify_git_source(repository: Path, expected_head: str, label: str) -> None:
    head = _run(["git", "-C", str(repository), "rev-parse", "HEAD"], f"{label} Head check")
    if head != expected_head:
        raise EnrichmentError(f"{label} Head does not match the source lock")
    tracked = _run(
        ["git", "-C", str(repository), "status", "--short", "--untracked-files=no"],
        f"{label} tracked-worktree check",
    )
    if tracked:
        raise EnrichmentError(f"{label} tracked worktree is modified")


def _verify_locked_file(
    path: Path,
    *,
    sha256: str,
    git_blob_sha1: str | None,
    label: str,
) -> bytes:
    value = _read_bytes(path, label)
    if _sha256_bytes(value) != sha256:
        raise EnrichmentError(f"{label} SHA-256 does not match the source lock")
    if git_blob_sha1 is not None and _git_blob_sha1(value) != git_blob_sha1:
        raise EnrichmentError(f"{label} Git blob identity does not match the source lock")
    return value


def _strip_enum(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EnrichmentError(f"{label} is missing")
    return value.rsplit("::", 1)[-1]


def _verify_native_table(
    table: object,
    *,
    name: str,
    package_path: str,
    fields: list[str],
    row_count: int,
    table_hash: str,
    value_fields: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(table, dict):
        raise EnrichmentError(f"native {name} table is missing")
    if (
        table.get("name") != name
        or table.get("packagePath") != package_path
        or table.get("selectedFields") != fields
        or table.get("rowCount") != row_count
    ):
        raise EnrichmentError(f"native {name} table identity is invalid")
    rows = table.get("rows")
    if not isinstance(rows, list) or len(rows) != row_count:
        raise EnrichmentError(f"native {name} source row count is invalid")
    source_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "sourceRowId",
            "sourceRowSha256",
            "sourceFields",
            "values",
        }:
            raise EnrichmentError(f"native {name} source row contract is invalid")
        source_row_id = row.get("sourceRowId")
        values = row.get("values")
        if (
            not isinstance(source_row_id, str)
            or not source_row_id
            or row.get("sourceFields") != fields
            or not isinstance(values, dict)
            or set(values) != value_fields
        ):
            raise EnrichmentError(f"native {name} selected fields are invalid")
        expected_hash = _native_record_hash(
            {
                "sourceRowId": source_row_id,
                "sourceFields": fields,
                "values": values,
            }
        )
        if row.get("sourceRowSha256") != expected_hash:
            raise EnrichmentError(f"native {name} source row hash is invalid")
        source_ids.append(source_row_id)
    if source_ids != sorted(source_ids) or len(source_ids) != len(set(source_ids)):
        raise EnrichmentError(f"native {name} source row order or identity is invalid")
    expected_table_hash = _native_record_hash(
        {
            "packagePath": package_path,
            "selectedFields": fields,
            "rows": rows,
        }
    )
    if (
        table.get("selectedFieldsSha256") != expected_table_hash
        or expected_table_hash != table_hash
    ):
        raise EnrichmentError(f"native {name} selected-field table hash is invalid")
    return rows


def _load_native_snapshot(
    path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if _sha256_file(path) != NATIVE_SNAPSHOT_SHA256:
        raise EnrichmentError(
            "native snapshot byte identity does not match the reviewed extraction"
        )
    snapshot = _read_json(path, "native snapshot")
    if {
        "schemaVersion": snapshot.get("schemaVersion"),
        "contract": snapshot.get("contract"),
        "steamBuildId": snapshot.get("steamBuildId"),
        "pakBytes": snapshot.get("pakBytes"),
        "mappingsProvided": snapshot.get("mappingsProvided"),
    } != {
        "schemaVersion": 1,
        "contract": "palnavi-atlas-enrichment/v1",
        "steamBuildId": acquisition.BUILD_ID,
        "pakBytes": acquisition.PAK_SIZE,
        "mappingsProvided": False,
    }:
        raise EnrichmentError("native snapshot acquisition identity is invalid")
    pal_rows = _verify_native_table(
        snapshot.get("palTable"),
        name="pals",
        package_path=PAL_TABLE_PATH,
        fields=PAL_FIELDS,
        row_count=EXPECTED_COUNTS["native_pal_rows"],
        table_hash=PAL_TABLE_HASH,
        value_fields={
            "elementType1",
            "elementType2",
            "maleProbability",
            "passiveSkill1",
            "passiveSkill2",
            "passiveSkill3",
            "passiveSkill4",
        },
    )
    skill_rows = _verify_native_table(
        snapshot.get("activeSkillTable"),
        name="active-skill-learnset",
        package_path=ACTIVE_SKILL_TABLE_PATH,
        fields=ACTIVE_SKILL_FIELDS,
        row_count=EXPECTED_COUNTS["native_active_skill_rows"],
        table_hash=ACTIVE_SKILL_TABLE_HASH,
        value_fields={"palId", "wazaId", "level"},
    )
    return snapshot, pal_rows, skill_rows


def _load_roster(
    roster_path: Path,
    pals: list[dict[str, Any]],
) -> tuple[bytes, dict[str, dict[str, Any]]]:
    roster_bytes = _verify_locked_file(
        roster_path,
        sha256=ROSTER_CLASSIFICATION_SHA256,
        git_blob_sha1=None,
        label="roster classification",
    )
    try:
        roster = json.loads(roster_bytes)
    except json.JSONDecodeError as error:
        raise EnrichmentError("roster classification is malformed") from error
    rule = roster.get("classification_rule") if isinstance(roster, dict) else None
    overrides = rule.get("overrides") if isinstance(rule, dict) else None
    if not isinstance(overrides, list) or len(overrides) != 12:
        raise EnrichmentError("roster classification overrides are invalid")
    override_by_name: dict[str, dict[str, Any]] = {}
    for override in overrides:
        if not isinstance(override, dict):
            raise EnrichmentError("roster classification override is malformed")
        source_name = override.get("source_internal_name")
        if not isinstance(source_name, str) or source_name in override_by_name:
            raise EnrichmentError("roster classification override identity is invalid")
        override_by_name[source_name] = override

    classification: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for pal in pals:
        source_name = pal.get("source_internal_name")
        if not isinstance(source_name, str) or source_name in classification:
            raise EnrichmentError("dataset Pal source identity is invalid")
        override = override_by_name.get(source_name)
        if override is None:
            value = {
                "canonical_paldeck_member": True,
                "roster_class": "canonical_paldeck",
            }
        else:
            if override.get("paldex_number") != pal.get("paldex_number") or override.get(
                "english_name"
            ) != pal.get("localized_names", {}).get("en"):
                raise EnrichmentError("roster override no longer matches its Pal record")
            value = {
                "canonical_paldeck_member": override.get("canonical_paldeck_member"),
                "roster_class": override.get("roster_class"),
            }
        classification[source_name] = value
        counts[str(value["roster_class"])] += 1
    if set(override_by_name) - set(classification):
        raise EnrichmentError("roster override references an unknown Pal")
    for name in (
        "canonical_paldeck",
        "terraria_collaboration_entity",
        "internal_duplicate_form",
    ):
        if counts[name] != EXPECTED_COUNTS[name]:
            raise EnrichmentError(f"roster count is invalid: {name}")
    return roster_bytes, classification


def _load_palcalc(
    db_path: Path,
    csv_path: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    db_bytes = _verify_locked_file(
        db_path,
        sha256=PALCALC_DB_SHA256,
        git_blob_sha1=PALCALC_DB_GIT_BLOB_SHA1,
        label="PalCalc db.json",
    )
    csv_bytes = _verify_locked_file(
        csv_path,
        sha256=PALCALC_CSV_SHA256,
        git_blob_sha1=PALCALC_CSV_GIT_BLOB_SHA1,
        label="PalCalc pals.csv",
    )
    try:
        db = json.loads(db_bytes)
    except json.JSONDecodeError as error:
        raise EnrichmentError("PalCalc db.json is malformed") from error
    raw_pals = db.get("Pals") if isinstance(db, dict) else None
    if not isinstance(raw_pals, list) or len(raw_pals) != EXPECTED_COUNTS["pal_records"]:
        raise EnrichmentError("PalCalc db.json does not contain 299 Pals")
    db_by_name: dict[str, dict[str, Any]] = {}
    for pal in raw_pals:
        if not isinstance(pal, dict) or not isinstance(pal.get("InternalName"), str):
            raise EnrichmentError("PalCalc Pal record is malformed")
        name = pal["InternalName"]
        if name in db_by_name:
            raise EnrichmentError("PalCalc Pal internal name is duplicated")
        db_by_name[name] = pal

    try:
        csv_text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise EnrichmentError("PalCalc pals.csv is not UTF-8") from error
    probability_by_name: dict[str, int] = {}
    for row in csv.DictReader(csv_text.splitlines()):
        name = row.get("CodeName")
        try:
            probability = int(row.get("MaleProbability", ""))
        except ValueError as error:
            raise EnrichmentError("PalCalc male probability is invalid") from error
        if not isinstance(name, str) or name in probability_by_name:
            raise EnrichmentError("PalCalc CSV Pal identity is invalid")
        if probability < 0 or probability > 100:
            raise EnrichmentError("PalCalc male probability is outside [0, 100]")
        probability_by_name[name] = probability
    if set(probability_by_name) != set(db_by_name):
        raise EnrichmentError("PalCalc CSV and database Pal identities differ")
    return db_by_name, probability_by_name


def _source_row_output(
    row: dict[str, Any],
    *,
    joined_pal_internal_id: str | None,
    exclusion_reason: str | None,
) -> dict[str, Any]:
    return {
        "source_row_id": row["sourceRowId"],
        "source_row_sha256": row["sourceRowSha256"],
        "source_fields": row["sourceFields"],
        "selected_values": row["values"],
        "join_status": "joined" if joined_pal_internal_id is not None else "excluded",
        "joined_pal_internal_id": joined_pal_internal_id,
        "exclusion_reason": exclusion_reason,
    }


def _normalize_native(
    pals: list[dict[str, Any]],
    pal_rows: list[dict[str, Any]],
    skill_rows: list[dict[str, Any]],
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    pal_by_source = {pal["source_internal_name"]: pal for pal in pals}
    if len(pal_by_source) != EXPECTED_COUNTS["pal_records"]:
        raise EnrichmentError("dataset Pal source identities are duplicated")
    native_pal_by_source = {row["sourceRowId"]: row for row in pal_rows}
    if set(pal_by_source) - set(native_pal_by_source):
        raise EnrichmentError("a dataset Pal has no exact native source-row match")

    pal_source_rows: list[dict[str, Any]] = []
    normalized_by_source: dict[str, dict[str, Any]] = {}
    for row in pal_rows:
        source_name = row["sourceRowId"]
        pal = pal_by_source.get(source_name)
        pal_source_rows.append(
            _source_row_output(
                row,
                joined_pal_internal_id=pal["internal_id"] if pal is not None else None,
                exclusion_reason=(
                    None if pal is not None else "source_row_not_in_locked_299_calculation_roster"
                ),
            )
        )
        if pal is None:
            continue
        values = row["values"]
        raw_elements = [
            _strip_enum(values["elementType1"], "native primary element"),
            _strip_enum(values["elementType2"], "native secondary element"),
        ]
        elements = [element for element in raw_elements if element != "None"]
        if not 1 <= len(elements) <= 2 or len(elements) != len(set(elements)):
            raise EnrichmentError("native Pal element assignment is invalid")
        male_percent = values["maleProbability"]
        if not isinstance(male_percent, int) or isinstance(male_percent, bool):
            raise EnrichmentError("joined native Pal male probability is missing")
        if male_percent < 0 or male_percent > 100:
            raise EnrichmentError("joined native Pal male probability is invalid")
        passives = sorted(
            {
                _strip_enum(values[f"passiveSkill{index}"], "native passive skill")
                for index in range(1, 5)
            }
            - {"None"}
        )
        normalized_by_source[source_name] = {
            "elements": elements,
            "male_percent": male_percent,
            "guaranteed_passive_skill_ids": passives,
            "source_row_id": source_name,
            "source_row_sha256": row["sourceRowSha256"],
        }

    learnsets_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    active_skill_source_rows: list[dict[str, Any]] = []
    joined_skill_keys: set[tuple[str, str, int]] = set()
    for row in skill_rows:
        values = row["values"]
        pal_source_name = _strip_enum(values["palId"], "native active-skill Pal ID")
        skill_id = _strip_enum(values["wazaId"], "native active-skill ID")
        level = values["level"]
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 100:
            raise EnrichmentError("native active-skill learned level is invalid")
        pal = pal_by_source.get(pal_source_name)
        active_skill_source_rows.append(
            _source_row_output(
                row,
                joined_pal_internal_id=pal["internal_id"] if pal is not None else None,
                exclusion_reason=(
                    None if pal is not None else "pal_id_not_in_locked_299_calculation_roster"
                ),
            )
        )
        if pal is None:
            continue
        key = (pal["internal_id"], skill_id, level)
        if key in joined_skill_keys:
            raise EnrichmentError("joined active-skill learnset entry is duplicated")
        joined_skill_keys.add(key)
        learnsets_by_source[pal_source_name].append(
            {
                "pal_internal_id": pal["internal_id"],
                "skill_id": skill_id,
                "level": level,
            }
        )
    for learnset in learnsets_by_source.values():
        learnset.sort(key=lambda entry: (entry["level"], entry["skill_id"]))

    native_output = {
        "schema_version": 1,
        "contract": "palnavi-native-enrichment-provenance/v1",
        "source_snapshot": {
            "sha256": NATIVE_SNAPSHOT_SHA256,
            "steam_build_id": acquisition.BUILD_ID,
            "pak_bytes": acquisition.PAK_SIZE,
            "mappings": "not_provided_not_required",
            "tables": [
                {
                    "name": "pals",
                    "package_path": PAL_TABLE_PATH,
                    "raw_row_count": len(pal_rows),
                    "selected_fields": PAL_FIELDS,
                    "selected_fields_sha256": PAL_TABLE_HASH,
                },
                {
                    "name": "active-skill-learnset",
                    "package_path": ACTIVE_SKILL_TABLE_PATH,
                    "raw_row_count": len(skill_rows),
                    "selected_fields": ACTIVE_SKILL_FIELDS,
                    "selected_fields_sha256": ACTIVE_SKILL_TABLE_HASH,
                },
            ],
        },
        "aliases": {},
        "pal_source_rows": pal_source_rows,
        "active_skill_source_rows": active_skill_source_rows,
    }
    joined_pal_count = sum(row["join_status"] == "joined" for row in pal_source_rows)
    joined_skill_count = sum(row["join_status"] == "joined" for row in active_skill_source_rows)
    if (
        joined_pal_count != EXPECTED_COUNTS["native_pal_rows_joined"]
        or len(pal_source_rows) - joined_pal_count != EXPECTED_COUNTS["native_pal_rows_excluded"]
        or joined_skill_count != EXPECTED_COUNTS["native_active_skill_rows_joined"]
        or len(active_skill_source_rows) - joined_skill_count
        != EXPECTED_COUNTS["native_active_skill_rows_excluded"]
    ):
        raise EnrichmentError("native source row accounting is invalid")
    return native_output, normalized_by_source, learnsets_by_source


def _build_enrichment(
    pals: list[dict[str, Any]],
    classification: dict[str, dict[str, Any]],
    normalized_by_source: dict[str, dict[str, Any]],
    learnsets_by_source: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    for pal in sorted(pals, key=lambda value: value["internal_id"]):
        source_name = pal["source_internal_name"]
        native = normalized_by_source[source_name]
        roster = classification[source_name]
        male_percent = native["male_percent"]
        fields = {
            "canonical_paldeck_member": roster["canonical_paldeck_member"],
            "roster_class": roster["roster_class"],
            "elements": native["elements"],
            "male_probability": male_percent / 100,
            "female_probability": (100 - male_percent) / 100,
            "active_skill_learnset": learnsets_by_source.get(source_name, []),
            "guaranteed_passive_skill_ids": native["guaranteed_passive_skill_ids"],
        }
        if set(fields) != ENRICHMENT_FIELDS:
            raise EnrichmentError("enrichment field allowlist is invalid")
        records[pal["internal_id"]] = fields
    if len(records) != EXPECTED_COUNTS["pal_records"]:
        raise EnrichmentError("enrichment does not contain 299 records")
    return {
        "schema_version": 1,
        "enrichment_id": ENRICHMENT_ID,
        "source_dataset_id": DATASET_ID,
        "runtime_status": "stored_not_activated",
        "records_by_pal_internal_id": records,
    }


def _build_diff(
    pals: list[dict[str, Any]],
    palcalc_by_source: dict[str, dict[str, Any]],
    probability_by_source: dict[str, int],
    normalized_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    for pal in sorted(pals, key=lambda value: value["internal_id"]):
        source_name = pal["source_internal_name"]
        palcalc = palcalc_by_source[source_name]
        native = normalized_by_source[source_name]
        palcalc_passives = sorted(palcalc.get("GuaranteedPassivesInternalIds") or [])
        comparisons = {
            "male_probability_percent": {
                "palcalc": probability_by_source[source_name],
                "native": native["male_percent"],
                "status": (
                    "match"
                    if probability_by_source[source_name] == native["male_percent"]
                    else "difference"
                ),
            },
            "guaranteed_passive_skill_ids": {
                "palcalc": palcalc_passives,
                "native": native["guaranteed_passive_skill_ids"],
                "status": (
                    "match"
                    if palcalc_passives == native["guaranteed_passive_skill_ids"]
                    else "difference"
                ),
            },
        }
        statuses.update(comparison["status"] for comparison in comparisons.values())
        records.append(
            {
                "pal_internal_id": pal["internal_id"],
                "source_internal_name": source_name,
                "native_source_row_sha256": native["source_row_sha256"],
                "comparisons": comparisons,
            }
        )
    return {
        "schema_version": 1,
        "contract": "palnavi-palcalc-native-diff/v1",
        "compared_records": len(records),
        "compared_fields_per_record": [
            "male_probability_percent",
            "guaranteed_passive_skill_ids",
        ],
        "summary": {
            "comparisons": sum(statuses.values()),
            "matches": statuses["match"],
            "differences": statuses["difference"],
        },
        "records": records,
    }


def _file_record(name: str, value: bytes, records: int | None) -> dict[str, Any]:
    return {
        "path": name,
        "bytes": len(value),
        "sha256": _sha256_bytes(value),
        "records": records,
    }


def _build_manifest(outputs: dict[str, bytes], counts: dict[str, int]) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "enrichment_id": ENRICHMENT_ID,
        "source_dataset_id": DATASET_ID,
        "created_at": CREATED_AT,
        "classification": "production_source_data_stored_inactive",
        "runtime_status": "stored_not_activated",
        "native_acquisition": {
            "lock_path": "../native-acquisition-lock.json",
            "lock_sha256": ACQUISITION_LOCK_SHA256,
            "steam_app_id": acquisition.APP_ID,
            "steam_build_id": acquisition.BUILD_ID,
            "depot_id": acquisition.DEPOT_ID,
            "manifest_id": acquisition.MANIFEST_ID,
            "pak_path": acquisition.PAK_PATH,
            "pak_bytes": acquisition.PAK_SIZE,
            "pak_steam_sha1": acquisition.PAK_STEAM_SHA1,
            "pak_sha256": acquisition.PAK_SHA256,
            "mappings": "not_provided_not_required",
        },
        "extractor": {
            "repository": ATLAS_REPOSITORY,
            "commit": ATLAS_COMMIT,
            "project": ATLAS_PROJECT,
            "project_sha256": ATLAS_PROJECT_SHA256,
            "dependency_lock_record_sha256": acquisition.DEPENDENCY_LOCK_RECORD_SHA256,
            "patch_path": "tools/palworld_atlas_enrichment.patch",
            "patch_sha256": ATLAS_PATCH_SHA256,
            "raw_snapshot_sha256": NATIVE_SNAPSHOT_SHA256,
        },
        "palcalc": {
            "repository": PALCALC_REPOSITORY,
            "commit": PALCALC_COMMIT,
            "db_path": "PalCalc.Model/db.json",
            "db_sha256": PALCALC_DB_SHA256,
            "db_git_blob_sha1": PALCALC_DB_GIT_BLOB_SHA1,
            "csv_path": "PalCalc.GenDB/out-csv/pals.csv",
            "csv_sha256": PALCALC_CSV_SHA256,
            "csv_git_blob_sha1": PALCALC_CSV_GIT_BLOB_SHA1,
        },
        "roster_classification": {
            "control_source_path": (
                "research/palworld/2026-07-24/gap-closure/roster-classification.json"
            ),
            "sha256": ROSTER_CLASSIFICATION_SHA256,
        },
        "counts": counts,
        "generated_files": [
            _file_record("ATLAS-LICENSE.txt", outputs["ATLAS-LICENSE.txt"], None),
            _file_record(
                "native-pal-fields.json",
                outputs["native-pal-fields.json"],
                counts["native_pal_rows"] + counts["native_active_skill_rows"],
            ),
            _file_record(
                "pal-enrichment.json",
                outputs["pal-enrichment.json"],
                counts["pal_records"],
            ),
            _file_record(
                "palcalc-native-diff.json",
                outputs["palcalc-native-diff.json"],
                counts["pal_records"],
            ),
            _file_record(
                "roster-classification.json",
                outputs["roster-classification.json"],
                counts["pal_records"],
            ),
        ],
        "claim_limits": [
            (
                "This enrichment is derived from the Linux dedicated-server tables, "
                "not PC client assets."
            ),
            "Guaranteed passive IDs are direct fixed assignments, not an inheritance pool.",
            (
                "No partner skill, ranch output, mutation, cake, IV, or probability-cost "
                "value is inferred."
            ),
            "Runtime, API, planner, and frontend behavior remain unchanged.",
        ],
        "generation": {
            "tool": "tools/build_palworld_enrichment.py",
            "serialization": "UTF-8 JSON, two-space indentation, LF terminator",
            "deterministic": True,
            "aliases": {},
        },
    }
    manifest["content_identity"] = {
        "algorithm": "sha256",
        "digest": _record_hash(manifest),
    }
    return manifest


def build(args: argparse.Namespace) -> None:
    dataset = args.dataset
    acquisition_lock = dataset / "native-acquisition-lock.json"
    if _sha256_file(acquisition_lock) != ACQUISITION_LOCK_SHA256:
        raise EnrichmentError("native acquisition lock byte identity is invalid")
    acquisition.load_and_validate(acquisition_lock)

    if _sha256_file(args.pak) != acquisition.PAK_SHA256:
        raise EnrichmentError("native PAK SHA-256 does not match the acquisition lock")
    try:
        pak_size = args.pak.stat().st_size
    except OSError as error:
        raise EnrichmentError("native PAK is unreadable") from error
    if pak_size != acquisition.PAK_SIZE:
        raise EnrichmentError("native PAK byte count does not match the acquisition lock")

    _verify_git_source(args.atlas_repo, ATLAS_COMMIT, "Atlas")
    project_value = _verify_locked_file(
        args.atlas_repo / ATLAS_PROJECT,
        sha256=ATLAS_PROJECT_SHA256,
        git_blob_sha1=None,
        label="Atlas project",
    )
    if not project_value:
        raise EnrichmentError("Atlas project is empty")
    atlas_license = _verify_locked_file(
        args.atlas_license,
        sha256=ATLAS_LICENSE_SOURCE_SHA256,
        git_blob_sha1=ATLAS_LICENSE_SOURCE_GIT_BLOB_SHA1,
        label="Atlas license",
    )
    normalized_atlas_license = atlas_license.rstrip(b"\r\n") + b"\n"
    if _sha256_bytes(normalized_atlas_license) != ATLAS_LICENSE_OUTPUT_SHA256:
        raise EnrichmentError("normalized Atlas license identity is invalid")
    repository_root = Path(__file__).resolve().parents[1]
    patch_path = repository_root / "tools" / "palworld_atlas_enrichment.patch"
    if _sha256_file(patch_path) != ATLAS_PATCH_SHA256:
        raise EnrichmentError("Atlas enrichment patch identity is invalid")
    _run(
        [
            "git",
            "-C",
            str(args.atlas_repo),
            "apply",
            "--check",
            str(patch_path),
        ],
        "Atlas enrichment patch applicability check",
    )

    _verify_git_source(args.palcalc_repo, PALCALC_COMMIT, "PalCalc")
    palcalc_by_source, probability_by_source = _load_palcalc(
        args.palcalc_db,
        args.palcalc_csv,
    )
    snapshot, pal_rows, skill_rows = _load_native_snapshot(args.native_snapshot)
    del snapshot
    pals_document = _read_json(dataset / "pals.json", "dataset pals.json")
    pals = pals_document.get("records")
    if not isinstance(pals, list) or len(pals) != EXPECTED_COUNTS["pal_records"]:
        raise EnrichmentError("dataset pals.json does not contain 299 records")
    roster_bytes, classification = _load_roster(args.roster_classification, pals)
    native_output, normalized_by_source, learnsets_by_source = _normalize_native(
        pals,
        pal_rows,
        skill_rows,
    )
    if set(normalized_by_source) != set(palcalc_by_source):
        raise EnrichmentError("native and PalCalc Pal identities are not bijective")
    enrichment = _build_enrichment(
        pals,
        classification,
        normalized_by_source,
        learnsets_by_source,
    )
    diff = _build_diff(
        pals,
        palcalc_by_source,
        probability_by_source,
        normalized_by_source,
    )

    counts = {
        **EXPECTED_COUNTS,
        "active_skill_entries": sum(
            len(record["active_skill_learnset"])
            for record in enrichment["records_by_pal_internal_id"].values()
        ),
        "palcalc_native_comparisons": diff["summary"]["comparisons"],
        "palcalc_native_differences": diff["summary"]["differences"],
    }
    if counts["active_skill_entries"] != EXPECTED_COUNTS["native_active_skill_rows_joined"]:
        raise EnrichmentError("active-skill entry count does not match joined source rows")
    if counts["palcalc_native_comparisons"] != 598:
        raise EnrichmentError("PalCalc/native comparison count is invalid")

    outputs = {
        "ATLAS-LICENSE.txt": normalized_atlas_license,
        "native-pal-fields.json": _pretty_bytes(native_output),
        "pal-enrichment.json": _pretty_bytes(enrichment),
        "palcalc-native-diff.json": _pretty_bytes(diff),
        "roster-classification.json": roster_bytes,
    }
    manifest = _build_manifest(outputs, counts)
    enrichment_directory = dataset / "enrichment"
    for name, value in outputs.items():
        _write_atomic(enrichment_directory / name, value)
    _write_atomic(enrichment_directory / "manifest.json", _pretty_bytes(manifest))
    validate(dataset)


def _validate_manifest(dataset: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    enrichment_directory = dataset / "enrichment"
    manifest = _read_json(enrichment_directory / "manifest.json", "enrichment manifest")
    if (
        manifest.get("enrichment_id") != ENRICHMENT_ID
        or manifest.get("source_dataset_id") != DATASET_ID
        or manifest.get("runtime_status") != "stored_not_activated"
    ):
        raise EnrichmentError("enrichment manifest identity or runtime status is invalid")
    identity = manifest.get("content_identity")
    without_identity = dict(manifest)
    without_identity.pop("content_identity", None)
    if (
        not isinstance(identity, dict)
        or identity.get("algorithm") != "sha256"
        or identity.get("digest") != _record_hash(without_identity)
    ):
        raise EnrichmentError("enrichment manifest content identity is invalid")
    if manifest.get("counts") != {
        **EXPECTED_COUNTS,
        "active_skill_entries": 2_356,
        "palcalc_native_comparisons": 598,
        "palcalc_native_differences": 0,
    }:
        raise EnrichmentError("enrichment manifest counts are invalid")
    native_acquisition = manifest.get("native_acquisition")
    extractor = manifest.get("extractor")
    if (
        not isinstance(native_acquisition, dict)
        or native_acquisition.get("lock_sha256") != ACQUISITION_LOCK_SHA256
        or native_acquisition.get("steam_build_id") != acquisition.BUILD_ID
        or native_acquisition.get("manifest_id") != acquisition.MANIFEST_ID
        or native_acquisition.get("pak_sha256") != acquisition.PAK_SHA256
        or native_acquisition.get("mappings") != "not_provided_not_required"
        or not isinstance(extractor, dict)
        or extractor.get("commit") != ATLAS_COMMIT
        or extractor.get("project_sha256") != ATLAS_PROJECT_SHA256
        or extractor.get("patch_sha256") != ATLAS_PATCH_SHA256
        or extractor.get("raw_snapshot_sha256") != NATIVE_SNAPSHOT_SHA256
    ):
        raise EnrichmentError("enrichment manifest source identity is invalid")

    generated = manifest.get("generated_files")
    if not isinstance(generated, list) or [
        record.get("path") if isinstance(record, dict) else None for record in generated
    ] != list(OUTPUT_NAMES):
        raise EnrichmentError("enrichment manifest file inventory is invalid")
    outputs: dict[str, bytes] = {}
    for record in generated:
        if not isinstance(record, dict):
            raise EnrichmentError("enrichment manifest file record is malformed")
        name = record["path"]
        value = _read_bytes(enrichment_directory / name, f"enrichment output {name}")
        if len(value) != record.get("bytes") or _sha256_bytes(value) != record.get("sha256"):
            raise EnrichmentError("enrichment output identity does not match the manifest")
        outputs[name] = value
    return manifest, outputs


def _validate_native_output(native: dict[str, Any]) -> None:
    if (
        native.get("contract") != "palnavi-native-enrichment-provenance/v1"
        or native.get("aliases") != {}
    ):
        raise EnrichmentError("native provenance contract is invalid")
    source_snapshot = native.get("source_snapshot")
    if not isinstance(source_snapshot, dict) or source_snapshot.get("sha256") != (
        NATIVE_SNAPSHOT_SHA256
    ):
        raise EnrichmentError("native provenance snapshot identity is invalid")
    tables = source_snapshot.get("tables")
    if not isinstance(tables, list) or len(tables) != 2:
        raise EnrichmentError("native provenance table inventory is invalid")
    if tables[0] != {
        "name": "pals",
        "package_path": PAL_TABLE_PATH,
        "raw_row_count": 753,
        "selected_fields": PAL_FIELDS,
        "selected_fields_sha256": PAL_TABLE_HASH,
    } or tables[1] != {
        "name": "active-skill-learnset",
        "package_path": ACTIVE_SKILL_TABLE_PATH,
        "raw_row_count": 5_772,
        "selected_fields": ACTIVE_SKILL_FIELDS,
        "selected_fields_sha256": ACTIVE_SKILL_TABLE_HASH,
    }:
        raise EnrichmentError("native provenance table identity is invalid")
    for name, expected_total, expected_joined in (
        ("pal_source_rows", 753, 299),
        ("active_skill_source_rows", 5_772, 2_356),
    ):
        rows = native.get(name)
        if not isinstance(rows, list) or len(rows) != expected_total:
            raise EnrichmentError("native provenance source-row count is invalid")
        source_ids: list[str] = []
        joined = 0
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "source_row_id",
                "source_row_sha256",
                "source_fields",
                "selected_values",
                "join_status",
                "joined_pal_internal_id",
                "exclusion_reason",
            }:
                raise EnrichmentError("native provenance source-row contract is invalid")
            source_ids.append(row["source_row_id"])
            if row["join_status"] == "joined":
                joined += 1
                if (
                    not isinstance(row["joined_pal_internal_id"], str)
                    or row["exclusion_reason"] is not None
                ):
                    raise EnrichmentError("joined native source-row accounting is invalid")
            elif (
                row["join_status"] != "excluded"
                or row["joined_pal_internal_id"] is not None
                or not isinstance(row["exclusion_reason"], str)
            ):
                raise EnrichmentError("excluded native source-row accounting is invalid")
        if source_ids != sorted(source_ids) or len(source_ids) != len(set(source_ids)):
            raise EnrichmentError("native provenance source-row order is invalid")
        if joined != expected_joined:
            raise EnrichmentError("native provenance joined-row count is invalid")


def _validate_enrichment(enrichment: dict[str, Any]) -> None:
    if (
        enrichment.get("enrichment_id") != ENRICHMENT_ID
        or enrichment.get("source_dataset_id") != DATASET_ID
        or enrichment.get("runtime_status") != "stored_not_activated"
    ):
        raise EnrichmentError("Pal enrichment identity or runtime status is invalid")
    records = enrichment.get("records_by_pal_internal_id")
    if not isinstance(records, dict) or len(records) != 299:
        raise EnrichmentError("Pal enrichment record count is invalid")
    if list(records) != sorted(records):
        raise EnrichmentError("Pal enrichment record order is invalid")
    roster_counts: Counter[str] = Counter()
    skill_keys: set[tuple[str, str, int]] = set()
    for pal_id, fields in records.items():
        if not isinstance(fields, dict) or set(fields) != ENRICHMENT_FIELDS:
            raise EnrichmentError("Pal enrichment field allowlist is invalid")
        roster_counts[str(fields["roster_class"])] += 1
        expected_member = fields["roster_class"] == "canonical_paldeck"
        if fields["canonical_paldeck_member"] is not expected_member:
            raise EnrichmentError("Pal enrichment roster membership is inconsistent")
        elements = fields["elements"]
        if (
            not isinstance(elements, list)
            or not 1 <= len(elements) <= 2
            or len(elements) != len(set(elements))
            or not all(isinstance(value, str) and value for value in elements)
        ):
            raise EnrichmentError("Pal enrichment element assignment is invalid")
        male = fields["male_probability"]
        female = fields["female_probability"]
        if (
            not isinstance(male, int | float)
            or isinstance(male, bool)
            or not isinstance(female, int | float)
            or isinstance(female, bool)
            or not 0 <= male <= 1
            or not 0 <= female <= 1
            or round(male + female, 10) != 1
        ):
            raise EnrichmentError("Pal enrichment gender probability is invalid")
        passives = fields["guaranteed_passive_skill_ids"]
        if (
            not isinstance(passives, list)
            or passives != sorted(set(passives))
            or not all(isinstance(value, str) and value for value in passives)
        ):
            raise EnrichmentError("Pal enrichment fixed passive list is invalid")
        learnset = fields["active_skill_learnset"]
        if not isinstance(learnset, list):
            raise EnrichmentError("Pal enrichment active-skill learnset is invalid")
        expected_order = sorted(
            learnset,
            key=lambda entry: (entry.get("level"), entry.get("skill_id")),
        )
        if learnset != expected_order:
            raise EnrichmentError("Pal enrichment active-skill order is invalid")
        for entry in learnset:
            if not isinstance(entry, dict) or set(entry) != {
                "pal_internal_id",
                "skill_id",
                "level",
            }:
                raise EnrichmentError("Pal enrichment active-skill entry is malformed")
            if (
                entry["pal_internal_id"] != pal_id
                or not isinstance(entry["skill_id"], str)
                or not isinstance(entry["level"], int)
            ):
                raise EnrichmentError("Pal enrichment active-skill identity is invalid")
            key = (pal_id, entry["skill_id"], entry["level"])
            if key in skill_keys:
                raise EnrichmentError("Pal enrichment active-skill entry is duplicated")
            skill_keys.add(key)
    for name in (
        "canonical_paldeck",
        "terraria_collaboration_entity",
        "internal_duplicate_form",
    ):
        if roster_counts[name] != EXPECTED_COUNTS[name]:
            raise EnrichmentError(f"Pal enrichment roster count is invalid: {name}")
    if len(skill_keys) != EXPECTED_COUNTS["native_active_skill_rows_joined"]:
        raise EnrichmentError("Pal enrichment active-skill count is invalid")


def _validate_diff(diff: dict[str, Any]) -> None:
    if (
        diff.get("contract") != "palnavi-palcalc-native-diff/v1"
        or diff.get("compared_records") != 299
        or diff.get("summary") != {"comparisons": 598, "matches": 598, "differences": 0}
    ):
        raise EnrichmentError("PalCalc/native diff summary is invalid")
    records = diff.get("records")
    if not isinstance(records, list) or len(records) != 299:
        raise EnrichmentError("PalCalc/native diff record count is invalid")
    pal_ids: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise EnrichmentError("PalCalc/native diff record is malformed")
        pal_ids.append(record.get("pal_internal_id"))
        comparisons = record.get("comparisons")
        if not isinstance(comparisons, dict) or set(comparisons) != {
            "male_probability_percent",
            "guaranteed_passive_skill_ids",
        }:
            raise EnrichmentError("PalCalc/native diff fields are invalid")
        for comparison in comparisons.values():
            if (
                not isinstance(comparison, dict)
                or comparison.get("status") != "match"
                or comparison.get("palcalc") != comparison.get("native")
            ):
                raise EnrichmentError("PalCalc/native comparison is not explicit or equal")
    if pal_ids != sorted(pal_ids) or len(pal_ids) != len(set(pal_ids)):
        raise EnrichmentError("PalCalc/native diff order or identity is invalid")


def validate(dataset: Path) -> None:
    acquisition_lock = dataset / "native-acquisition-lock.json"
    if _sha256_file(acquisition_lock) != ACQUISITION_LOCK_SHA256:
        raise EnrichmentError("native acquisition lock byte identity is invalid")
    acquisition.load_and_validate(acquisition_lock)
    repository_root = Path(__file__).resolve().parents[1]
    patch_path = repository_root / "tools" / "palworld_atlas_enrichment.patch"
    if _sha256_file(patch_path) != ATLAS_PATCH_SHA256:
        raise EnrichmentError("Atlas enrichment patch identity is invalid")

    manifest, outputs = _validate_manifest(dataset)
    del manifest
    try:
        native = json.loads(outputs["native-pal-fields.json"])
        enrichment = json.loads(outputs["pal-enrichment.json"])
        diff = json.loads(outputs["palcalc-native-diff.json"])
        roster = json.loads(outputs["roster-classification.json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EnrichmentError("enrichment output JSON is malformed") from error
    if _sha256_bytes(outputs["ATLAS-LICENSE.txt"]) != ATLAS_LICENSE_OUTPUT_SHA256:
        raise EnrichmentError("Atlas license identity is invalid")
    if _sha256_bytes(outputs["roster-classification.json"]) != (ROSTER_CLASSIFICATION_SHA256):
        raise EnrichmentError("roster classification identity is invalid")
    if not isinstance(roster, dict) or roster.get("expected_counts") != {
        "canonical_paldeck": 287,
        "terraria_collaboration_entity": 11,
        "internal_duplicate_form": 1,
        "total": 299,
    }:
        raise EnrichmentError("roster classification expected counts are invalid")
    if (
        not isinstance(native, dict)
        or not isinstance(enrichment, dict)
        or not isinstance(diff, dict)
    ):
        raise EnrichmentError("enrichment output root is malformed")
    _validate_native_output(native)
    _validate_enrichment(enrichment)
    _validate_diff(diff)

    serialized = b"".join(outputs.values()).decode("utf-8", errors="ignore").casefold()
    if any(fragment in serialized for fragment in PROHIBITED_FRAGMENTS):
        raise EnrichmentError("enrichment outputs contain a prohibited path or secret marker")
    runtime_root = repository_root / "backend" / "src"
    for path in runtime_root.rglob("*.py"):
        if "enrichment" in path.read_text(encoding="utf-8").casefold():
            raise EnrichmentError("runtime source unexpectedly references the inactive enrichment")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--native-snapshot", type=Path)
    parser.add_argument("--pak", type=Path)
    parser.add_argument("--atlas-repo", type=Path)
    parser.add_argument("--atlas-license", type=Path)
    parser.add_argument("--palcalc-repo", type=Path)
    parser.add_argument("--palcalc-db", type=Path)
    parser.add_argument("--palcalc-csv", type=Path)
    parser.add_argument("--roster-classification", type=Path)
    return parser


def _resolve_paths(arguments: argparse.Namespace) -> None:
    for name in (
        "dataset",
        "native_snapshot",
        "pak",
        "atlas_repo",
        "atlas_license",
        "palcalc_repo",
        "palcalc_db",
        "palcalc_csv",
        "roster_classification",
    ):
        value = getattr(arguments, name)
        if value is not None:
            setattr(arguments, name, value.resolve())


def main() -> int:
    arguments = _parser().parse_args()
    _resolve_paths(arguments)
    try:
        if arguments.validate_only:
            generation_values = (
                arguments.native_snapshot,
                arguments.pak,
                arguments.atlas_repo,
                arguments.atlas_license,
                arguments.palcalc_repo,
                arguments.palcalc_db,
                arguments.palcalc_csv,
                arguments.roster_classification,
            )
            if any(value is not None for value in generation_values):
                raise EnrichmentError("--validate-only does not accept generation inputs")
            validate(arguments.dataset)
        else:
            required = {
                "--native-snapshot": arguments.native_snapshot,
                "--pak": arguments.pak,
                "--atlas-repo": arguments.atlas_repo,
                "--atlas-license": arguments.atlas_license,
                "--palcalc-repo": arguments.palcalc_repo,
                "--palcalc-db": arguments.palcalc_db,
                "--palcalc-csv": arguments.palcalc_csv,
                "--roster-classification": arguments.roster_classification,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise EnrichmentError(
                    "generation requires explicit local inputs: " + ", ".join(missing)
                )
            build(arguments)
    except (EnrichmentError, acquisition.AcquisitionError) as error:
        print(f"enrichment validation failed: {error}", file=sys.stderr)
        return 1
    print(f"enrichment valid: {ENRICHMENT_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
