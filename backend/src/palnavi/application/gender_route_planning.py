"""Application service for production-backed gender-capable route planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from palnavi.domain.breeding import (
    GenderAwareRoutePlanner,
    GenderRoutePlanningRequest,
    GenderRouteResult,
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
class GenderRoutePlanningSuccess:
    dataset_id: str
    content_identity: ContentIdentity
    gender_data_identity: ContentIdentity
    result: GenderRouteResult


class GenderRoutePlanningFailureKind(StrEnum):
    DATASET_NOT_FOUND = "dataset_not_found"
    DATASET_INVALID = "dataset_invalid"


@dataclass(frozen=True, slots=True)
class GenderRoutePlanningFailure:
    kind: GenderRoutePlanningFailureKind
    dataset_id: str
    issues: tuple[DatasetValidationIssue, ...]


GenderRoutePlanningOutcome = GenderRoutePlanningSuccess | GenderRoutePlanningFailure


@dataclass(frozen=True, slots=True)
class GenderRoutePlanningService:
    repository: GenderAwareBreedingDatasetRepository
    planner: GenderAwareRoutePlanner

    def plan(
        self,
        dataset_id: str,
        request: GenderRoutePlanningRequest,
    ) -> GenderRoutePlanningOutcome:
        loaded = self.repository.load(dataset_id)
        if isinstance(loaded, DatasetNotFound):
            return GenderRoutePlanningFailure(
                kind=GenderRoutePlanningFailureKind.DATASET_NOT_FOUND,
                dataset_id=dataset_id,
                issues=(),
            )
        if isinstance(loaded, DatasetInvalid):
            return GenderRoutePlanningFailure(
                kind=GenderRoutePlanningFailureKind.DATASET_INVALID,
                dataset_id=dataset_id,
                issues=loaded.issues,
            )
        if not isinstance(loaded, GenderAwareDatasetFound):
            raise AssertionError("repository returned an unsupported result type")

        snapshot = loaded.snapshot
        return GenderRoutePlanningSuccess(
            dataset_id=snapshot.dataset_id,
            content_identity=snapshot.content_identity,
            gender_data_identity=snapshot.gender_data_identity,
            result=self.planner.plan(
                request,
                snapshot.rules,
                snapshot.gender_feasibility,
            ),
        )
