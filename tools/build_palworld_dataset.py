#!/usr/bin/env python3
"""Build and validate the pinned Palworld v1 breeding dataset without network access."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DATASET_ID = "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47"
IMPORTER_VERSION = "palnavi-palworld-normalizer/1"
CREATED_AT = "2026-07-24T05:19:31Z"
PALCALC_COMMIT = "8b7e2f779e47fddae16ddcb973e828ba20c02b80"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
OUTCOME_CHUNK_SIZE = 1_500

INPUT_LOCKS = {
    "palcalc_db": {
        "path": "PalCalc.Model/db.json",
        "bytes": 1_588_212,
        "sha256": "803d891afdb18bd00e24332844a7276bbe5c0855170ef90ef142f2f4d7698ed1",
        "git_blob_sha1": "82ef55ab1f26a8c4fd032eb29a9aab0ddb1532eb",
    },
    "palcalc_breeding": {
        "path": "PalCalc.Model/breeding.json",
        "bytes": 8_941_970,
        "sha256": "1af1e4d6b461599ec3b80a2195002337ff484ed3c28ce57e27def96138262ec2",
        "git_blob_sha1": "768ee32bb1e56339dfbd5157955d0c80df1673dd",
    },
    "palcalc_algorithm": {
        "path": "PalCalc.GenDB/PalBreedingCalculator.cs",
        "bytes": 2_260,
        "sha256": "30f1cd4e787ca2c713075e4269ddf1b451a120eaaf347474eabb216f436fcab1",
        "git_blob_sha1": "bc5f3599df11c2856333202e39c884b6500d3b95",
    },
    "palcalc_license": {
        "path": "LICENSE.txt",
        "bytes": 1_058,
        "sha256": "60768557719376acb654991ff138d1b6ce5e9bf872582566b3f82b22e51ad5a4",
        "git_blob_sha1": "ad11cbfdbfcb4d58f80169a922addd125d81b415",
    },
    "palweave_json": {
        "path": "palworld-breeding-data.json",
        "bytes": 8_049_960,
        "sha256": "9f558802ed3fa14b52c352d18a05cd40b295e636ccca249376293e80dc1643c4",
        "git_blob_sha1": None,
    },
    "palweave_csv": {
        "path": "palworld-breeding-data.csv",
        "bytes": 2_128_682,
        "sha256": "db4e0e2b755ed3c01ef61744dfcc66c1af320ad444b4c0f47af687a3cf8f0b74",
        "git_blob_sha1": None,
    },
}

EXPECTED_COUNTS = {
    "pal_records": 299,
    "source_derived_outcomes": 44_851,
    "source_ordinary_outcomes": 44_603,
    "source_special_outcomes": 248,
    "same_species": 299,
    "ordinary_power": 44_418,
    "fixed_special": 132,
    "gender_directed": 2,
    "gender_dependent_parent_pair_families": 1,
}

WORK_KEY_MAP = {
    "Kindling": "kindling",
    "Watering": "watering",
    "Planting": "planting",
    "GenerateElectricity": "generate_electricity",
    "Handiwork": "handiwork",
    "Gathering": "gathering",
    "Lumbering": "lumbering",
    "Mining": "mining",
    "MedicineProduction": "medicine_production",
    "Cooling": "cooling",
    "Transporting": "transporting",
    "Farming": "farming",
}


class DatasetError(ValueError):
    """A sanitized deterministic dataset failure."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_hash(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _git_blob_sha1(value: bytes) -> str:
    header = f"blob {len(value)}\0".encode()
    return hashlib.sha1(header + value, usedforsecurity=False).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"
    ).encode("utf-8")


def _pretty_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


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


def _read_locked(path: Path, lock_name: str) -> bytes:
    lock = INPUT_LOCKS[lock_name]
    try:
        value = path.read_bytes()
    except OSError as error:
        raise DatasetError(f"{lock_name}: locked input is unreadable") from error
    if len(value) != lock["bytes"]:
        raise DatasetError(f"{lock_name}: byte count does not match the source lock")
    if _sha256_bytes(value) != lock["sha256"]:
        raise DatasetError(f"{lock_name}: SHA-256 does not match the source lock")
    expected_blob = lock["git_blob_sha1"]
    if expected_blob is not None and _git_blob_sha1(value) != expected_blob:
        raise DatasetError(f"{lock_name}: Git blob identity does not match the source lock")
    return value


