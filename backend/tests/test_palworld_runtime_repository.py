import copy
import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

import palnavi.infrastructure.palworld_dataset_repository as repository_module
from palnavi.domain.breeding import BreedingResultKind
from palnavi.domain.data import DatasetInvalid, DatasetNotFound, GenderAwareDatasetFound
from palnavi.infrastructure.palworld_dataset_repository import (
    PALWORLD_CONTENT_SHA256,
    PALWORLD_DATASET_ID,
    PALWORLD_GENDER_DATA_CONTENT_SHA256,
    LocalPalworldBreedingDatasetRepository,
    default_palworld_dataset_root,
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


@pytest.fixture
def copied_dataset(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "datasets"
    dataset = root / PALWORLD_DATASET_ID
    shutil.copytree(default_palworld_dataset_root() / PALWORLD_DATASET_ID, dataset)
    return root, dataset


def _load(root: Path) -> GenderAwareDatasetFound | DatasetNotFound | DatasetInvalid:
    return LocalPalworldBreedingDatasetRepository(root).load(PALWORLD_DATASET_ID)


def _rewrite_outcome(
    dataset: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    shard_path = dataset / "breeding-outcomes" / "part-020.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    records = shard["records"]
    assert isinstance(records, list)
    target = next(
        record
        for record in records
        if isinstance(record, dict)
        and record.get("parent_1_internal_id") == "katress"
        and record.get("parent_2_internal_id") == "wixen"
    )
    mutate(target)
    shard_bytes = (
        json.dumps(shard, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"
    ).encode()
    shard_path.write_bytes(shard_bytes)

    manifest_path = dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generated = next(
        entry
        for entry in manifest["generated_files"]
        if entry["path"] == "breeding-outcomes/part-020.json"
    )
    generated["bytes"] = len(shard_bytes)
    generated["sha256"] = _sha256(shard_bytes)
    unsigned = copy.deepcopy(manifest)
    unsigned.pop("content_identity")
    content_digest = _canonical_sha256(unsigned)
    manifest["content_identity"]["digest"] = content_digest
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    monkeypatch.setattr(repository_module, "PALWORLD_CONTENT_SHA256", content_digest)
    monkeypatch.setattr(repository_module, "PALWORLD_MANIFEST_SHA256", _sha256(manifest_bytes))


def _rewrite_gender_record(
    dataset: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    record_path = dataset / "enrichment" / "pal-enrichment.json"
    document = json.loads(record_path.read_text(encoding="utf-8"))
    records = document["records_by_pal_internal_id"]
    assert isinstance(records, dict)
    target = records["katress"]
    assert isinstance(target, dict)
    mutate(target)
    record_bytes = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
    record_path.write_bytes(record_bytes)

    manifest_path = dataset / "enrichment" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generated = next(
        entry for entry in manifest["generated_files"] if entry["path"] == "pal-enrichment.json"
    )
    generated["bytes"] = len(record_bytes)
    generated["sha256"] = _sha256(record_bytes)
    unsigned = copy.deepcopy(manifest)
    unsigned.pop("content_identity")
    content_digest = _canonical_sha256(unsigned)
    manifest["content_identity"]["digest"] = content_digest
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    monkeypatch.setattr(repository_module, "PALWORLD_GENDER_RECORDS_SHA256", _sha256(record_bytes))
    monkeypatch.setattr(
        repository_module,
        "PALWORLD_GENDER_DATA_CONTENT_SHA256",
        content_digest,
    )
    monkeypatch.setattr(
        repository_module,
        "PALWORLD_GENDER_DATA_MANIFEST_SHA256",
        _sha256(manifest_bytes),
    )


def test_exact_production_snapshot_loads_all_bound_records() -> None:
    loaded = _load(default_palworld_dataset_root())

    assert isinstance(loaded, GenderAwareDatasetFound)
    snapshot = loaded.snapshot
    assert snapshot.dataset_id == PALWORLD_DATASET_ID
    assert snapshot.content_identity.digest == PALWORLD_CONTENT_SHA256
    assert snapshot.gender_data_identity.digest == PALWORLD_GENDER_DATA_CONTENT_SHA256
    assert len(snapshot.species_ids) == 299
    assert len(snapshot.rules) == 44_851
    assert len(snapshot.gender_feasibility) == 299
    assert [item.species for item in snapshot.gender_feasibility] == sorted(snapshot.species_ids)
    assert all(
        item.male_probability > 0
        and item.female_probability > 0
        and item.male_probability + item.female_probability == pytest.approx(1.0)
        for item in snapshot.gender_feasibility
    )
    assert (
        sum(rule.result_kind is BreedingResultKind.GENDER_DIRECTED for rule in snapshot.rules) == 2
    )
    assert {
        (
            rule.parent_a.species.value,
            rule.parent_a.gender.value,
            rule.parent_b.species.value,
            rule.parent_b.gender.value,
            rule.child.value,
            rule.source_record_hash,
        )
        for rule in snapshot.rules
        if rule.result_kind is BreedingResultKind.GENDER_DIRECTED
    } == {
        (
            "katress",
            "female",
            "wixen",
            "male",
            "katress_ignis",
            "bfe5c673830368aee57ad9e5cbb77517c9560915779f47c392f042adb77198d0",
        ),
        (
            "katress",
            "male",
            "wixen",
            "female",
            "wixen_noct",
            "9da3059bdaa87c8a40b9446c72004720b18f41ad8370dabf23688eb0ce944452",
        ),
    }
    assert all(
        len(rule.source_record_hash) == 64
        and set(rule.source_record_hash) <= set("0123456789abcdef")
        for rule in snapshot.rules
    )


def test_unsupported_or_absent_dataset_is_not_found(tmp_path: Path) -> None:
    repository = LocalPalworldBreedingDatasetRepository(tmp_path)
    assert isinstance(repository.load("another-dataset"), DatasetNotFound)
    assert isinstance(repository.load(PALWORLD_DATASET_ID), DatasetNotFound)


def test_altered_manifest_fails_closed(copied_dataset: tuple[Path, Path]) -> None:
    root, dataset = copied_dataset
    manifest = dataset / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")

    loaded = _load(root)

    assert isinstance(loaded, DatasetInvalid)
    assert loaded.issues[0].field == "manifest.json"


def test_altered_bound_shard_fails_closed(copied_dataset: tuple[Path, Path]) -> None:
    root, dataset = copied_dataset
    shard = dataset / "breeding-outcomes" / "part-000.json"
    shard.write_bytes(shard.read_bytes() + b" ")

    loaded = _load(root)

    assert isinstance(loaded, DatasetInvalid)
    assert loaded.issues[0].code.value == "file_integrity_mismatch"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row.__setitem__("source_record_hash", "invalid"),
        lambda row: row.__setitem__("parent_1_internal_id", "unknown_species"),
        lambda row: row.__setitem__("child_internal_id", "anubis"),
    ],
)
def test_altered_hash_species_or_directed_rule_fails_inner_validation(
    copied_dataset: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    root, dataset = copied_dataset
    _rewrite_outcome(dataset, monkeypatch, mutate)

    loaded = _load(root)

    assert isinstance(loaded, DatasetInvalid)
    assert loaded.issues[0].code.value in {
        "malformed_palworld_record",
        "invalid_species_identifier",
    }


def test_altered_enrichment_identity_fails_closed(
    copied_dataset: tuple[Path, Path],
) -> None:
    root, dataset = copied_dataset
    enrichment = dataset / "enrichment" / "pal-enrichment.json"
    enrichment.write_bytes(enrichment.read_bytes() + b" ")

    loaded = _load(root)

    assert isinstance(loaded, DatasetInvalid)
    assert loaded.issues[0].code.value == "file_integrity_mismatch"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row.__setitem__("male_probability", True),
        lambda row: row.__setitem__("male_probability", 0),
        lambda row: row.__setitem__("female_probability", 0.6),
        lambda row: row.pop("female_probability"),
    ],
)
def test_manifest_retargeted_invalid_gender_probability_fails_inner_validation(
    copied_dataset: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    root, dataset = copied_dataset
    _rewrite_gender_record(dataset, monkeypatch, mutate)

    loaded = _load(root)

    assert isinstance(loaded, DatasetInvalid)
    assert loaded.issues[0].code.value == "invalid_gender_data"


def test_altered_native_acquisition_lock_fails_closed(
    copied_dataset: tuple[Path, Path],
) -> None:
    root, dataset = copied_dataset
    lock = dataset / "native-acquisition-lock.json"
    lock.write_bytes(lock.read_bytes() + b" ")

    loaded = _load(root)

    assert isinstance(loaded, DatasetInvalid)
    assert loaded.issues[0].field == "native-acquisition-lock.json"
