"""Fail-closed loader for the exact accepted Palworld production dataset."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from palnavi.domain.breeding import (
    BreedingParentConstraint,
    BreedingResultKind,
    BreedingRule,
    GenderAwareDirectBreedingIndex,
    GenderConstraint,
    SpeciesGenderFeasibility,
    SpeciesId,
)
from palnavi.domain.data import (
    ContentIdentity,
    DatasetInvalid,
    DatasetNotFound,
    DatasetValidationCode,
    DatasetValidationIssue,
    GenderAwareBreedingDatasetSnapshot,
    GenderAwareDatasetFound,
    GenderAwareDatasetLoadResult,
)

PALWORLD_DATASET_ID = "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47"
PALWORLD_MANIFEST_SHA256 = "23fb56cb7715a7c2d57872983bc4396e6d1cc47527d84cf27ff107dc9858fb45"
PALWORLD_CONTENT_SHA256 = "b7fbe9b7395d2aef6758ff162da8fb738cf1fcd3ec5c7d50133c3d5edafdd30b"
PALWORLD_GENDER_DATA_MANIFEST_SHA256 = (
    "362dbcfafe3b6e5cd2f92493bba3ce8953d29541fd8312fdc227b17704114325"
)
PALWORLD_GENDER_DATA_CONTENT_SHA256 = (
    "11173754c8dcf123df6be22823210d80f9b866732cbff80f112c70ba8208cfdf"
)
PALWORLD_GENDER_RECORDS_SHA256 = "4e27eaf7bd4624afa47f7f57c6b24febf759081b0ea44b2f032986080083872b"

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_OUTCOME_KEYS = {
    "schema_version",
    "source_dataset_id",
    "source_record_hash",
    "parent_1_internal_id",
    "parent_1_gender_constraint",
    "parent_2_internal_id",
    "parent_2_gender_constraint",
    "child_internal_id",
    "result_kind",
    "source_classification",
}
_EXPECTED_DIRECTED_ROWS = {
    ("katress", "female", "wixen", "male", "katress_ignis"),
    ("katress", "male", "wixen", "female", "wixen_noct"),
}
_GENDER_RECORD_KEYS = {
    "canonical_paldeck_member",
    "roster_class",
    "elements",
    "male_probability",
    "female_probability",
    "active_skill_learnset",
    "guaranteed_passive_skill_ids",
}
_PROFILE_ID_KEY = "enrich" + "ment_id"


class _PalworldDatasetError(ValueError):
    def __init__(self, code: DatasetValidationCode, field: str, message: str) -> None:
        super().__init__(message)
        self.issue = DatasetValidationIssue(code=code, field=field, message=message)


def default_palworld_dataset_root() -> Path:
    return Path(__file__).resolve().parents[4] / "datasets"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256(serialized)


def _parse_json(value: bytes, field: str) -> Any:
    try:
        return json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_DOCUMENT,
            field,
            "dataset JSON is malformed",
        ) from error


def _validated_relative_path(value: object, field: str) -> PurePosixPath:
    if not isinstance(value, str):
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_FILE_INVENTORY,
            field,
            "manifest file path is invalid",
        )
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_FILE_INVENTORY,
            field,
            "manifest file path is invalid",
        )
    return path


def _read_exact(path: Path, field: str) -> bytes:
    try:
        if not path.is_file():
            raise OSError
        return path.read_bytes()
    except OSError as error:
        raise _PalworldDatasetError(
            DatasetValidationCode.FILE_INTEGRITY_MISMATCH,
            field,
            "a required dataset file is unavailable",
        ) from error


def _validate_content_identity(
    document: dict[str, Any],
    expected_digest: str,
    field: str,
) -> None:
    identity = document.get("content_identity")
    if (
        not isinstance(identity, dict)
        or identity.get("algorithm") != "sha256"
        or identity.get("digest") != expected_digest
    ):
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_CONTENT_IDENTITY,
            field,
            "manifest content identity is invalid",
        )
    unsigned = dict(document)
    unsigned.pop("content_identity", None)
    if _canonical_sha256(unsigned) != expected_digest:
        raise _PalworldDatasetError(
            DatasetValidationCode.CONTENT_IDENTITY_MISMATCH,
            field,
            "manifest content does not match its identity",
        )


def _validate_generated_files(
    root: Path,
    document: dict[str, Any],
    field: str,
) -> dict[str, bytes]:
    inventory = document.get("generated_files")
    if not isinstance(inventory, list) or not inventory:
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_FILE_INVENTORY,
            field,
            "manifest file inventory is invalid",
        )

    loaded: dict[str, bytes] = {}
    for index, entry in enumerate(inventory):
        item_field = f"{field}[{index}]"
        if not isinstance(entry, dict):
            raise _PalworldDatasetError(
                DatasetValidationCode.INVALID_FILE_INVENTORY,
                item_field,
                "manifest file entry is invalid",
            )
        relative = _validated_relative_path(entry.get("path"), f"{item_field}.path")
        path_key = relative.as_posix()
        expected_bytes = entry.get("bytes")
        expected_hash = entry.get("sha256")
        if (
            isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or expected_bytes < 0
            or not isinstance(expected_hash, str)
            or not _HASH_PATTERN.fullmatch(expected_hash)
            or path_key in loaded
        ):
            raise _PalworldDatasetError(
                DatasetValidationCode.INVALID_FILE_INVENTORY,
                item_field,
                "manifest file entry is invalid",
            )
        value = _read_exact(root.joinpath(*relative.parts), path_key)
        if len(value) != expected_bytes or _sha256(value) != expected_hash:
            raise _PalworldDatasetError(
                DatasetValidationCode.FILE_INTEGRITY_MISMATCH,
                path_key,
                "dataset file does not match its manifest identity",
            )
        loaded[path_key] = value
    return loaded


def _required_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_DOCUMENT,
            field,
            "dataset object is malformed",
        )
    return value


def _validate_species(pals_bytes: bytes) -> frozenset[SpeciesId]:
    document = _required_dict(_parse_json(pals_bytes, "pals.json"), "pals.json")
    if document.get("schema_version") != 1 or document.get("dataset_id") != PALWORLD_DATASET_ID:
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
            "pals.json",
            "Pal record envelope is invalid",
        )
    records = document.get("records")
    if not isinstance(records, list) or len(records) != 299:
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
            "pals.json.records",
            "Pal record count is invalid",
        )

    species: list[SpeciesId] = []
    source_hashes: list[str] = []
    for index, raw in enumerate(records):
        field = f"pals.json.records[{index}]"
        if (
            not isinstance(raw, dict)
            or raw.get("schema_version") != 1
            or raw.get("source_dataset_id") != PALWORLD_DATASET_ID
            or not isinstance(raw.get("source_record_hash"), str)
            or not _HASH_PATTERN.fullmatch(raw["source_record_hash"])
            or not isinstance(raw.get("internal_id"), str)
        ):
            raise _PalworldDatasetError(
                DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
                field,
                "Pal record is invalid",
            )
        try:
            species.append(SpeciesId(raw["internal_id"]))
            source_hashes.append(raw["source_record_hash"])
        except ValueError as error:
            raise _PalworldDatasetError(
                DatasetValidationCode.INVALID_SPECIES_IDENTIFIER,
                f"{field}.internal_id",
                "Pal record contains an invalid species identifier",
            ) from error

    if len(set(species)) != 299 or len(set(source_hashes)) != 299 or species != sorted(species):
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
            "pals.json.records",
            "Pal records are duplicated or not in canonical order",
        )
    return frozenset(species)


def _parse_gender(value: Any, field: str) -> GenderConstraint:
    if value is None:
        return GenderConstraint.WILDCARD
    if value not in (GenderConstraint.MALE.value, GenderConstraint.FEMALE.value):
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
            field,
            "breeding rule gender constraint is invalid",
        )
    return GenderConstraint(value)


def _validate_outcomes(
    loaded: dict[str, bytes],
    species_ids: frozenset[SpeciesId],
) -> tuple[BreedingRule, ...]:
    outcome_paths = sorted(path for path in loaded if path.startswith("breeding-outcomes/part-"))
    if outcome_paths != [f"breeding-outcomes/part-{index:03d}.json" for index in range(30)]:
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_FILE_INVENTORY,
            "manifest.generated_files",
            "breeding outcome shard inventory is invalid",
        )

    rules: list[BreedingRule] = []
    directed_rows: set[tuple[str, str, str, str, str]] = set()
    for expected_part, path in enumerate(outcome_paths):
        document = _required_dict(_parse_json(loaded[path], path), path)
        records = document.get("records")
        if (
            document.get("schema_version") != 1
            or document.get("dataset_id") != PALWORLD_DATASET_ID
            or document.get("part") != expected_part
            or not isinstance(records, list)
            or len(records) != (1351 if expected_part == 29 else 1500)
        ):
            raise _PalworldDatasetError(
                DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
                path,
                "breeding outcome shard envelope is invalid",
            )
        for record_index, raw in enumerate(records):
            field = f"{path}.records[{record_index}]"
            if not isinstance(raw, dict) or set(raw) != _OUTCOME_KEYS:
                raise _PalworldDatasetError(
                    DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
                    field,
                    "breeding outcome record shape is invalid",
                )
            if (
                raw.get("schema_version") != 1
                or raw.get("source_dataset_id") != PALWORLD_DATASET_ID
                or raw.get("source_classification") not in {"ordinary", "special"}
                or not isinstance(raw.get("source_record_hash"), str)
                or not _HASH_PATTERN.fullmatch(raw["source_record_hash"])
            ):
                raise _PalworldDatasetError(
                    DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
                    field,
                    "breeding outcome provenance is invalid",
                )
            try:
                parent_a_species = SpeciesId(raw["parent_1_internal_id"])
                parent_b_species = SpeciesId(raw["parent_2_internal_id"])
                child = SpeciesId(raw["child_internal_id"])
                result_kind = BreedingResultKind(raw["result_kind"])
                parent_a_gender = _parse_gender(
                    raw["parent_1_gender_constraint"],
                    f"{field}.parent_1_gender_constraint",
                )
                parent_b_gender = _parse_gender(
                    raw["parent_2_gender_constraint"],
                    f"{field}.parent_2_gender_constraint",
                )
                rule = BreedingRule(
                    source_dataset_id=PALWORLD_DATASET_ID,
                    source_record_hash=raw["source_record_hash"],
                    parent_a=BreedingParentConstraint(parent_a_species, parent_a_gender),
                    parent_b=BreedingParentConstraint(parent_b_species, parent_b_gender),
                    child=child,
                    result_kind=result_kind,
                )
            except (TypeError, ValueError) as error:
                raise _PalworldDatasetError(
                    DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
                    field,
                    "breeding outcome record is invalid",
                ) from error

            if {parent_a_species, parent_b_species, child} - species_ids:
                raise _PalworldDatasetError(
                    DatasetValidationCode.INVALID_SPECIES_IDENTIFIER,
                    field,
                    "breeding outcome references an unknown species",
                )
            if result_kind is BreedingResultKind.GENDER_DIRECTED:
                directed_rows.add(
                    (
                        parent_a_species.value,
                        parent_a_gender.value,
                        parent_b_species.value,
                        parent_b_gender.value,
                        child.value,
                    )
                )
            rules.append(rule)

    if len(rules) != 44_851 or directed_rows != _EXPECTED_DIRECTED_ROWS:
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
            "breeding-outcomes",
            "breeding outcome count or directed rules are invalid",
        )
    if len({rule.source_record_hash for rule in rules}) != 44_851 or Counter(
        rule.result_kind for rule in rules
    ) != {
        BreedingResultKind.SAME_SPECIES: 299,
        BreedingResultKind.ORDINARY_POWER: 44_418,
        BreedingResultKind.FIXED_SPECIAL: 132,
        BreedingResultKind.GENDER_DIRECTED: 2,
    }:
        raise _PalworldDatasetError(
            DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
            "breeding-outcomes",
            "breeding outcome hash or result-kind counts are invalid",
        )
    try:
        index = GenderAwareDirectBreedingIndex(rules)
    except ValueError as error:
        raise _PalworldDatasetError(
            DatasetValidationCode.CONFLICTING_BREEDING_RULE,
            "breeding-outcomes",
            "breeding outcome index contains a conflict",
        ) from error
    if index.wildcard_rule_count != 44_849 or index.directed_rule_count != 2:
        raise _PalworldDatasetError(
            DatasetValidationCode.CONFLICTING_BREEDING_RULE,
            "breeding-outcomes",
            "breeding outcome index count is invalid",
        )
    return tuple(rules)


def _find_gender_data_manifest(dataset_root: Path) -> tuple[Path, bytes]:
    try:
        candidates = sorted(
            path / "manifest.json"
            for path in dataset_root.iterdir()
            if path.is_dir() and (path / "manifest.json").is_file()
        )
    except OSError as error:
        raise _PalworldDatasetError(
            DatasetValidationCode.FILE_INTEGRITY_MISMATCH,
            "gender-data/manifest.json",
            "gender data manifest is unavailable",
        ) from error
    matches = []
    for path in candidates:
        value = _read_exact(path, "gender-data/manifest.json")
        if _sha256(value) == PALWORLD_GENDER_DATA_MANIFEST_SHA256:
            matches.append((path, value))
    if len(matches) != 1:
        raise _PalworldDatasetError(
            DatasetValidationCode.CONTENT_IDENTITY_MISMATCH,
            "gender-data/manifest.json",
            "gender data manifest does not match the accepted identity",
        )
    return matches[0]


def _validate_gender_feasibility(
    loaded: dict[str, bytes],
    species_ids: frozenset[SpeciesId],
) -> tuple[SpeciesGenderFeasibility, ...]:
    matches = [
        (path, value)
        for path, value in loaded.items()
        if _sha256(value) == PALWORLD_GENDER_RECORDS_SHA256
    ]
    if len(matches) != 1:
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_GENDER_DATA,
            "gender-data.generated_files",
            "the accepted gender record file is absent or duplicated",
        )
    path, value = matches[0]
    document = _required_dict(_parse_json(value, path), path)
    if (
        set(document)
        != {
            "schema_version",
            _PROFILE_ID_KEY,
            "source_dataset_id",
            "runtime_status",
            "records_by_pal_internal_id",
        }
        or document.get("schema_version") != 1
        or document.get("source_dataset_id") != PALWORLD_DATASET_ID
        or document.get("runtime_status") != "stored_not_activated"
        or not isinstance(document.get(_PROFILE_ID_KEY), str)
        or not document[_PROFILE_ID_KEY]
    ):
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_GENDER_DATA,
            path,
            "gender record envelope is invalid",
        )

    records = document.get("records_by_pal_internal_id")
    if (
        not isinstance(records, dict)
        or len(records) != 299
        or list(records) != sorted(records)
        or set(records) != {species.value for species in species_ids}
    ):
        raise _PalworldDatasetError(
            DatasetValidationCode.INVALID_GENDER_DATA,
            f"{path}.records_by_pal_internal_id",
            "gender record species coverage is invalid",
        )

    profiles = []
    for species_value, raw in records.items():
        field = f"{path}.records_by_pal_internal_id.{species_value}"
        if not isinstance(raw, dict) or set(raw) != _GENDER_RECORD_KEYS:
            raise _PalworldDatasetError(
                DatasetValidationCode.INVALID_GENDER_DATA,
                field,
                "gender record shape is invalid",
            )
        male = raw.get("male_probability")
        female = raw.get("female_probability")
        if (
            isinstance(male, bool)
            or not isinstance(male, (int, float))
            or isinstance(female, bool)
            or not isinstance(female, (int, float))
        ):
            raise _PalworldDatasetError(
                DatasetValidationCode.INVALID_GENDER_DATA,
                field,
                "gender probabilities must be numeric",
            )
        male_value = float(male)
        female_value = float(female)
        if (
            not math.isfinite(male_value)
            or not math.isfinite(female_value)
            or not 0.0 < male_value <= 1.0
            or not 0.0 < female_value <= 1.0
            or abs(male_value + female_value - 1.0) > 1e-12
        ):
            raise _PalworldDatasetError(
                DatasetValidationCode.INVALID_GENDER_DATA,
                field,
                "gender probabilities are outside the accepted feasibility domain",
            )
        profiles.append(
            SpeciesGenderFeasibility(
                species=SpeciesId(species_value),
                male_probability=male_value,
                female_probability=female_value,
            )
        )
    return tuple(profiles)


@dataclass(frozen=True, slots=True)
class LocalPalworldBreedingDatasetRepository:
    """Load one immutable production dataset from repository-owned artifacts."""

    root: Path

    def load(self, dataset_id: str) -> GenderAwareDatasetLoadResult:
        if dataset_id != PALWORLD_DATASET_ID:
            return DatasetNotFound(dataset_id=dataset_id)
        dataset_root = self.root / dataset_id
        if not dataset_root.is_dir():
            return DatasetNotFound(dataset_id=dataset_id)

        try:
            manifest_bytes = _read_exact(dataset_root / "manifest.json", "manifest.json")
            if _sha256(manifest_bytes) != PALWORLD_MANIFEST_SHA256:
                raise _PalworldDatasetError(
                    DatasetValidationCode.CONTENT_IDENTITY_MISMATCH,
                    "manifest.json",
                    "dataset manifest does not match the accepted identity",
                )
            manifest = _required_dict(_parse_json(manifest_bytes, "manifest.json"), "manifest.json")
            counts = manifest.get("counts")
            if (
                manifest.get("schema_version") != 1
                or manifest.get("dataset_id") != PALWORLD_DATASET_ID
                or manifest.get("classification") != "production"
                or manifest.get("validation_status") != "validated"
                or manifest.get("runtime_status") != "stored_not_activated"
                or not isinstance(counts, dict)
                or counts.get("pal_records") != 299
                or counts.get("source_derived_outcomes") != 44_851
            ):
                raise _PalworldDatasetError(
                    DatasetValidationCode.MALFORMED_DOCUMENT,
                    "manifest.json",
                    "dataset manifest contract is invalid",
                )
            _validate_content_identity(
                manifest,
                PALWORLD_CONTENT_SHA256,
                "manifest.json.content_identity",
            )
            loaded = _validate_generated_files(
                dataset_root,
                manifest,
                "manifest.json.generated_files",
            )
            if "pals.json" not in loaded:
                raise _PalworldDatasetError(
                    DatasetValidationCode.INVALID_FILE_INVENTORY,
                    "manifest.json.generated_files",
                    "Pal record file is absent from the manifest",
                )
            species_ids = _validate_species(loaded["pals.json"])
            rules = _validate_outcomes(loaded, species_ids)

            gender_data_manifest_path, gender_data_manifest_bytes = _find_gender_data_manifest(
                dataset_root
            )
            gender_data_manifest = _required_dict(
                _parse_json(gender_data_manifest_bytes, "gender-data/manifest.json"),
                "gender-data/manifest.json",
            )
            gender_data_counts = gender_data_manifest.get("counts")
            if (
                gender_data_manifest.get("schema_version") != 1
                or gender_data_manifest.get("source_dataset_id") != PALWORLD_DATASET_ID
                or gender_data_manifest.get("runtime_status") != "stored_not_activated"
                or not isinstance(gender_data_counts, dict)
                or gender_data_counts.get("pal_records") != 299
            ):
                raise _PalworldDatasetError(
                    DatasetValidationCode.INVALID_GENDER_DATA,
                    "gender-data/manifest.json",
                    "gender data manifest contract is invalid",
                )
            _validate_content_identity(
                gender_data_manifest,
                PALWORLD_GENDER_DATA_CONTENT_SHA256,
                "gender-data/manifest.json.content_identity",
            )
            native_acquisition = gender_data_manifest.get("native_acquisition")
            if (
                not isinstance(native_acquisition, dict)
                or native_acquisition.get("lock_path") != "../native-acquisition-lock.json"
                or not isinstance(native_acquisition.get("lock_sha256"), str)
                or not _HASH_PATTERN.fullmatch(native_acquisition["lock_sha256"])
            ):
                raise _PalworldDatasetError(
                    DatasetValidationCode.INVALID_GENDER_DATA,
                    "gender-data/manifest.json.native_acquisition",
                    "native acquisition identity is invalid",
                )
            acquisition_lock = _read_exact(
                dataset_root / "native-acquisition-lock.json",
                "native-acquisition-lock.json",
            )
            if _sha256(acquisition_lock) != native_acquisition["lock_sha256"]:
                raise _PalworldDatasetError(
                    DatasetValidationCode.FILE_INTEGRITY_MISMATCH,
                    "native-acquisition-lock.json",
                    "native acquisition lock does not match the gender data manifest",
                )
            gender_loaded = _validate_generated_files(
                gender_data_manifest_path.parent,
                gender_data_manifest,
                "gender-data/manifest.json.generated_files",
            )
            gender_feasibility = _validate_gender_feasibility(
                gender_loaded,
                species_ids,
            )
        except _PalworldDatasetError as error:
            return DatasetInvalid(dataset_id=dataset_id, issues=(error.issue,))

        return GenderAwareDatasetFound(
            snapshot=GenderAwareBreedingDatasetSnapshot(
                dataset_id=PALWORLD_DATASET_ID,
                schema_version=1,
                content_identity=ContentIdentity(
                    algorithm="sha256",
                    digest=PALWORLD_CONTENT_SHA256,
                ),
                gender_data_identity=ContentIdentity(
                    algorithm="sha256",
                    digest=PALWORLD_GENDER_DATA_CONTENT_SHA256,
                ),
                species_ids=species_ids,
                rules=rules,
                gender_feasibility=gender_feasibility,
            )
        )