def _parse_json(value: bytes, source_name: str) -> Any:
    try:
        return json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetError(f"{source_name}: locked JSON is malformed") from error


def _source_slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def _palweave_to_palnavi_id(source_id: str) -> str:
    value = source_id.replace("-", "_")
    if ID_PATTERN.fullmatch(value) is None:
        raise DatasetError("source ID cannot be represented by the PalNavi identifier contract")
    return value


def _palcalc_source_id(pal: dict[str, Any]) -> str:
    if pal.get("InternalName") == "PlantSlime_Flower":
        return "gumoss-flower"
    names = pal.get("LocalizedNames")
    if not isinstance(names, dict) or not isinstance(names.get("en"), str):
        raise DatasetError("PalCalc record is missing an English localized name")
    return _source_slug(names["en"])


def _normalize_gender(value: object) -> str | None:
    if value in (None, "", "WILDCARD"):
        return None
    normalized = str(value).lower()
    if normalized not in {"female", "male"}:
        raise DatasetError("breeding record contains an unsupported gender constraint")
    return normalized


def _normalized_outcome_key(
    parent_a: str,
    parent_a_gender: str | None,
    parent_b: str,
    parent_b_gender: str | None,
    child: str,
) -> tuple[str, str, str, str, str]:
    left = (parent_a, parent_a_gender or "")
    right = (parent_b, parent_b_gender or "")
    if right < left:
        left, right = right, left
    return (left[0], left[1], right[0], right[1], child)


def _cross_check_palcalc_breeding(
    source: dict[str, Any],
    source_id_by_internal_name: dict[str, str],
    audited_records: list[dict[str, Any]],
) -> None:
    raw_records = source.get("Breeding")
    if not isinstance(raw_records, list) or len(raw_records) != 44_851:
        raise DatasetError("PalCalc breeding export does not contain 44,851 records")

    palcalc_rows: Counter[tuple[str, str, str, str, str]] = Counter()
    for row in raw_records:
        try:
            key = _normalized_outcome_key(
                source_id_by_internal_name[row["Parent1InternalName"]],
                _normalize_gender(row["Parent1Gender"]),
                source_id_by_internal_name[row["Parent2InternalName"]],
                _normalize_gender(row["Parent2Gender"]),
                source_id_by_internal_name[row["ChildInternalName"]],
            )
        except (KeyError, TypeError) as error:
            raise DatasetError(
                "PalCalc breeding export contains an unknown Pal reference"
            ) from error
        palcalc_rows[key] += 1

    audited_rows: Counter[tuple[str, str, str, str, str]] = Counter()
    for row in audited_records:
        try:
            key = _normalized_outcome_key(
                str(row["parent_a"]),
                _normalize_gender(row.get("parent_a_gender")),
                str(row["parent_b"]),
                _normalize_gender(row.get("parent_b_gender")),
                str(row["child"]),
            )
        except (KeyError, TypeError) as error:
            raise DatasetError("audited breeding export contains an invalid record") from error
        audited_rows[key] += 1
    if palcalc_rows != audited_rows:
        raise DatasetError("PalCalc and audited breeding exports do not contain the same outcomes")


def _cross_check_csv(value: bytes, audited_records: list[dict[str, Any]]) -> None:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DatasetError("Palweave CSV is not valid UTF-8") from error
    csv_rows: Counter[tuple[str, str, str, str, str, str]] = Counter()
    for row in csv.DictReader(text.splitlines()):
        key = _normalized_outcome_key(
            row["parent_a"],
            _normalize_gender(row["parent_a_gender"]),
            row["parent_b"],
            _normalize_gender(row["parent_b_gender"]),
            row["child"],
        )
        csv_rows[(*key, row["special_combination"].lower())] += 1

    json_rows: Counter[tuple[str, str, str, str, str, str]] = Counter()
    for row in audited_records:
        key = _normalized_outcome_key(
            str(row["parent_a"]),
            _normalize_gender(row.get("parent_a_gender")),
            str(row["parent_b"]),
            _normalize_gender(row.get("parent_b_gender")),
            str(row["child"]),
        )
        json_rows[(*key, str(bool(row["special_combination"])).lower())] += 1
    if csv_rows != json_rows:
        raise DatasetError("audited JSON and CSV exports do not contain the same outcomes")


