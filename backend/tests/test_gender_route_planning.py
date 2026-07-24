import pytest

from palnavi.domain.breeding import (
    BreedingParentConstraint,
    BreedingResultKind,
    BreedingRule,
    GenderAwareRoutePlanner,
    GenderConstraint,
    GenderRequiredRouteResult,
    GenderRoutePlanningRequest,
    InventoryGender,
    OwnedBreedingCandidate,
    SpeciesGenderFeasibility,
    SpeciesId,
    SuccessfulGenderRouteResult,
    UnreachableGenderRouteResult,
)
from palnavi.domain.data import GenderAwareDatasetFound
from palnavi.infrastructure.palworld_dataset_repository import (
    PALWORLD_DATASET_ID,
    LocalPalworldBreedingDatasetRepository,
    default_palworld_dataset_root,
)


def _rule(
    parent_a: str,
    parent_b: str,
    child: str,
    *,
    source_hash: str,
    kind: BreedingResultKind = BreedingResultKind.ORDINARY_POWER,
    gender_a: GenderConstraint = GenderConstraint.WILDCARD,
    gender_b: GenderConstraint = GenderConstraint.WILDCARD,
) -> BreedingRule:
    return BreedingRule(
        source_dataset_id="test-dataset",
        source_record_hash=source_hash,
        parent_a=BreedingParentConstraint(SpeciesId(parent_a), gender_a),
        parent_b=BreedingParentConstraint(SpeciesId(parent_b), gender_b),
        child=SpeciesId(child),
        result_kind=kind,
    )


@pytest.fixture
def small_graph() -> tuple[tuple[BreedingRule, ...], tuple[SpeciesGenderFeasibility, ...]]:
    rules = (
        _rule("pal_a", "pal_b", "pal_c", source_hash="1" * 64),
        _rule(
            "pal_c",
            "pal_d",
            "pal_e",
            source_hash="2" * 64,
            kind=BreedingResultKind.GENDER_DIRECTED,
            gender_a=GenderConstraint.MALE,
            gender_b=GenderConstraint.FEMALE,
        ),
        _rule(
            "pal_c",
            "pal_d",
            "pal_f",
            source_hash="3" * 64,
            kind=BreedingResultKind.GENDER_DIRECTED,
            gender_a=GenderConstraint.FEMALE,
            gender_b=GenderConstraint.MALE,
        ),
    )
    profiles = tuple(
        SpeciesGenderFeasibility(
            species=SpeciesId(species),
            male_probability=0.5,
            female_probability=0.5,
        )
        for species in ("pal_a", "pal_b", "pal_c", "pal_d", "pal_e", "pal_f")
    )
    return rules, profiles


def _request(
    target: str,
    target_gender: InventoryGender,
    *inventory: tuple[str, str, InventoryGender],
) -> GenderRoutePlanningRequest:
    return GenderRoutePlanningRequest(
        target_species=SpeciesId(target),
        target_gender=target_gender,
        inventory=tuple(
            OwnedBreedingCandidate(
                instance_id=instance_id,
                species=SpeciesId(species),
                gender=gender,
            )
            for instance_id, species, gender in inventory
        ),
    )


def test_two_generation_route_preserves_gender_state_and_directed_step(
    small_graph: tuple[tuple[BreedingRule, ...], tuple[SpeciesGenderFeasibility, ...]],
) -> None:
    rules, profiles = small_graph
    request = _request(
        "pal_e",
        InventoryGender.FEMALE,
        ("a-1", "pal_a", InventoryGender.MALE),
        ("b-1", "pal_b", InventoryGender.FEMALE),
        ("d-1", "pal_d", InventoryGender.FEMALE),
    )

    result = GenderAwareRoutePlanner().plan(request, rules, profiles)

    assert isinstance(result, SuccessfulGenderRouteResult)
    assert result.target.species == SpeciesId("pal_e")
    assert result.target.gender is InventoryGender.FEMALE
    assert result.cost.generations == 2
    assert result.cost.breeding_steps == 2
    assert result.cost.probability_dependent_cost_available is False
    assert result.cost.expected_attempts is None
    assert [
        (
            step.generation,
            step.parent_a.species.value,
            step.parent_a.gender.value,
            step.parent_b.species.value,
            step.parent_b.gender.value,
            step.child.species.value,
            step.child.gender.value,
            step.result_kind.value,
        )
        for step in result.steps
    ] == [
        (1, "pal_a", "male", "pal_b", "female", "pal_c", "male", "ordinary_power"),
        (2, "pal_c", "male", "pal_d", "female", "pal_e", "female", "gender_directed"),
    ]
    assert all(not step.child.required_passive_set for step in result.steps)
    assert all(not step.child.required_iv_constraints for step in result.steps)
    assert GenderAwareRoutePlanner().plan(request, rules, profiles) == result


