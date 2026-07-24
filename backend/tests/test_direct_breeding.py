import pytest

from palnavi.domain.breeding import (
    BreedingParentConstraint,
    BreedingResultKind,
    BreedingRule,
    DirectBreedingGenderRequired,
    DirectBreedingInvalid,
    DirectBreedingNotFound,
    DirectBreedingRequest,
    DirectBreedingSuccess,
    GenderAwareDirectBreedingIndex,
    GenderConstraint,
    InventoryGender,
    SpeciesId,
)
from palnavi.domain.data import GenderAwareDatasetFound
from palnavi.infrastructure.palworld_dataset_repository import (
    PALWORLD_DATASET_ID,
    LocalPalworldBreedingDatasetRepository,
    default_palworld_dataset_root,
)


@pytest.fixture(scope="module")
def production_rules() -> tuple[BreedingRule, ...]:
    loaded = LocalPalworldBreedingDatasetRepository(default_palworld_dataset_root()).load(
        PALWORLD_DATASET_ID
    )
    assert isinstance(loaded, GenderAwareDatasetFound)
    return loaded.snapshot.rules


def _request(
    parent_a: str,
    parent_b: str,
    parent_a_gender: InventoryGender | None = None,
    parent_b_gender: InventoryGender | None = None,
) -> DirectBreedingRequest:
    return DirectBreedingRequest(
        parent_a=SpeciesId(parent_a),
        parent_b=SpeciesId(parent_b),
        parent_a_gender=parent_a_gender,
        parent_b_gender=parent_b_gender,
    )


def _rule(
    parent_a: str,
    parent_b: str,
    child: str,
    *,
    result_kind: BreedingResultKind = BreedingResultKind.ORDINARY_POWER,
    parent_a_gender: GenderConstraint = GenderConstraint.WILDCARD,
    parent_b_gender: GenderConstraint = GenderConstraint.WILDCARD,
    source_hash: str = "0" * 64,
) -> BreedingRule:
    return BreedingRule(
        source_dataset_id="dataset",
        source_record_hash=source_hash,
        parent_a=BreedingParentConstraint(SpeciesId(parent_a), parent_a_gender),
        parent_b=BreedingParentConstraint(SpeciesId(parent_b), parent_b_gender),
        child=SpeciesId(child),
        result_kind=result_kind,
    )


def test_all_non_directed_rules_preserve_child_and_parent_order_parity(
    production_rules: tuple[BreedingRule, ...],
) -> None:
    index = GenderAwareDirectBreedingIndex(production_rules)
    checked = 0

    for rule in production_rules:
        if rule.result_kind is BreedingResultKind.GENDER_DIRECTED:
            continue
        for request in (
            _request(rule.parent_a.species.value, rule.parent_b.species.value),
            _request(rule.parent_b.species.value, rule.parent_a.species.value),
            _request(
                rule.parent_a.species.value,
                rule.parent_b.species.value,
                InventoryGender.MALE,
                InventoryGender.FEMALE,
            ),
            _request(
                rule.parent_b.species.value,
                rule.parent_a.species.value,
                InventoryGender.FEMALE,
                InventoryGender.MALE,
            ),
        ):
            result = index.query(request)
            assert isinstance(result, DirectBreedingSuccess)
            assert result.child == rule.child
            assert result.result_kind == rule.result_kind
            assert result.source_record_hash == rule.source_record_hash
        checked += 1

    assert checked == 44_849
    assert index.wildcard_rule_count == 44_849
    assert index.directed_rule_count == 2


@pytest.mark.parametrize(
    ("parent_a", "gender_a", "parent_b", "gender_b", "expected_child"),
    [
        ("katress", "male", "wixen", "female", "wixen_noct"),
        ("katress", "female", "wixen", "male", "katress_ignis"),
        ("wixen", "female", "katress", "male", "wixen_noct"),
        ("wixen", "male", "katress", "female", "katress_ignis"),
    ],
)
def test_gender_directed_rules_preserve_species_gender_association(
    production_rules: tuple[BreedingRule, ...],
    parent_a: str,
    gender_a: str,
    parent_b: str,
    gender_b: str,
    expected_child: str,
) -> None:
    result = GenderAwareDirectBreedingIndex(production_rules).query(
        _request(
            parent_a,
            parent_b,
            InventoryGender(gender_a),
            InventoryGender(gender_b),
        )
    )
    assert isinstance(result, DirectBreedingSuccess)
    assert result.child == SpeciesId(expected_child)
    assert result.result_kind is BreedingResultKind.GENDER_DIRECTED


