"""Application service joining validated data repositories to the domain planner."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from palnavi.domain.breeding import (
    BreedingRelationship,
    RoutePlanningRequest,
    RouteResult,
)
from palnavi.domain.data import (
    BreedingDatasetRepository,
    BreedingDatasetSnapshot,
    DatasetFound,
    DatasetInvalid,
    DatasetNotFound,
    DatasetValidationIssue,
    validate_relationship_rows,
)


@dataclass(frozen=True, slots=True)
class PlanningSuccess:
    route_result: RouteResult
    dataset: BreedingDatasetSnapshot | None


class PlanningFailureKind(StrEnum):
    DATASET_NOT_FOUND = "dataset_not_found"
    DATASET_INVALID = "dataset_invalid"
    RELATIONSHIPS_INVALID = "relationships_invalid"


@dataclass(frozen=True, slots=True)
class PlanningFailure:
    kind: PlanningFailureKind
    data_source: str
    issues: tuple[DatasetValidationIssue, ...]


PlanningOutcome = PlanningSuccess | PlanningFailure


class RoutePlanner(Protocol):
    def plan(
        self,
        request: RoutePlanningRequest,
        relationships: Iterable[BreedingRelationship],
    ) -> RouteResult: ...


@dataclass(frozen=True, slots=True)
class BreedingPlanningService:
    repository: BreedingDatasetRepository
    planner: RoutePlanner

    def plan_from_dataset(
        self,
        request: RoutePlanningRequest,
        dataset_id: str,
    ) -> PlanningOutcome:
        loaded = self.repository.load(dataset_id)
        if isinstance(loaded, DatasetNotFound):
            return PlanningFailure(
                kind=PlanningFailureKind.DATASET_NOT_FOUND,
                data_source=dataset_id,
                issues=(),
            )
        if isinstance(loaded, DatasetInvalid):
            return PlanningFailure(
                kind=PlanningFailureKind.DATASET_INVALID,
                data_source=dataset_id,
                issues=loaded.issues,
            )
        if not isinstance(loaded, DatasetFound):
            raise AssertionError("repository returned an unsupported result type")
        return PlanningSuccess(
            route_result=self.planner.plan(request, loaded.snapshot.relationships),
            dataset=loaded.snapshot,
        )

    def plan_from_explicit_relationships(
        self,
        request: RoutePlanningRequest,
        relationship_rows: object,
    ) -> PlanningOutcome:
        relationships, issues = validate_relationship_rows(relationship_rows)
        if issues:
            return PlanningFailure(
                kind=PlanningFailureKind.RELATIONSHIPS_INVALID,
                data_source="explicit-request",
                issues=issues,
            )
        return PlanningSuccess(
            route_result=self.planner.plan(request, relationships),
            dataset=None,
        )
