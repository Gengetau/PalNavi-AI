"""Deterministic direct-breeding lookup without lossy gender canonicalization."""

from __future__ import annotations

from collections.abc import Iterable

from palnavi.domain.breeding.models import (
    BreedingResultKind,
    BreedingRule,
    DirectBreedingGenderRequired,
    DirectBreedingInvalid,
    DirectBreedingNotFound,
    DirectBreedingPossibility,
    DirectBreedingRequest,
    DirectBreedingResult,
    DirectBreedingSuccess,
    InventoryGender,
    SpeciesId,
)

_ConcreteKey = tuple[SpeciesId, InventoryGender, SpeciesId, InventoryGender]
_SpeciesKey = tuple[SpeciesId, SpeciesId]


def _species_key(parent_a: SpeciesId, parent_b: SpeciesId) -> _SpeciesKey:
    return (parent_a, parent_b) if parent_a <= parent_b else (parent_b, parent_a)


def _concrete_key(
    parent_a: SpeciesId,
    parent_a_gender: InventoryGender,
    parent_b: SpeciesId,
    parent_b_gender: InventoryGender,
) -> _ConcreteKey:
    return (parent_a, parent_a_gender, parent_b, parent_b_gender)


class GenderAwareDirectBreedingIndex:
    """Separate directed and unordered indexes built from validated immutable rules."""

    def __init__(self, rules: Iterable[BreedingRule]) -> None:
        wildcard_rules: dict[_SpeciesKey, BreedingRule] = {}
        directed_rules: dict[_ConcreteKey, BreedingRule] = {}
        directed_families: dict[_SpeciesKey, list[BreedingRule]] = {}
        source_dataset_id: str | None = None

        for rule in rules:
            if source_dataset_id is None:
                source_dataset_id = rule.source_dataset_id
            elif source_dataset_id != rule.source_dataset_id:
                raise ValueError("direct breeding index cannot mix source datasets")

            family_key = _species_key(rule.parent_a.species, rule.parent_b.species)
            if rule.result_kind is BreedingResultKind.GENDER_DIRECTED:
                if family_key in wildcard_rules:
                    raise ValueError("directed and wildcard rules conflict for one species pair")
                key = self._rule_concrete_key(rule)
                reverse_key = (key[2], key[3], key[0], key[1])
                for candidate_key in (key, reverse_key):
                    existing = directed_rules.get(candidate_key)
                    if existing is not None and existing != rule:
                        raise ValueError("directed breeding key has conflicting source rules")
                    directed_rules[candidate_key] = rule
                directed_families.setdefault(family_key, []).append(rule)
            else:
                if family_key in directed_families:
                    raise ValueError("wildcard and directed rules conflict for one species pair")
                existing = wildcard_rules.get(family_key)
                if existing is not None and existing != rule:
                    raise ValueError("unordered breeding key has conflicting source rules")
                wildcard_rules[family_key] = rule

        for family_rules in directed_families.values():
            if len(family_rules) < 2:
                raise ValueError("gender-directed family must preserve every possible result")

        self._wildcard_rules = wildcard_rules
        self._directed_rules = directed_rules
        self._directed_families = {
            key: tuple(
                sorted(
                    family_rules,
                    key=lambda rule: (
                        rule.parent_a.species.value,
                        rule.parent_a.gender.value,
                        rule.parent_b.species.value,
                        rule.parent_b.gender.value,
                        rule.child.value,
                    ),
                )
            )
            for key, family_rules in directed_families.items()
        }
        self._source_dataset_id = source_dataset_id

    @staticmethod
    def _rule_concrete_key(rule: BreedingRule) -> _ConcreteKey:
        return _concrete_key(
            rule.parent_a.species,
            InventoryGender(rule.parent_a.gender.value),
            rule.parent_b.species,
            InventoryGender(rule.parent_b.gender.value),
        )

    @property
    def source_dataset_id(self) -> str | None:
        return self._source_dataset_id

    @property
    def wildcard_rule_count(self) -> int:
        return len(self._wildcard_rules)

    @property
    def directed_rule_count(self) -> int:
        return sum(len(rules) for rules in self._directed_families.values())

    def query(self, request: DirectBreedingRequest) -> DirectBreedingResult:
        gender_a = request.parent_a_gender
        gender_b = request.parent_b_gender
        family_key = _species_key(request.parent_a, request.parent_b)
        wildcard_rule = self._wildcard_rules.get(family_key)
        directed_family = self._directed_families.get(family_key)

        if (gender_a is None) != (gender_b is None):
            return DirectBreedingInvalid(
                errors=("species-only queries must omit both parent genders",)
            )

        if gender_a is None and gender_b is None:
            if directed_family is not None:
                return DirectBreedingGenderRequired(
                    possible_results=self._directed_possibilities(
                        request.parent_a,
                        request.parent_b,
                        directed_family,
                    ),
                    reason="this species pair has gender-dependent results",
                )
            if wildcard_rule is None:
                return DirectBreedingNotFound(reason="no direct breeding rule was found")
            return self._success(wildcard_rule)

        if gender_a is None or gender_b is None:
            raise AssertionError("gender pair validation did not narrow optional values")

        if gender_a is InventoryGender.UNKNOWN or gender_b is InventoryGender.UNKNOWN:
            if directed_family is not None:
                possibilities = self._directed_possibilities(
                    request.parent_a,
                    request.parent_b,
                    directed_family,
                )
            elif wildcard_rule is not None:
                possibilities = self._wildcard_possibilities(wildcard_rule)
            else:
                return DirectBreedingNotFound(reason="no direct breeding rule was found")
            return DirectBreedingGenderRequired(
                possible_results=possibilities,
                reason="concrete breeding requires known opposite parent genders",
            )

        if gender_a is gender_b:
            return DirectBreedingInvalid(
                errors=("concrete breeding requires opposite parent genders",)
            )

        directed_rule = self._directed_rules.get(
            _concrete_key(request.parent_a, gender_a, request.parent_b, gender_b)
        )
        if directed_rule is not None:
            return self._success(directed_rule)
        if directed_family is not None:
            return DirectBreedingInvalid(
                errors=("parent species and genders do not satisfy a directed breeding rule",)
            )
        if wildcard_rule is not None:
            return self._success(wildcard_rule)
        return DirectBreedingNotFound(reason="no direct breeding rule was found")

    @staticmethod
    def _success(rule: BreedingRule) -> DirectBreedingSuccess:
        return DirectBreedingSuccess(
            child=rule.child,
            result_kind=rule.result_kind,
            source_record_hash=rule.source_record_hash,
        )

    @staticmethod
    def _wildcard_possibilities(
        rule: BreedingRule,
    ) -> tuple[DirectBreedingPossibility, ...]:
        return (
            DirectBreedingPossibility(
                parent_a_gender=InventoryGender.MALE,
                parent_b_gender=InventoryGender.FEMALE,
                child=rule.child,
                result_kind=rule.result_kind,
                source_record_hash=rule.source_record_hash,
            ),
            DirectBreedingPossibility(
                parent_a_gender=InventoryGender.FEMALE,
                parent_b_gender=InventoryGender.MALE,
                child=rule.child,
                result_kind=rule.result_kind,
                source_record_hash=rule.source_record_hash,
            ),
        )

    @staticmethod
    def _directed_possibilities(
        query_parent_a: SpeciesId,
        query_parent_b: SpeciesId,
        rules: tuple[BreedingRule, ...],
    ) -> tuple[DirectBreedingPossibility, ...]:
        possibilities = []
        for rule in rules:
            if rule.parent_a.species == query_parent_a and rule.parent_b.species == query_parent_b:
                parent_a = rule.parent_a
                parent_b = rule.parent_b
            elif (
                rule.parent_b.species == query_parent_a and rule.parent_a.species == query_parent_b
            ):
                parent_a = rule.parent_b
                parent_b = rule.parent_a
            else:
                raise AssertionError("directed family contains an unrelated rule")
            possibilities.append(
                DirectBreedingPossibility(
                    parent_a_gender=InventoryGender(parent_a.gender.value),
                    parent_b_gender=InventoryGender(parent_b.gender.value),
                    child=rule.child,
                    result_kind=rule.result_kind,
                    source_record_hash=rule.source_record_hash,
                )
            )
        return tuple(
            sorted(
                possibilities,
                key=lambda item: (
                    0 if item.parent_a_gender is InventoryGender.MALE else 1,
                    item.child.value,
                ),
            )
        )