def test_species_only_directed_query_returns_both_stable_possibilities(
    production_rules: tuple[BreedingRule, ...],
) -> None:
    index = GenderAwareDirectBreedingIndex(production_rules)

    result = index.query(_request("katress", "wixen"))
    reversed_result = index.query(_request("wixen", "katress"))

    assert isinstance(result, DirectBreedingGenderRequired)
    assert [
        (item.parent_a_gender.value, item.parent_b_gender.value, item.child.value)
        for item in result.possible_results
    ] == [
        ("male", "female", "wixen_noct"),
        ("female", "male", "katress_ignis"),
    ]
    assert isinstance(reversed_result, DirectBreedingGenderRequired)
    assert [
        (item.parent_a_gender.value, item.parent_b_gender.value, item.child.value)
        for item in reversed_result.possible_results
    ] == [
        ("male", "female", "katress_ignis"),
        ("female", "male", "wixen_noct"),
    ]


def test_unknown_gender_requires_concrete_opposite_genders(
    production_rules: tuple[BreedingRule, ...],
) -> None:
    index = GenderAwareDirectBreedingIndex(production_rules)

    directed = index.query(
        _request(
            "katress",
            "wixen",
            InventoryGender.UNKNOWN,
            InventoryGender.FEMALE,
        )
    )
    ordinary = index.query(
        _request(
            "anubis",
            "lamball",
            InventoryGender.MALE,
            InventoryGender.UNKNOWN,
        )
    )

    assert isinstance(directed, DirectBreedingGenderRequired)
    assert len(directed.possible_results) == 2
    assert isinstance(ordinary, DirectBreedingGenderRequired)
    assert len(ordinary.possible_results) == 2
    assert {item.child for item in ordinary.possible_results}


@pytest.mark.parametrize("gender", [InventoryGender.MALE, InventoryGender.FEMALE])
def test_same_gender_concrete_parents_are_invalid(
    production_rules: tuple[BreedingRule, ...],
    gender: InventoryGender,
) -> None:
    result = GenderAwareDirectBreedingIndex(production_rules).query(
        _request("katress", "wixen", gender, gender)
    )
    assert isinstance(result, DirectBreedingInvalid)


def test_partial_species_only_shape_is_invalid(
    production_rules: tuple[BreedingRule, ...],
) -> None:
    result = GenderAwareDirectBreedingIndex(production_rules).query(
        _request("katress", "wixen", InventoryGender.MALE)
    )
    assert isinstance(result, DirectBreedingInvalid)


def test_missing_rule_is_structured(production_rules: tuple[BreedingRule, ...]) -> None:
    result = GenderAwareDirectBreedingIndex(production_rules).query(
        _request("not_in_dataset", "katress")
    )
    assert isinstance(result, DirectBreedingNotFound)


def test_unordered_index_rejects_conflicting_children() -> None:
    with pytest.raises(ValueError, match="conflicting"):
        GenderAwareDirectBreedingIndex(
            [
                _rule("pal_a", "pal_b", "pal_c"),
                _rule("pal_b", "pal_a", "pal_d", source_hash="1" * 64),
            ]
        )


def test_directed_family_must_not_be_collapsed_or_incomplete() -> None:
    directed = _rule(
        "pal_a",
        "pal_b",
        "pal_c",
        result_kind=BreedingResultKind.GENDER_DIRECTED,
        parent_a_gender=GenderConstraint.MALE,
        parent_b_gender=GenderConstraint.FEMALE,
    )
    with pytest.raises(ValueError, match="every possible result"):
        GenderAwareDirectBreedingIndex([directed])
    with pytest.raises(ValueError, match="conflict"):
        GenderAwareDirectBreedingIndex([directed, _rule("pal_a", "pal_b", "pal_d")])
