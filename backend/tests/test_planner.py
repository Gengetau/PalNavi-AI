from palnavi.domain.breeding import (
    BreedingRelationship,
    BreedingRoutePlanner,
    InvalidRouteResult,
    OwnedSpeciesInventory,
    RoutePlanningRequest,
    SpeciesId,
    SuccessfulRouteResult,
    UnreachableRouteResult,
)
from palnavi.domain.data import DatasetFound
from palnavi.infrastructure.json_dataset_repository import (
    LocalJsonBreedingDatasetRepository,
    default_dataset_root,
)


def sid(value: str) -> SpeciesId:
    return SpeciesId(value)


def request(target: str, owned: set[str]) -> RoutePlanningRequest:
    return RoutePlanningRequest(
        target=sid(target),
        inventory=OwnedSpeciesInventory.from_ids({sid(value) for value in owned}),
    )


def fixture_relationships() -> tuple[BreedingRelationship, ...]:
    loaded = LocalJsonBreedingDatasetRepository(default_dataset_root()).load("synthetic-v1")
    assert isinstance(loaded, DatasetFound)
    return loaded.snapshot.relationships


def test_direct_route() -> None:
    result = BreedingRoutePlanner().plan(
        request("pal_c", {"pal_a", "pal_b"}), fixture_relationships()
    )

    assert isinstance(result, SuccessfulRouteResult)
    assert [step.child.value for step in result.steps] == ["pal_c"]
    assert result.cost.generations == 1


def test_multi_generation_steps_are_executable_in_order() -> None:
    result = BreedingRoutePlanner().plan(
        request("pal_d", {"pal_a", "pal_b"}), fixture_relationships()
    )

    assert isinstance(result, SuccessfulRouteResult)
    available = {"pal_a", "pal_b"}
    for step in result.steps:
        assert step.parent_a.value in available
        assert step.parent_b.value in available
        available.add(step.child.value)
    assert [step.child.value for step in result.steps] == ["pal_c", "pal_d"]
    assert result.cost.generations == 2


def test_alternate_routes_have_stable_tie_breaking() -> None:
    planner = BreedingRoutePlanner()
    first = planner.plan(request("pal_f", {"pal_a", "pal_b"}), fixture_relationships())
    second = planner.plan(request("pal_f", {"pal_b", "pal_a"}), reversed(fixture_relationships()))

    assert isinstance(first, SuccessfulRouteResult)
    assert isinstance(second, SuccessfulRouteResult)
    assert first == second
    assert [step.child.value for step in first.steps] == ["pal_c", "pal_e", "pal_f"]


def test_cycle_does_not_prevent_unreachable_result() -> None:
    result = BreedingRoutePlanner().plan(
        request("pal_z", {"pal_a", "pal_b"}), fixture_relationships()
    )

    assert isinstance(result, UnreachableRouteResult)
    assert result.target == sid("pal_z")
    assert "pal_f" in {species.value for species in result.reachable_species}


def test_conflicting_unordered_parent_pair_is_invalid() -> None:
    relationships = (
        BreedingRelationship(sid("pal_a"), sid("pal_b"), sid("pal_c")),
        BreedingRelationship(sid("pal_b"), sid("pal_a"), sid("pal_d")),
    )

    result = BreedingRoutePlanner().plan(request("pal_c", {"pal_a", "pal_b"}), relationships)

    assert isinstance(result, InvalidRouteResult)
    assert "conflicting children" in result.errors[0]


def test_invalid_species_identifier_is_rejected() -> None:
    try:
        SpeciesId("Pal A")
    except ValueError as error:
        assert "species identifiers" in str(error)
    else:
        raise AssertionError("invalid identifier was accepted")
