"""Application service for the fixed validated Palworld species catalog."""

from dataclasses import dataclass
from enum import StrEnum

from palnavi.domain.data import (
    DatasetInvalid,
    DatasetNotFound,
    DatasetValidationIssue,
    SpeciesCatalogFound,
    SpeciesCatalogRepository,
    SpeciesCatalogSnapshot,
)


class SpeciesCatalogFailureKind(StrEnum):
    DATASET_NOT_FOUND = "dataset_not_found"
    DATASET_INVALID = "dataset_invalid"


@dataclass(frozen=True, slots=True)
class SpeciesCatalogSuccess:
    snapshot: SpeciesCatalogSnapshot


@dataclass(frozen=True, slots=True)
class SpeciesCatalogFailure:
    dataset_id: str
    kind: SpeciesCatalogFailureKind
    issues: tuple[DatasetValidationIssue, ...] = ()


SpeciesCatalogOutcome = SpeciesCatalogSuccess | SpeciesCatalogFailure


class SpeciesCatalogService:
    def __init__(self, repository: SpeciesCatalogRepository) -> None:
        self._repository = repository

    def load(self, dataset_id: str) -> SpeciesCatalogOutcome:
        result = self._repository.load(dataset_id)
        if isinstance(result, SpeciesCatalogFound):
            return SpeciesCatalogSuccess(snapshot=result.snapshot)
        if isinstance(result, DatasetNotFound):
            return SpeciesCatalogFailure(
                dataset_id=result.dataset_id,
                kind=SpeciesCatalogFailureKind.DATASET_NOT_FOUND,
            )
        if isinstance(result, DatasetInvalid):
            return SpeciesCatalogFailure(
                dataset_id=result.dataset_id,
                kind=SpeciesCatalogFailureKind.DATASET_INVALID,
                issues=result.issues,
            )
        raise AssertionError("species catalog repository returned an unsupported result")
