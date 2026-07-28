import pytest

from palnavi.domain.breeding import (
    BreedingParentConstraint,
    BreedingResultKind,
    BreedingRule,
    CaptureAwareRoutePlanner,
    CaptureCandidate,
    CaptureGenderRequiredResult,
    CaptureRoutePlanningRequest,
    CaptureRouteSearchLimitExceeded,
    GenderConstraint,
    InventoryGender,
    OwnedBreedingCandidate,
    SpeciesGenderFeasibility,
    SpeciesId,
    SuccessfulCaptureRouteResult,
    UnreachableCaptureRouteResult,
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


def _profiles(*species: str) -> tuple[SpeciesGenderFeasibility, ...]:
    return tuple(
        SpeciesGenderFeasibility(
            species=SpeciesId(item),
            male_probability=0.5,
            female_probability=0.5,
        )
        for item in species
    )


def _owned(
    instance_id: str,
    species: str,
    gender: InventoryGender,
) -> OwnedBreedingCandidate:
    return OwnedBreedingCandidate(instance_id, SpeciesId(species), gender)


def _candidate(
    candidate_id: str,
    species: str,
    gender: InventoryGender,
) -> CaptureCandidate:
    return CaptureCandidate(candidate_id, SpeciesId(species), gender)


def _request(
    target: str,
    gender: InventoryGender,
    *,
    inventory: tuple[OwnedBreedingCandidate, ...] = (),
    candidates: tuple[CaptureCandidate, ...] = (),
) -> CaptureRoutePlanningRequest:
    return CaptureRoutePlanningRequest(
        target_species=SpeciesId(target),
        target_gender=gender,
        inventory=inventory,
        capture_candidates=candidates,
    )


def test_direct_target_capture_is_ranked_before_breeding() -> None:
    request = _request(
        "target",
        InventoryGender.FEMALE,
        candidates=(
            _candidate("pal-a-capture", "pal_a", InventoryGender.MALE),
            _candidate("pal-b-capture", "pal_b", InventoryGender.FEMALE),
            _candidate("target-capture", "target", InventoryGender.FEMALE),
        ),
    )

    result = CaptureAwareRoutePlanner().plan(
        request,
        (_rule("pal_a", "pal_b", "target", source_hash="1" * 64),),
        _profiles("pal_a", "pal_b", "target"),
    )

    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.steps == ()
    assert result.cost.new_capture_count == 1
    assert result.cost.generations == 0
    assert result.cost.breeding_steps == 0
    assert result.capture_requirements == (result.capture_requirements[0],)
    assert result.capture_requirements[0].candidate_id == "target-capture"


def test_one_capture_route_outranks_shorter_two_capture_route() -> None:
    rules = (
        _rule("one", "owned_x", "middle", source_hash="1" * 64),
        _rule("middle", "owned_y", "target", source_hash="2" * 64),
        _rule("two_a", "two_b", "target", source_hash="3" * 64),
    )
    result = CaptureAwareRoutePlanner().plan(
        _request(
            "target",
            InventoryGender.MALE,
            inventory=(
                _owned("x", "owned_x", InventoryGender.FEMALE),
                _owned("y", "owned_y", InventoryGender.FEMALE),
            ),
            candidates=(
                _candidate("capture-one", "one", InventoryGender.MALE),
                _candidate("capture-two-a", "two_a", InventoryGender.MALE),
                _candidate("capture-two-b", "two_b", InventoryGender.FEMALE),
            ),
        ),
        rules,
        _profiles("one", "owned_x", "middle", "owned_y", "two_a", "two_b", "target"),
    )

    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.cost.new_capture_count == 1
    assert result.cost.generations == 2
    assert [item.candidate_id for item in result.capture_requirements] == ["capture-one"]
    assert [step.child.species.value for step in result.steps] == ["middle", "target"]


def test_equal_cardinality_labels_survive_for_later_capture_overlap() -> None:
    rules = (
        _rule("capture_a", "owned_x", "shared_parent", source_hash="1" * 64),
        _rule("capture_b", "owned_y", "shared_parent", source_hash="2" * 64),
        _rule("capture_b", "owned_z", "other_parent", source_hash="3" * 64),
        _rule("shared_parent", "other_parent", "target", source_hash="4" * 64),
    )
    result = CaptureAwareRoutePlanner().plan(
        _request(
            "target",
            InventoryGender.MALE,
            inventory=(
                _owned("x", "owned_x", InventoryGender.FEMALE),
                _owned("y", "owned_y", InventoryGender.FEMALE),
                _owned("z", "owned_z", InventoryGender.FEMALE),
            ),
            candidates=(
                _candidate("a", "capture_a", InventoryGender.MALE),
                _candidate("b", "capture_b", InventoryGender.MALE),
            ),
        ),
        rules,
        _profiles(
            "capture_a",
            "capture_b",
            "owned_x",
            "owned_y",
            "owned_z",
            "shared_parent",
            "other_parent",
            "target",
        ),
    )

    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.cost.new_capture_count == 1
    assert [item.candidate_id for item in result.capture_requirements] == ["b"]
    assert {step.child.species.value for step in result.steps} == {
        "shared_parent",
        "other_parent",
        "target",
    }


def test_shallower_longer_label_does_not_prune_deeper_shorter_route() -> None:
    rules = (
        # A shallow seven-step tree to the shared state.
        _rule("capture", "shallow_owned_1", "shallow_1", source_hash=f"{1:064x}"),
        _rule(
            "shallow_owned_2",
            "shallow_owned_3",
            "shallow_2",
            source_hash=f"{2:064x}",
        ),
        _rule(
            "shallow_owned_4",
            "shallow_owned_5",
            "shallow_3",
            source_hash=f"{3:064x}",
        ),
        _rule(
            "shallow_owned_6",
            "shallow_owned_7",
            "shallow_4",
            source_hash=f"{4:064x}",
        ),
        _rule("shallow_1", "shallow_2", "shallow_5", source_hash=f"{5:064x}"),
        _rule("shallow_3", "shallow_4", "shallow_6", source_hash=f"{6:064x}"),
        _rule(
            "shallow_5",
            "shallow_6",
            "shared",
            source_hash=f"{7:064x}",
        ),
        # A deeper four-step chain to the same shared state and capture set.
        _rule("capture", "deep_owned_1", "deep_1", source_hash=f"{8:064x}"),
        _rule("deep_1", "deep_owned_2", "deep_2", source_hash=f"{9:064x}"),
        _rule("deep_2", "deep_owned_3", "deep_3", source_hash=f"{10:064x}"),
        _rule("deep_3", "deep_owned_4", "shared", source_hash=f"{11:064x}"),
        # A five-generation other parent equalizes the final target generation.
        _rule("other_owned_1", "other_owned_2", "other_1", source_hash=f"{12:064x}"),
        _rule("other_1", "other_owned_3", "other_2", source_hash=f"{13:064x}"),
        _rule("other_2", "other_owned_4", "other_3", source_hash=f"{14:064x}"),
        _rule("other_3", "other_owned_5", "other_4", source_hash=f"{15:064x}"),
        _rule("other_4", "other_owned_6", "other", source_hash=f"{16:064x}"),
        _rule("shared", "other", "target", source_hash=f"{17:064x}"),
    )
    owned_species = (
        *(f"shallow_owned_{index}" for index in range(1, 8)),
        *(f"deep_owned_{index}" for index in range(1, 5)),
        *(f"other_owned_{index}" for index in range(1, 7)),
    )
    produced_species = (
        *(f"shallow_{index}" for index in range(1, 7)),
        *(f"deep_{index}" for index in range(1, 4)),
        *(f"other_{index}" for index in range(1, 5)),
        "shared",
        "other",
        "target",
    )
    male_owned_species = {
        "shallow_owned_2",
        "shallow_owned_4",
        "shallow_owned_6",
        "other_owned_1",
    }
    inventory = tuple(
        _owned(
            f"owned-{species}",
            species,
            (InventoryGender.MALE if species in male_owned_species else InventoryGender.FEMALE),
        )
        for species in owned_species
    )
    request = _request(
        "target",
        InventoryGender.MALE,
        inventory=inventory,
        candidates=(_candidate("capture-one", "capture", InventoryGender.MALE),),
    )

    planner = CaptureAwareRoutePlanner()
    baseline = planner.plan(
        request,
        rules[7:],
        _profiles("capture", *owned_species, *produced_species),
    )
    result = planner.plan(
        request,
        rules,
        _profiles("capture", *owned_species, *produced_species),
    )

    assert isinstance(baseline, SuccessfulCaptureRouteResult)
    assert baseline.cost.new_capture_count == 1
    assert baseline.cost.generations == 6
    assert baseline.cost.breeding_steps == 10
    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.cost == baseline.cost
    assert not any(step.child.species.value.startswith("shallow_") for step in result.steps)


def test_shallower_equal_step_label_does_not_prune_smaller_deep_signature() -> None:
    deep_rules = (
        _rule(
            "capture",
            "deep_owned_1",
            "deep_1",
            source_hash=f"{1:064x}",
        ),
        _rule(
            "deep_1",
            "deep_owned_2",
            "deep_2",
            source_hash=f"{2:064x}",
        ),
        _rule(
            "deep_2",
            "deep_owned_3",
            "shared",
            source_hash=f"{3:064x}",
        ),
    )
    shallow_rules = (
        _rule(
            "capture",
            "shallow_owned_1",
            "shallow_1",
            source_hash=f"{4:064x}",
        ),
        _rule(
            "shallow_owned_2",
            "shallow_owned_3",
            "shallow_2",
            source_hash=f"{5:064x}",
        ),
        _rule(
            "shallow_1",
            "shallow_2",
            "shared",
            source_hash=f"{6:064x}",
        ),
    )
    equalizing_rules = (
        _rule(
            "other_owned_1",
            "other_owned_2",
            "other_1",
            source_hash=f"{7:064x}",
        ),
        _rule(
            "other_1",
            "other_owned_3",
            "other_2",
            source_hash=f"{8:064x}",
        ),
        _rule(
            "other_2",
            "other_owned_4",
            "other",
            source_hash=f"{9:064x}",
        ),
        _rule(
            "shared",
            "other",
            "target",
            source_hash=f"{10:064x}",
        ),
    )
    inventory = (
        _owned("deep-owned-1", "deep_owned_1", InventoryGender.FEMALE),
        _owned("deep-owned-2", "deep_owned_2", InventoryGender.FEMALE),
        _owned("deep-owned-3", "deep_owned_3", InventoryGender.FEMALE),
        _owned("shallow-owned-1", "shallow_owned_1", InventoryGender.FEMALE),
        _owned("shallow-owned-2", "shallow_owned_2", InventoryGender.MALE),
        _owned("shallow-owned-3", "shallow_owned_3", InventoryGender.FEMALE),
        _owned("other-owned-1", "other_owned_1", InventoryGender.MALE),
        _owned("other-owned-2", "other_owned_2", InventoryGender.FEMALE),
        _owned("other-owned-3", "other_owned_3", InventoryGender.FEMALE),
        _owned("other-owned-4", "other_owned_4", InventoryGender.FEMALE),
    )
    species = (
        "capture",
        "deep_owned_1",
        "deep_owned_2",
        "deep_owned_3",
        "deep_1",
        "deep_2",
        "shallow_owned_1",
        "shallow_owned_2",
        "shallow_owned_3",
        "shallow_1",
        "shallow_2",
        "other_owned_1",
        "other_owned_2",
        "other_owned_3",
        "other_owned_4",
        "other_1",
        "other_2",
        "shared",
        "other",
        "target",
    )
    request = _request(
        "target",
        InventoryGender.MALE,
        inventory=inventory,
        candidates=(_candidate("capture-one", "capture", InventoryGender.MALE),),
    )

    planner = CaptureAwareRoutePlanner()
    baseline = planner.plan(
        request,
        (*deep_rules, *equalizing_rules),
        _profiles(*species),
    )
    result = planner.plan(
        request,
        (*shallow_rules, *deep_rules, *equalizing_rules),
        _profiles(*species),
    )

    assert isinstance(baseline, SuccessfulCaptureRouteResult)
    assert baseline.cost.new_capture_count == 1
    assert baseline.cost.generations == 4
    assert baseline.cost.breeding_steps == 7
    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.cost == baseline.cost
    assert result.steps == baseline.steps
    assert not any(step.child.species.value.startswith("shallow_") for step in result.steps)


def test_target_frontier_continues_after_captures_become_produced_states() -> None:
    rules = (
        _rule("w", "ox", "x", source_hash=f"{1:064x}"),
        _rule("w", "oz", "z", source_hash=f"{2:064x}"),
        _rule("z", "oa", "h1", source_hash=f"{3:064x}"),
        _rule("x", "ob", "h2", source_hash=f"{4:064x}"),
        _rule("x", "h1", "a", source_hash=f"{5:064x}"),
        _rule("z", "h2", "b", source_hash=f"{6:064x}"),
        _rule("a", "b", "target", source_hash=f"{7:064x}"),
    )
    result = CaptureAwareRoutePlanner().plan(
        _request(
            "target",
            InventoryGender.MALE,
            inventory=(
                _owned("owned-ox", "ox", InventoryGender.FEMALE),
                _owned("owned-oz", "oz", InventoryGender.FEMALE),
                _owned("owned-oa", "oa", InventoryGender.FEMALE),
                _owned("owned-ob", "ob", InventoryGender.FEMALE),
            ),
            candidates=(
                _candidate("w", "w", InventoryGender.MALE),
                _candidate("x", "x", InventoryGender.MALE),
                _candidate("z", "z", InventoryGender.MALE),
            ),
        ),
        rules,
        _profiles("w", "x", "z", "ox", "oz", "oa", "ob", "h1", "h2", "a", "b", "target"),
    )

    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.cost.new_capture_count == 1
    assert result.cost.generations == 4
    assert result.cost.breeding_steps == 7
    assert [item.candidate_id for item in result.capture_requirements] == ["w"]
    assert sum(step.child.species.value == "x" for step in result.steps) == 1
    assert sum(step.child.species.value == "z" for step in result.steps) == 1


def test_zero_candidates_matches_owned_only_reachability_for_production_route() -> None:
    loaded = LocalPalworldBreedingDatasetRepository(default_palworld_dataset_root()).load(
        PALWORLD_DATASET_ID
    )
    assert isinstance(loaded, GenderAwareDatasetFound)
    request = _request(
        "wixen_noct",
        InventoryGender.FEMALE,
        inventory=(
            _owned("dumud-1", "dumud", InventoryGender.MALE),
            _owned("katress-ignis-1", "katress_ignis", InventoryGender.FEMALE),
            _owned("wixen-1", "wixen", InventoryGender.FEMALE),
        ),
    )

    result = CaptureAwareRoutePlanner().plan(
        request,
        loaded.snapshot.rules,
        loaded.snapshot.gender_feasibility,
    )

    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.cost.new_capture_count == 0
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


def test_one_explicit_candidate_unlocks_a_production_directed_route() -> None:
    loaded = LocalPalworldBreedingDatasetRepository(default_palworld_dataset_root()).load(
        PALWORLD_DATASET_ID
    )
    assert isinstance(loaded, GenderAwareDatasetFound)

    result = CaptureAwareRoutePlanner().plan(
        _request(
            "wixen_noct",
            InventoryGender.FEMALE,
            inventory=(
                _owned("katress-ignis-1", "katress_ignis", InventoryGender.FEMALE),
                _owned("wixen-1", "wixen", InventoryGender.FEMALE),
            ),
            candidates=(_candidate("capture-dumud", "dumud", InventoryGender.MALE),),
        ),
        loaded.snapshot.rules,
        loaded.snapshot.gender_feasibility,
    )

    assert isinstance(result, SuccessfulCaptureRouteResult)
    assert result.cost.new_capture_count == 1
    assert result.cost.generations == 2
    assert [item.candidate_id for item in result.capture_requirements] == ["capture-dumud"]
    assert [step.child.species.value for step in result.steps] == [
        "katress",
        "wixen_noct",
    ]


def test_unknown_owned_gender_returns_machine_readable_result() -> None:
    result = CaptureAwareRoutePlanner().plan(
        _request(
            "target",
            InventoryGender.FEMALE,
            inventory=(_owned("unknown-1", "pal_a", InventoryGender.UNKNOWN),),
            candidates=(_candidate("candidate", "target", InventoryGender.FEMALE),),
        ),
        (),
        _profiles("pal_a", "target"),
    )

    assert isinstance(result, CaptureGenderRequiredResult)
    assert result.unknown_instance_ids == ("unknown-1",)


def test_unreachable_result_is_deterministic() -> None:
    request = _request(
        "target",
        InventoryGender.FEMALE,
        inventory=(_owned("owned", "pal_a", InventoryGender.MALE),),
    )
    planner = CaptureAwareRoutePlanner()

    first = planner.plan(request, (), _profiles("pal_a", "target"))
    second = planner.plan(request, (), _profiles("pal_a", "target"))

    assert isinstance(first, UnreachableCaptureRouteResult)
    assert first == second
    assert {(state.species.value, state.gender.value) for state in first.reachable_states} == {
        ("pal_a", "male")
    }


def test_search_limit_exceeded_fails_closed() -> None:
    result = CaptureAwareRoutePlanner(max_total_labels=1).plan(
        _request(
            "target",
            InventoryGender.FEMALE,
            inventory=(_owned("owned", "pal_a", InventoryGender.MALE),),
            candidates=(_candidate("candidate", "pal_b", InventoryGender.FEMALE),),
        ),
        (),
        _profiles("pal_a", "pal_b", "target"),
    )

    assert isinstance(result, CaptureRouteSearchLimitExceeded)
    assert "label bound" in result.reason


@pytest.mark.parametrize(
    ("inventory", "candidates", "message"),
    [
        (
            (),
            (
                _candidate("same", "pal_a", InventoryGender.MALE),
                _candidate("same", "pal_b", InventoryGender.FEMALE),
            ),
            "duplicate candidate",
        ),
        (
            (),
            (
                _candidate("one", "pal_a", InventoryGender.MALE),
                _candidate("two", "pal_a", InventoryGender.MALE),
            ),
            "duplicate species",
        ),
        (
            (_owned("collision", "pal_a", InventoryGender.MALE),),
            (_candidate("collision", "pal_b", InventoryGender.FEMALE),),
            "collide",
        ),
    ],
)
def test_request_rejects_duplicate_or_colliding_candidates(
    inventory: tuple[OwnedBreedingCandidate, ...],
    candidates: tuple[CaptureCandidate, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _request(
            "target",
            InventoryGender.FEMALE,
            inventory=inventory,
            candidates=candidates,
        )


def test_candidate_rejects_unknown_gender() -> None:
    with pytest.raises(ValueError, match="concrete"):
        _candidate("candidate", "pal_a", InventoryGender.UNKNOWN)


def test_request_rejects_more_than_sixteen_candidates() -> None:
    candidates = tuple(
        _candidate(f"candidate-{index}", f"pal_{index}", InventoryGender.MALE)
        for index in range(17)
    )
    with pytest.raises(ValueError, match="sixteen"):
        _request(
            "target",
            InventoryGender.FEMALE,
            candidates=candidates,
        )
