import copy
import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

import palnavi.infrastructure.palworld_dataset_repository as repository_module
from palnavi.domain.data import (
    DatasetInvalid,
    DatasetNotFound,
    GenderAwareDatasetFound,
    SpeciesCatalogFound,
)
from palnavi.infrastructure.palworld_dataset_repository import (
    PALWORLD_CATALOG_LOCALE_TAGS,
    PALWORLD_CONTENT_SHA256,
    PALWORLD_DATASET_ID,
    LocalPalworldBreedingDatasetRepository,
    LocalPalworldSpeciesCatalogRepository,
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


def _rewrite_pals(
    dataset: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[list[dict[str, object]]], None],
) -> None:
    pals_path = dataset / "pals.json"
    document = json.loads(pals_path.read_text(encoding="utf-8"))
    records = document["records"]
    assert isinstance(records, list)
    mutate(records)
    pals_bytes = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
    pals_path.write_bytes(pals_bytes)

    manifest_path = dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generated = next(entry for entry in manifest["generated_files"] if entry["path"] == "pals.json")
    generated["bytes"] = len(pals_bytes)
    generated["sha256"] = _sha256(pals_bytes)
    unsigned = copy.deepcopy(manifest)
    unsigned.pop("content_identity")
    content_digest = _canonical_sha256(unsigned)
    manifest["content_identity"]["digest"] = content_digest
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    monkeypatch.setattr(repository_module, "PALWORLD_CONTENT_SHA256", content_digest)
    monkeypatch.setattr(repository_module, "PALWORLD_MANIFEST_SHA256", _sha256(manifest_bytes))


def test_exact_catalog_loads_all_localized_records() -> None:
    loaded = LocalPalworldSpeciesCatalogRepository(default_palworld_dataset_root()).load(
        PALWORLD_DATASET_ID
    )

    assert isinstance(loaded, SpeciesCatalogFound)
    snapshot = loaded.snapshot
    assert snapshot.dataset_id == PALWORLD_DATASET_ID
    assert snapshot.content_identity.digest == PALWORLD_CONTENT_SHA256
    assert snapshot.locale_tags == PALWORLD_CATALOG_LOCALE_TAGS
    assert len(snapshot.records) == 299
    assert [record.species_id for record in snapshot.records] == sorted(
        record.species_id for record in snapshot.records
    )
    anubis = next(record for record in snapshot.records if record.species_id.value == "anubis")
    names = dict(anubis.localized_names)
    assert (names["en"], names["ja"], names["zh-Hans"], names["zh-Hant"]) == (
        "Anubis",
        "アヌビス",
        "阿努比斯",
        "阿努比斯",
    )
    assert anubis.source_record_sha256 == (
        "16fa84241baad9b7a23f3717a3f5dd03c9f1834daa2940e6a1ba8210ed920fb4"
    )


def test_unknown_catalog_is_not_found(tmp_path: Path) -> None:
    repository = LocalPalworldSpeciesCatalogRepository(tmp_path)

    assert isinstance(repository.load("another-dataset"), DatasetNotFound)
    assert isinstance(repository.load(PALWORLD_DATASET_ID), DatasetNotFound)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda records: records[0].__setitem__("unexpected", "value"),
        lambda records: records[1].__setitem__("internal_id", records[0]["internal_id"]),
        lambda records: records[1].__setitem__(
            "source_internal_name",
            records[0]["source_internal_name"],
        ),
        lambda records: records[0]["localized_names"].pop("ja"),
        lambda records: records[0].__setitem__("source_record_hash", "invalid"),
    ],
)
def test_malformed_duplicate_missing_locale_or_invalid_hash_fails_closed(
    copied_dataset: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[list[dict[str, object]]], None],
) -> None:
    root, dataset = copied_dataset
    _rewrite_pals(dataset, monkeypatch, mutate)

    loaded = LocalPalworldSpeciesCatalogRepository(root).load(PALWORLD_DATASET_ID)

    assert isinstance(loaded, DatasetInvalid)


def test_catalog_and_breeding_species_set_mismatch_fails_closed() -> None:
    breeding = LocalPalworldBreedingDatasetRepository(default_palworld_dataset_root()).load(
        PALWORLD_DATASET_ID
    )
    assert isinstance(breeding, GenderAwareDatasetFound)
    missing_species = next(iter(breeding.snapshot.species_ids))
    mismatched = GenderAwareDatasetFound(
        snapshot=replace(
            breeding.snapshot,
            species_ids=breeding.snapshot.species_ids - {missing_species},
        )
    )

    class MismatchedBreedingRepository:
        def load(self, dataset_id: str) -> GenderAwareDatasetFound:
            assert dataset_id == PALWORLD_DATASET_ID
            return mismatched

    loaded = LocalPalworldSpeciesCatalogRepository(
        default_palworld_dataset_root(),
        breeding_repository=MismatchedBreedingRepository(),
    ).load(PALWORLD_DATASET_ID)

    assert isinstance(loaded, DatasetInvalid)
    assert loaded.issues[0].message == "catalog and breeding species sets do not match"
