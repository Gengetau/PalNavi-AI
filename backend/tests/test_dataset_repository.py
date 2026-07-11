import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from palnavi.domain.data import DatasetFound, DatasetInvalid, DatasetNotFound
from palnavi.infrastructure.json_dataset_repository import (
    LocalJsonBreedingDatasetRepository,
    default_dataset_root,
)


def test_repository_loads_by_stable_dataset_identifier() -> None:
    repository = LocalJsonBreedingDatasetRepository(default_dataset_root())

    result = repository.load("synthetic-v1")

    assert isinstance(result, DatasetFound)
    assert result.snapshot.metadata.dataset_id == "synthetic-v1"


def test_repository_reports_dataset_not_found() -> None:
    repository = LocalJsonBreedingDatasetRepository(default_dataset_root())

    result = repository.load("missing-dataset")

    assert result == DatasetNotFound(dataset_id="missing-dataset")


def test_repository_results_are_immutable_and_fresh() -> None:
    repository = LocalJsonBreedingDatasetRepository(default_dataset_root())

    first = repository.load("synthetic-v1")
    second = repository.load("synthetic-v1")

    assert isinstance(first, DatasetFound)
    assert isinstance(second, DatasetFound)
    assert first.snapshot == second.snapshot
    assert first.snapshot is not second.snapshot
    assert isinstance(first.snapshot.relationships, tuple)
    assert isinstance(first.snapshot.species_ids, frozenset)
    with pytest.raises(FrozenInstanceError):
        first.snapshot.metadata.dataset_id = "changed"  # type: ignore[misc]


def test_repository_reports_invalid_local_dataset(tmp_path: Path) -> None:
    source = default_dataset_root() / "synthetic-v1"
    target = tmp_path / "synthetic-v1"
    target.mkdir()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    manifest["content_identity"]["digest"] = "0" * 64
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (target / "relationships.json").write_text(
        (source / "relationships.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = LocalJsonBreedingDatasetRepository(tmp_path).load("synthetic-v1")

    assert isinstance(result, DatasetInvalid)
    assert result.issues[0].code.value == "content_identity_mismatch"


def test_repository_rejects_path_like_dataset_identifier(tmp_path: Path) -> None:
    result = LocalJsonBreedingDatasetRepository(tmp_path).load("../synthetic-v1")

    assert isinstance(result, DatasetInvalid)
    assert result.issues[0].code.value == "invalid_dataset_id"
