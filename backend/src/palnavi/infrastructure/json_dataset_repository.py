"""Read-only repository for validated local JSON breeding datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from palnavi.domain.data import (
    DATASET_ID_PATTERN,
    DatasetInvalid,
    DatasetLoadResult,
    DatasetNotFound,
    DatasetValidationCode,
    DatasetValidationIssue,
)
from palnavi.infrastructure.dataset_validation import BreedingDatasetImporter


@dataclass(frozen=True, slots=True)
class LocalJsonBreedingDatasetRepository:
    """Load immutable snapshots from one directory per stable dataset identifier."""

    root: Path
    importer: BreedingDatasetImporter = field(default_factory=BreedingDatasetImporter)

    def load(self, dataset_id: str) -> DatasetLoadResult:
        if DATASET_ID_PATTERN.fullmatch(dataset_id) is None:
            return DatasetInvalid(
                dataset_id=dataset_id,
                issues=(
                    DatasetValidationIssue(
                        code=DatasetValidationCode.INVALID_DATASET_ID,
                        field="dataset_id",
                        message="dataset identifier has an invalid format",
                    ),
                ),
            )

        dataset_directory = self.root / dataset_id
        if not dataset_directory.is_dir():
            return DatasetNotFound(dataset_id=dataset_id)

        try:
            manifest = json.loads((dataset_directory / "manifest.json").read_text(encoding="utf-8"))
            relationships = json.loads(
                (dataset_directory / "relationships.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return DatasetInvalid(
                dataset_id=dataset_id,
                issues=(
                    DatasetValidationIssue(
                        code=DatasetValidationCode.MALFORMED_DOCUMENT,
                        field="dataset",
                        message="dataset documents are missing, unreadable, or malformed",
                    ),
                ),
            )

        return self.importer.import_documents(
            manifest_document=manifest,
            relationship_document=relationships,
            expected_dataset_id=dataset_id,
        )


def default_dataset_root() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "samples" / "datasets"