def test_unknown_inventory_returns_gender_required_before_matching(
    small_graph: tuple[tuple[BreedingRule, ...], tuple[SpeciesGenderFeasibility, ...]],
) -> None:
    rules, profiles = small_graph
    result = GenderAwareRoutePlanner().plan(
        _request(
            "pal_c",
            InventoryGender.MALE,
            ("b-2", "pal_b", InventoryGender.UNKNOWN),
            ("a-2", "pal_a", InventoryGender.MALE),
        ),
        rules,
        profiles,
    )

    assert isinstance(result, GenderRequiredRouteResult)
    assert result.unknown_instance_ids == ("b-2",)


def test_same_gender_only_inventory_is_unreachable(
    small_graph: tuple[tuple[BreedingRule, ...], tuple[SpeciesGenderFeasibility, ...]],
) -> None:
    rules, profiles = small_graph
    result = GenderAwareRoutePlanner().plan(
        _request(
            "pal_c",
            InventoryGender.MALE,
            ("a-3", "pal_a", InventoryGender.MALE),
            ("b-3", "pal_b", InventoryGender.MALE),
        ),
        rules,
        profiles,
    )

    assert isinstance(result, UnreachableGenderRouteResult)
    assert {(item.species.value, item.gender.value) for item in result.reachable_states} == {
        ("pal_a", "male"),
        ("pal_b", "male"),
    }


def test_duplicate_instance_ids_are_invalid() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _request(
            "pal_c",
            InventoryGender.MALE,
            ("duplicate", "pal_a", InventoryGender.MALE),
            ("duplicate", "pal_b", InventoryGender.FEMALE),
        )


def test_production_route_uses_directed_rule_after_an_ordinary_step() -> None:
    loaded = LocalPalworldBreedingDatasetRepository(default_palworld_dataset_root()).load(
        PALWORLD_DATASET_ID
    )
    assert isinstance(loaded, GenderAwareDatasetFound)

    result = GenderAwareRoutePlanner().plan(
        _request(
            "wixen_noct",
            InventoryGender.FEMALE,
            ("dumud-1", "dumud", InventoryGender.MALE),
            ("katress-ignis-1", "katress_ignis", InventoryGender.FEMALE),
            ("wixen-1", "wixen", InventoryGender.FEMALE),
        ),
        loaded.snapshot.rules,
        loaded.snapshot.gender_feasibility,
    )

    assert isinstance(result, SuccessfulGenderRouteResult)
    assert result.cost.generations == 2
    assert [
        (
            step.parent_a.species.value,
            step.parent_a.gender.value,
            step.parent_b.species.value,
            step.parent_b.gender.value,
            step.child.species.value,
            step.result_kind.value,
        )
        for step in result.steps
    ] == [
        (
            "dumud",
            "male",
            "katress_ignis",
            "female",
            "katress",
            "ordinary_power",
        ),
        (
            "katress",
            "male",
            "wixen",
            "female",
            "wixen_noct",
            "gender_directed",
        ),
    ]


def test_every_non_directed_production_rule_expands_symmetrically() -> None:
    loaded = LocalPalworldBreedingDatasetRepository(default_palworld_dataset_root()).load(
        PALWORLD_DATASET_ID
    )
    assert isinstance(loaded, GenderAwareDatasetFound)
    planner = GenderAwareRoutePlanner()
    profiles = {item.species: item for item in loaded.snapshot.gender_feasibility}

    transitions = planner._build_transitions(loaded.snapshot.rules, profiles)
    by_source: dict[str, set[tuple[str, str, str, str, str, str]]] = {}
    for transition in transitions:
        by_source.setdefault(transition.rule.source_record_hash, set()).add(
            (
                transition.parent_a[0].value,
                transition.parent_a[1].value,
                transition.parent_b[0].value,
                transition.parent_b[1].value,
                transition.child[0].value,
                transition.child[1].value,
            )
        )

    checked = 0
    for rule in loaded.snapshot.rules:
        if rule.result_kind is BreedingResultKind.GENDER_DIRECTED:
            continue
        expanded = by_source[rule.source_record_hash]
        assert len(expanded) == 4
        assert {
            (parent_a_gender, parent_b_gender)
            for _, parent_a_gender, _, parent_b_gender, _, _ in expanded
        } == {("male", "female"), ("female", "male")}
        assert {child for *_, child, _ in expanded} == {rule.child.value}
        assert {child_gender for *_, child_gender in expanded} == {"male", "female"}
        checked += 1

    assert checked == 44_849
