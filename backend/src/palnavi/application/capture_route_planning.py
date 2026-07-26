"""Application service for production-backed capture-ranked route planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from palnavi.domain.breeding import (
    CaptureAwareRoutePlanner,
    CaptureRoutePlanningRequest,
    CaptureRouteResult,
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
class CaptureRoutePlanningSuccess:
    dataset_id: str
    content_identity: ContentIdentity
    gender_data_identity: ContentIdentity
    result: CaptureRouteResult


class CaptureRoutePlanningFailureKind(StrEnum):
    DATASET_NOT_FOUND = "dataset_not_found"
    DATASET_INVALID = "dataset_invalid"


@dataclass(frozen=True, slots=True)
class CaptureRoutePlanningFailure:
    kind: CaptureRoutePlanningFailureKind
    dataset_id: str
    issues: tuple[DatasetValidationIssue, ...]


CaptureRoutePlanningOutcome = CaptureRoutePlanningSuccess | CaptureRoutePlanningFailure


@dataclass(frozen=True, slots=True)
class CaptureRoutePlanningService:
    repository: GenderAwareBreedingDatasetRepository
    planner: CaptureAwareRoutePlanner

    def plan(
        self,
        dataset_id: str,
        request: CaptureRoutePlanningRequest,
    ) -> CaptureRoutePlanningOutcome:
        loaded = self.repository.load(dataset_id)
        if isinstance(loaded, DatasetNotFound):
            return CaptureRoutePlanningFailure(
                kind=CaptureRoutePlanningFailureKind.DATASET_NOT_FOUND,
                dataset_id=dataset_id,
                issues=(),
            )
        if isinstance(loaded, DatasetInvalid):
            return CaptureRoutePlanningFailure(
                kind=CaptureRoutePlanningFailureKind.DATASET_INVALID,
                dataset_id=dataset_id,
                issues=loaded.issues,
            )
        if not isinstance(loaded, GenderAwareDatasetFound):
            raise AssertionError("repository returned an unsupported result type")

        snapshot = loaded.snapshot
        return CaptureRoutePlanningSuccess(
            dataset_id=snapshot.dataset_id,
            content_identity=snapshot.content_identity,
            gender_data_identity=snapshot.gender_data_identity,
            result=self.planner.plan(
                request,
                snapshot.rules,
                snapshot.gender_feasibility,
            ),
        )
