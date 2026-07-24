"""Application service for exact, repository-backed direct breeding queries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from palnavi.domain.breeding import (
    DirectBreedingRequest,
    DirectBreedingResult,
    GenderAwareDirectBreedingIndex,
)
from palnavi.domain.data import (
    ContentIdentity,
    DatasetInvalid,
    DatasetNotFound,
    DatasetValidationIssue,
    GenderAwareBreedingDatasetRepository,
    GenderAwareDatasetFound,
)


@dataclass(frozen=True, slots=True)
class DirectBreedingQuerySuccess:
    dataset_id: str
    content_identity: ContentIdentity
    gender_data_identity: ContentIdentity
    result: DirectBreedingResult


class DirectBreedingQueryFailureKind(StrEnum):
    DATASET_NOT_FOUND = "dataset_not_found"
    DATASET_INVALID = "dataset_invalid"


@dataclass(frozen=True, slots=True)
class DirectBreedingQueryFailure:
    kind: DirectBreedingQueryFailureKind
    dataset_id: str
    issues: tuple[DatasetValidationIssue, ...]


DirectBreedingQueryOutcome = DirectBreedingQuerySuccess | DirectBreedingQueryFailure


@dataclass(frozen=True, slots=True)
class DirectBreedingService:
    repository: GenderAwareBreedingDatasetRepository

    def query(
        self,
        dataset_id: str,
        request: DirectBreedingRequest,
    ) -> DirectBreedingQueryOutcome:
        loaded = self.repository.load(dataset_id)
        if isinstance(loaded, DatasetNotFound):
            return DirectBreedingQueryFailure(
                kind=DirectBreedingQueryFailureKind.DATASET_NOT_FOUND,
                dataset_id=dataset_id,
                issues=(),
            )
        if isinstance(loaded, DatasetInvalid):
            return DirectBreedingQueryFailure(
                kind=DirectBreedingQueryFailureKind.DATASET_INVALID,
                dataset_id=dataset_id,
                issues=loaded.issues,
            )
        if not isinstance(loaded, GenderAwareDatasetFound):
            raise AssertionError("repository returned an unsupported result type")

        snapshot = loaded.snapshot
        index = GenderAwareDirectBreedingIndex(snapshot.rules)
        return DirectBreedingQuerySuccess(
            dataset_id=snapshot.dataset_id,
            content_identity=snapshot.content_identity,
            gender_data_identity=snapshot.gender_data_identity,
            result=index.query(request),
        )