def _normalize_pals(
    db: dict[str, Any],
    audited_source_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    raw_pals = db.get("Pals")
    if not isinstance(raw_pals, list) or len(raw_pals) != 299:
        raise DatasetError("PalCalc database does not contain 299 calculation records")

    source_id_by_internal_name: dict[str, str] = {}
    pals: list[dict[str, Any]] = []
    for raw in raw_pals:
        if not isinstance(raw, dict):
            raise DatasetError("PalCalc Pal record is not an object")
        source_id = _palcalc_source_id(raw)
        internal_name = raw.get("InternalName")
        if not isinstance(internal_name, str) or internal_name in source_id_by_internal_name:
            raise DatasetError("PalCalc internal Pal identity is invalid or duplicated")
        source_id_by_internal_name[internal_name] = source_id

        localized_names = raw.get("LocalizedNames")
        work = raw.get("WorkSuitability")
        paldex = raw.get("Id")
        if not isinstance(localized_names, dict) or len(localized_names) != 17:
            raise DatasetError("PalCalc Pal localizations are incomplete")
        if not isinstance(work, dict) or set(work) != set(WORK_KEY_MAP):
            raise DatasetError("PalCalc work-suitability contract changed")
        if not isinstance(paldex, dict):
            raise DatasetError("PalCalc Paldeck identity is missing")

        normalized = {
            "schema_version": 1,
            "source_dataset_id": DATASET_ID,
            "source_record_hash": _record_hash(raw),
            "internal_id": _palweave_to_palnavi_id(source_id),
            "source_internal_name": internal_name,
            "paldex_number": paldex.get("PalDexNo"),
            "paldex_suffix": None,
            "is_variant": paldex.get("IsVariant"),
            "player_visible": None,
            "calculation_eligible": True,
            "localized_names": dict(sorted(localized_names.items())),
            "breeding_power": raw.get("BreedingPower"),
            "breeding_power_priority": raw.get("BreedingPowerPriority"),
            "elements": None,
            "base_stats": {
                "hp": raw.get("Hp"),
                "attack": raw.get("Attack"),
                "defense": raw.get("Defense"),
            },
            "movement_stats": {
                "walk_speed": raw.get("WalkSpeed"),
                "run_speed": raw.get("RunSpeed"),
                "ride_sprint_speed": raw.get("RideSprintSpeed"),
                "transport_speed": raw.get("TransportSpeed"),
                "stamina": raw.get("Stamina"),
            },
            "work_suitability": {target: work[source] for source, target in WORK_KEY_MAP.items()},
            "ranch_outputs": None,
            "partner_skill_id": None,
            "guaranteed_passive_skill_ids": sorted(raw.get("GuaranteedPassivesInternalIds") or []),
            "active_skill_ids": None,
            "rarity": raw.get("Rarity"),
            "size": raw.get("Size"),
            "nocturnal": raw.get("Nocturnal"),
            "food_amount": raw.get("FoodAmount"),
            "max_full_stomach": raw.get("MaxFullStomach"),
        }
        pals.append(normalized)

    source_ids = {_palcalc_source_id(pal) for pal in raw_pals}
    if source_ids != audited_source_ids:
        raise DatasetError("PalCalc Pal records do not map bijectively to audited source IDs")
    normalized_ids = [record["internal_id"] for record in pals]
    if len(normalized_ids) != len(set(normalized_ids)):
        raise DatasetError("normalized Pal IDs are not unique")
    pals.sort(key=lambda record: record["internal_id"])
    return pals, source_id_by_internal_name


def _normalize_outcomes(
    records: list[dict[str, Any]],
    pal_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    outcomes: list[dict[str, Any]] = []
    source_ordinary = 0
    source_special = 0
    result_kind_counts: Counter[str] = Counter()
    qualified_keys: set[tuple[str, str, str, str]] = set()
    directed_families: set[tuple[str, str]] = set()

    for raw in records:
        parent_a_source = str(raw["parent_a"])
        parent_b_source = str(raw["parent_b"])
        parent_a_gender = _normalize_gender(raw.get("parent_a_gender"))
        parent_b_gender = _normalize_gender(raw.get("parent_b_gender"))
        parent_a = _palweave_to_palnavi_id(parent_a_source)
        parent_b = _palweave_to_palnavi_id(parent_b_source)
        child = _palweave_to_palnavi_id(str(raw["child"]))
        if {parent_a, parent_b, child} - pal_ids:
            raise DatasetError("breeding outcome references an unknown normalized Pal")

        is_special = raw.get("special_combination") is True
        source_classification = "special" if is_special else "ordinary"
        if is_special:
            source_special += 1
        else:
            source_ordinary += 1

        if parent_a_gender is not None or parent_b_gender is not None:
            result_kind = "gender_directed"
            directed_families.add(tuple(sorted((parent_a, parent_b))))
        elif parent_a == parent_b == child:
            result_kind = "same_species"
        elif is_special:
            result_kind = "fixed_special"
        else:
            result_kind = "ordinary_power"
        result_kind_counts[result_kind] += 1

        left = (parent_a, parent_a_gender or "")
        right = (parent_b, parent_b_gender or "")
        if right < left:
            parent_a, parent_b = parent_b, parent_a
            parent_a_gender, parent_b_gender = parent_b_gender, parent_a_gender
        key = (
            parent_a,
            parent_a_gender or "",
            parent_b,
            parent_b_gender or "",
        )
        if key in qualified_keys:
            raise DatasetError("fully qualified parent/gender key is duplicated")
        qualified_keys.add(key)

        outcomes.append(
            {
                "schema_version": 1,
                "source_dataset_id": DATASET_ID,
                "source_record_hash": _record_hash(raw),
                "parent_1_internal_id": parent_a,
                "parent_1_gender_constraint": parent_a_gender,
                "parent_2_internal_id": parent_b,
                "parent_2_gender_constraint": parent_b_gender,
                "child_internal_id": child,
                "result_kind": result_kind,
                "source_classification": source_classification,
            }
        )

    counts = {
        "source_ordinary_outcomes": source_ordinary,
        "source_special_outcomes": source_special,
        **dict(result_kind_counts),
        "gender_dependent_parent_pair_families": len(directed_families),
    }
    outcomes.sort(
        key=lambda record: (
            record["parent_1_internal_id"],
            record["parent_1_gender_constraint"] or "",
            record["parent_2_internal_id"],
            record["parent_2_gender_constraint"] or "",
            record["child_internal_id"],
        )
    )
    return outcomes, counts


def _source_manifest() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for source_id, lock in INPUT_LOCKS.items():
        result.append(
            {
                "source_id": source_id,
                "path": lock["path"],
                "bytes": lock["bytes"],
                "sha256": lock["sha256"],
                "git_blob_sha1": lock["git_blob_sha1"],
            }
        )
    return result


def _build_manifest(
    pals_bytes: bytes,
    outcome_chunks: list[tuple[str, bytes, int]],
    license_bytes: bytes,
    counts: dict[str, int],
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "dataset_id": DATASET_ID,
        "classification": "production",
        "created_at": CREATED_AT,
        "importer_version": IMPORTER_VERSION,
        "validation_status": "validated",
        "game_version_scope": {
            "source_snapshot": "v1.0.0",
            "independently_verified_compatible_patch": "v1.0.1",
            "compatibility_evidence": "secondary_community_audit",
            "compatibility_audited_at": "2026-07-17",
        },
        "provenance": {
            "palcalc_repository": "https://github.com/tylercamp/palcalc",
            "palcalc_commit": PALCALC_COMMIT,
            "palweave_methodology": "https://palweave.com/data-methodology",
            "license": "MIT",
            "attribution": "Copyright 2024, Tyler Camp",
        },
        "source_inputs": _source_manifest(),
        "counts": counts,
        "generated_files": [
            {
                "path": "pals.json",
                "bytes": len(pals_bytes),
                "sha256": _sha256_bytes(pals_bytes),
                "records": EXPECTED_COUNTS["pal_records"],
            },
            *[
                {
                    "path": path,
                    "bytes": len(value),
                    "sha256": _sha256_bytes(value),
                    "records": records,
                }
                for path, value, records in outcome_chunks
            ],
            {
                "path": "PALCALC-LICENSE.txt",
                "bytes": len(license_bytes),
                "sha256": _sha256_bytes(license_bytes),
                "records": None,
            },
        ],
        "insufficient_fields": [
            "player_visible",
            "elements",
            "ranch_outputs",
            "partner_skill_id",
            "active_skill_ids",
            "complete_passive_skill_ids",
            "inheritance_and_mutation_probabilities",
        ],
        "runtime_status": "stored_not_activated",
        "runtime_note": (
            "The current planner cannot represent the one gender-directed parent-pair "
            "family; runtime activation requires a separately reviewed schema change."
        ),
    }
    manifest["content_identity"] = {
        "algorithm": "sha256",
        "digest": _record_hash(manifest),
    }
    return manifest


def build(args: argparse.Namespace) -> None:
    locked = {
        "palcalc_db": _read_locked(args.palcalc_db, "palcalc_db"),
        "palcalc_breeding": _read_locked(args.palcalc_breeding, "palcalc_breeding"),
        "palcalc_algorithm": _read_locked(args.palcalc_algorithm, "palcalc_algorithm"),
        "palcalc_license": _read_locked(args.palcalc_license, "palcalc_license"),
        "palweave_json": _read_locked(args.palweave_json, "palweave_json"),
        "palweave_csv": _read_locked(args.palweave_csv, "palweave_csv"),
    }
    db = _parse_json(locked["palcalc_db"], "palcalc_db")
    breeding = _parse_json(locked["palcalc_breeding"], "palcalc_breeding")
    audited = _parse_json(locked["palweave_json"], "palweave_json")
    if not isinstance(db, dict) or not isinstance(breeding, dict) or not isinstance(audited, dict):
        raise DatasetError("locked JSON roots must be objects")
    audited_records = audited.get("records")
    if not isinstance(audited_records, list) or len(audited_records) != 44_851:
        raise DatasetError("audited export does not contain 44,851 records")
    source_ids = {
        str(value)
        for row in audited_records
        for value in (row.get("parent_a"), row.get("parent_b"), row.get("child"))
    }
    pals, source_id_by_internal_name = _normalize_pals(db, source_ids)
    _cross_check_palcalc_breeding(breeding, source_id_by_internal_name, audited_records)
    _cross_check_csv(locked["palweave_csv"], audited_records)
    pal_ids = {record["internal_id"] for record in pals}
    outcomes, outcome_counts = _normalize_outcomes(audited_records, pal_ids)

    counts = {
        "pal_records": len(pals),
        "source_derived_outcomes": len(outcomes),
        **outcome_counts,
    }
    for name, expected in EXPECTED_COUNTS.items():
        if counts.get(name) != expected:
            raise DatasetError(f"normalized count mismatch: {name}")

    pals_bytes = _json_bytes({"schema_version": 1, "dataset_id": DATASET_ID, "records": pals})
    outcome_chunks = []
    for index, offset in enumerate(range(0, len(outcomes), OUTCOME_CHUNK_SIZE)):
        records = outcomes[offset : offset + OUTCOME_CHUNK_SIZE]
        path = f"breeding-outcomes/part-{index:03d}.json"
        value = _json_bytes(
            {
                "schema_version": 1,
                "dataset_id": DATASET_ID,
                "part": index,
                "records": records,
            }
        )
        outcome_chunks.append((path, value, len(records)))
    manifest = _build_manifest(
        pals_bytes,
        outcome_chunks,
        locked["palcalc_license"],
        counts,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "breeding-outcomes.json").unlink(missing_ok=True)
    outcome_root = args.output / "breeding-outcomes"
    outcome_root.mkdir(parents=True, exist_ok=True)
    for stale_part in outcome_root.glob("part-*.json"):
        stale_part.unlink()
    outputs = {
        "manifest.json": _pretty_json_bytes(manifest),
        "pals.json": pals_bytes,
        "PALCALC-LICENSE.txt": locked["palcalc_license"],
        **{path: value for path, value, _ in outcome_chunks},
    }
    for name, value in outputs.items():
        _write_atomic(args.output / name, value)
    validate(args.output)


def validate(output: Path) -> None:
    try:
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        pals = json.loads((output / "pals.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetError("generated dataset is missing, unreadable, or malformed") from error

    if manifest.get("dataset_id") != DATASET_ID:
        raise DatasetError("generated manifest has the wrong dataset identity")
    identity = manifest.get("content_identity")
    if not isinstance(identity, dict) or identity.get("algorithm") != "sha256":
        raise DatasetError("generated manifest identity is missing")
    without_identity = dict(manifest)
    without_identity.pop("content_identity", None)
    if identity.get("digest") != _record_hash(without_identity):
        raise DatasetError("generated manifest identity does not match its content")

    pal_records = pals.get("records")
    if not isinstance(pal_records, list) or len(pal_records) != 299:
        raise DatasetError("generated Pal record count is invalid")
    generated_files = manifest.get("generated_files")
    if not isinstance(generated_files, list):
        raise DatasetError("generated manifest file inventory is invalid")
    outcome_files = [
        record
        for record in generated_files
        if isinstance(record, dict)
        and isinstance(record.get("path"), str)
        and record["path"].startswith("breeding-outcomes/part-")
    ]
    outcome_files.sort(key=lambda record: record["path"])
    outcome_records: list[dict[str, Any]] = []
    for expected_part, generated in enumerate(outcome_files):
        try:
            outcome_part = json.loads((output / generated["path"]).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DatasetError("generated outcome part is unreadable or malformed") from error
        if (
            outcome_part.get("dataset_id") != DATASET_ID
            or outcome_part.get("part") != expected_part
            or not isinstance(outcome_part.get("records"), list)
        ):
            raise DatasetError("generated outcome part contract is invalid")
        outcome_records.extend(outcome_part["records"])
    if not isinstance(outcome_records, list) or len(outcome_records) != 44_851:
        raise DatasetError("generated outcome count is invalid")
    pal_ids = {record.get("internal_id") for record in pal_records}
    if len(pal_ids) != 299 or any(
        not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None for value in pal_ids
    ):
        raise DatasetError("generated Pal identifiers are invalid or duplicated")
    if any(record.get("player_visible") is not None for record in pal_records):
        raise DatasetError("generated data inferred unsupported player visibility")
    if any(
        {
            record.get("parent_1_internal_id"),
            record.get("parent_2_internal_id"),
            record.get("child_internal_id"),
        }
        - pal_ids
        for record in outcome_records
    ):
        raise DatasetError("generated outcome contains an unresolved Pal reference")

    actual_kinds = Counter(record.get("result_kind") for record in outcome_records)
    for kind in ("same_species", "ordinary_power", "fixed_special", "gender_directed"):
        if actual_kinds[kind] != EXPECTED_COUNTS[kind]:
            raise DatasetError(f"generated result-kind count mismatch: {kind}")

    for generated in generated_files:
        path = output / generated["path"]
        try:
            value = path.read_bytes()
        except OSError as error:
            raise DatasetError("manifest references an unreadable generated file") from error
        if len(value) != generated["bytes"] or _sha256_bytes(value) != generated["sha256"]:
            raise DatasetError("generated file identity does not match the manifest")

    license_value = (output / "PALCALC-LICENSE.txt").read_bytes()
    if _sha256_bytes(license_value) != INPUT_LOCKS["palcalc_license"]["sha256"]:
        raise DatasetError("PalCalc license notice is not the pinned notice")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--palcalc-db", type=Path)
    parser.add_argument("--palcalc-breeding", type=Path)
    parser.add_argument("--palcalc-algorithm", type=Path)
    parser.add_argument("--palcalc-license", type=Path)
    parser.add_argument("--palweave-json", type=Path)
    parser.add_argument("--palweave-csv", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.validate_only:
            validate(args.output)
        else:
            required = (
                args.palcalc_db,
                args.palcalc_breeding,
                args.palcalc_algorithm,
                args.palcalc_license,
                args.palweave_json,
                args.palweave_csv,
            )
            if any(path is None for path in required):
                raise DatasetError("generation requires all six explicit local input paths")
            build(args)
    except DatasetError as error:
        print(f"dataset validation failed: {error}", file=sys.stderr)
        return 1
    print(f"dataset valid: {DATASET_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
