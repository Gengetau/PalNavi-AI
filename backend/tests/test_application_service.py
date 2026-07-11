from collections.abc import Iterable

from palnavi.application import BreedingPlanningService, PlanningFailure
from palnavi.domain.breeding import (
    BreedingRelationship,
    OwnedSpeciesInventory,
    RoutePlanningRequest,
    RouteResult,
    SpeciesId,
)
from palnavi.domain.data import (
    DatasetInvalid,
    DatasetLoadResult,
    DatasetValidationCode,
    DatasetValidationIssue,
)


class StubRepository:
    def __init__(self, result: DatasetLoadResult) -> None:
        self.result = result

    def load(self, dataset_id: str) -> DatasetLoadResult:
        return self.result


class RecordingPlanner:
    def __init__(self) -> None:
        self.calls = 0

    def plan(
        self,
        request: RoutePlanningRequest,
        relationships: Iterable[BreedingRelationship],
    ) -> RouteResult:
        self.calls += 1
        raise AssertionError("invalid data reached the planner")


def request() -> RoutePlanningRequest:
    return RoutePlanningRequest(
        target=SpeciesId("pal_c"),
        inventory=OwnedSpeciesInventory.from_ids({SpeciesId("pal_a"), SpeciesId("pal_b")}),
    )


def test_invalid_dataset_never_reaches_planner() -> None:
    planner = RecordingPlanner()
    service = BreedingPlanningService(
        repository=StubRepository(
            DatasetInvalid(
                dataset_id="synthetic-v1",
                issues=(
                    DatasetValidationIssue(
                        code=DatasetValidationCode.CONTENT_IDENTITY_MISMATCH,
                        field="content_identity.digest",
                        message="content mismatch",
                    ),
                ),
            )
        ),
        planner=planner,
    )

    result = service.plan_from_dataset(request(), "synthetic-v1")

    assert isinstance(result, PlanningFailure)
    assert planner.calls == 0


def test_invalid_explicit_relationships_never_reach_planner() -> None:
    planner = RecordingPlanner()
    service = BreedingPlanningService(
        repository=StubRepository(DatasetInvalid(dataset_id="unused", issues=())),
        planner=planner,
    )
    rows = [
        {"parent_a": "pal_a", "parent_b": "pal_b", "child": "pal_c"},
        {"parent_a": "pal_b", "parent_b": "pal_a", "child": "pal_d"},
    ]

    result = service.plan_from_explicit_relationships(request(), rows)

    assert isinstance(result, PlanningFailure)
    assert planner.calls == 0
