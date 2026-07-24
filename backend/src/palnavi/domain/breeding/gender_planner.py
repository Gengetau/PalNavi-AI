"""Deterministic gender-capable route search over immutable production rules."""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import count

from palnavi.domain.breeding.direct import GenderAwareDirectBreedingIndex
from palnavi.domain.breeding.models import (
    BreedingResultKind,
    BreedingRule,
    GenderConstraint,
    GenderRequiredRouteResult,
    GenderRouteCost,
    GenderRoutePlanningRequest,
    GenderRouteResult,
    GenderRouteState,
    GenderRouteStep,
    InvalidGenderRouteResult,
    InventoryGender,
    SpeciesGenderFeasibility,
    SpeciesId,
    SuccessfulGenderRouteResult,
    UnreachableGenderRouteResult,
)

_StateKey = tuple[SpeciesId, InventoryGender]
_ProducerSignature = tuple[int, str, str, str, str, str, str, str]
_PlanSignature = tuple[_ProducerSignature, ...]
_PlanPriority = tuple[int, int, _PlanSignature]


@dataclass(frozen=True, slots=True)
class _Producer:
    parent_a: _StateKey
    parent_b: _StateKey
    child: _StateKey
    generation: int
    rule: BreedingRule

    @property
    def signature(self) -> _ProducerSignature:
        return (
            self.generation,
            self.parent_a[0].value,
            self.parent_a[1].value,
            self.parent_b[0].value,
            self.parent_b[1].value,
            self.child[0].value,
            self.child[1].value,
            f"{self.rule.result_kind.value}:{self.rule.source_record_hash}",
        )


@dataclass(frozen=True, slots=True)
class _Plan:
    target: _StateKey
    generation: int
    producers: tuple[_Producer, ...]

    @property
    def priority(self) -> _PlanPriority:
        signature = tuple(producer.signature for producer in self.producers)
        return (self.generation, len(self.producers), signature)

    @property
    def producer_map(self) -> dict[_StateKey, _Producer]:
        return {producer.child: producer for producer in self.producers}


@dataclass(frozen=True, slots=True)
class _Transition:
    parent_a: _StateKey
    parent_b: _StateKey
    child: _StateKey
    rule: BreedingRule


class GenderAwareRoutePlanner:
    """Find minimum-generation routes without inventing probability-dependent costs."""

    def plan(
        self,
        request: GenderRoutePlanningRequest,
        rules: Iterable[BreedingRule],
        gender_feasibility: Iterable[SpeciesGenderFeasibility],
    ) -> GenderRouteResult:
        profiles, errors = self._normalize_profiles(gender_feasibility)
        if errors:
            return InvalidGenderRouteResult(
                target_species=request.target_species,
                errors=errors,
            )

        rule_tuple = tuple(rules)
        try:
            GenderAwareDirectBreedingIndex(rule_tuple)
        except ValueError:
            return InvalidGenderRouteResult(
                target_species=request.target_species,
                errors=("breeding rules contain a conflicting gender-aware index",),
            )

        errors = self._validate_request(request, profiles)
        if errors:
            return InvalidGenderRouteResult(
                target_species=request.target_species,
                errors=errors,
            )

        unknown_ids = tuple(
            sorted(
                candidate.instance_id
                for candidate in request.inventory
                if candidate.gender is InventoryGender.UNKNOWN
            )
        )
        if unknown_ids:
            return GenderRequiredRouteResult(
                unknown_instance_ids=unknown_ids,
                reason="route planning requires concrete inventory genders",
            )

        target_key = (request.target_species, request.target_gender)
        initial_keys = frozenset(
            (candidate.species, candidate.gender) for candidate in request.inventory
        )
        if target_key in initial_keys:
            return SuccessfulGenderRouteResult(
                target=self._state(target_key, 0),
                steps=(),
                cost=GenderRouteCost(generations=0, breeding_steps=0),
            )

        transitions = self._build_transitions(rule_tuple, profiles)
        best = self._search(initial_keys, transitions)
        target_plan = best.get(target_key)
        if target_plan is None:
            return UnreachableGenderRouteResult(
                target=self._state(target_key, 0),
                reachable_states=tuple(
                    self._state(key, plan.generation)
                    for key, plan in sorted(best.items(), key=lambda item: item[0])
                ),
                reason="target gender state cannot be produced from the supplied inventory",
            )
        return self._success(target_plan)

    @staticmethod
    def _normalize_profiles(
        values: Iterable[SpeciesGenderFeasibility],
    ) -> tuple[dict[SpeciesId, SpeciesGenderFeasibility], tuple[str, ...]]:
        profiles: dict[SpeciesId, SpeciesGenderFeasibility] = {}
        errors: list[str] = []
        for profile in values:
            if profile.species in profiles:
                errors.append("gender feasibility contains a duplicate species")
            profiles[profile.species] = profile
        if not profiles:
            errors.append("gender feasibility is empty")
        return profiles, tuple(sorted(set(errors)))

    @staticmethod
    def _validate_request(
        request: GenderRoutePlanningRequest,
        profiles: Mapping[SpeciesId, SpeciesGenderFeasibility],
    ) -> tuple[str, ...]:
        errors: list[str] = []
        target_profile = profiles.get(request.target_species)
        if target_profile is None:
            errors.append("target species is absent from gender feasibility")
        elif not target_profile.supports(request.target_gender):
            errors.append("target gender is not feasible for the target species")
        for candidate in request.inventory:
            profile = profiles.get(candidate.species)
            if profile is None:
                errors.append("inventory contains a species absent from gender feasibility")
            elif candidate.gender is not InventoryGender.UNKNOWN and not profile.supports(
                candidate.gender
            ):
                errors.append("inventory contains an infeasible concrete gender")
        return tuple(sorted(set(errors)))

    @classmethod
    def _build_transitions(
        cls,
        rules: tuple[BreedingRule, ...],
        profiles: Mapping[SpeciesId, SpeciesGenderFeasibility],
    ) -> tuple[_Transition, ...]:
        transitions: dict[
            tuple[_StateKey, _StateKey, _StateKey, str],
            _Transition,
        ] = {}
        for rule in rules:
            for parent_a, parent_b in cls._parent_orientations(rule):
                child_profile = profiles.get(rule.child)
                if child_profile is None:
                    continue
                for child_gender in (InventoryGender.MALE, InventoryGender.FEMALE):
                    if not child_profile.supports(child_gender):
                        continue
                    child = (rule.child, child_gender)
                    key = (parent_a, parent_b, child, rule.source_record_hash)
                    transitions[key] = _Transition(
                        parent_a=parent_a,
                        parent_b=parent_b,
                        child=child,
                        rule=rule,
                    )
        return tuple(
            sorted(
                transitions.values(),
                key=lambda item: (
                    item.parent_a,
                    item.parent_b,
                    item.child,
                    item.rule.result_kind.value,
                    item.rule.source_record_hash,
                ),
            )
        )

    @staticmethod
    def _parent_orientations(rule: BreedingRule) -> tuple[tuple[_StateKey, _StateKey], ...]:
        if rule.result_kind is BreedingResultKind.GENDER_DIRECTED:
            return (
                (
                    (
                        rule.parent_a.species,
                        InventoryGender(rule.parent_a.gender.value),
                    ),
                    (
                        rule.parent_b.species,
                        InventoryGender(rule.parent_b.gender.value),
                    ),
                ),
            )
        if (
            rule.parent_a.gender is not GenderConstraint.WILDCARD
            or rule.parent_b.gender is not GenderConstraint.WILDCARD
        ):
            raise ValueError("non-directed rule contains a concrete gender constraint")
        orientations = {
            (
                (rule.parent_a.species, InventoryGender.MALE),
                (rule.parent_b.species, InventoryGender.FEMALE),
            ),
            (
                (rule.parent_a.species, InventoryGender.FEMALE),
                (rule.parent_b.species, InventoryGender.MALE),
            ),
        }
        return tuple(sorted(orientations))

    @classmethod
    def _search(
        cls,
        initial_keys: frozenset[_StateKey],
        transitions: tuple[_Transition, ...],
    ) -> dict[_StateKey, _Plan]:
        best = {key: _Plan(target=key, generation=0, producers=()) for key in initial_keys}
        by_parent: dict[_StateKey, list[_Transition]] = defaultdict(list)
        for transition in transitions:
            by_parent[transition.parent_a].append(transition)
            if transition.parent_b != transition.parent_a:
                by_parent[transition.parent_b].append(transition)

        serial = count()
        heap: list[tuple[_PlanPriority, int, _StateKey]] = []
        for key, plan in sorted(best.items()):
            heapq.heappush(heap, (plan.priority, next(serial), key))

        while heap:
            priority, _, changed_key = heapq.heappop(heap)
            current = best.get(changed_key)
            if current is None or current.priority != priority:
                continue
            for transition in by_parent.get(changed_key, ()):
                parent_a_plan = best.get(transition.parent_a)
                parent_b_plan = best.get(transition.parent_b)
                if parent_a_plan is None or parent_b_plan is None:
                    continue
                if transition.child in parent_a_plan.producer_map or (
                    transition.child in parent_b_plan.producer_map
                ):
                    continue
                candidate = cls._combine(parent_a_plan, parent_b_plan, transition)
                existing = best.get(transition.child)
                if existing is not None and existing.priority <= candidate.priority:
                    continue
                best[transition.child] = candidate
                heapq.heappush(
                    heap,
                    (candidate.priority, next(serial), transition.child),
                )
        return best

    @classmethod
    def _combine(
        cls,
        parent_a_plan: _Plan,
        parent_b_plan: _Plan,
        transition: _Transition,
    ) -> _Plan:
        producers: dict[_StateKey, _Producer] = {}
        for producer in (*parent_a_plan.producers, *parent_b_plan.producers):
            existing = producers.get(producer.child)
            if existing is None or producer.signature < existing.signature:
                producers[producer.child] = producer

        generation = 1 + max(parent_a_plan.generation, parent_b_plan.generation)
        producers[transition.child] = _Producer(
            parent_a=transition.parent_a,
            parent_b=transition.parent_b,
            child=transition.child,
            generation=generation,
            rule=transition.rule,
        )
        required: dict[_StateKey, _Producer] = {}

        def visit(key: _StateKey) -> None:
            producer = producers.get(key)
            if producer is None or key in required:
                return
            required[key] = producer
            visit(producer.parent_a)
            visit(producer.parent_b)

        visit(transition.child)
        ordered = tuple(sorted(required.values(), key=lambda item: item.signature))
        return _Plan(
            target=transition.child,
            generation=generation,
            producers=ordered,
        )

    @staticmethod
    def _state(key: _StateKey, generation: int) -> GenderRouteState:
        return GenderRouteState(
            species=key[0],
            gender=key[1],
            required_passive_set=frozenset(),
            required_iv_constraints=(),
            generation_depth=generation,
        )

    @classmethod
    def _success(cls, plan: _Plan) -> SuccessfulGenderRouteResult:
        producer_by_child = {producer.child: producer for producer in plan.producers}
        steps = []
        for order, producer in enumerate(plan.producers, start=1):
            parent_a_producer = producer_by_child.get(producer.parent_a)
            parent_b_producer = producer_by_child.get(producer.parent_b)
            steps.append(
                GenderRouteStep(
                    order=order,
                    generation=producer.generation,
                    parent_a=cls._state(
                        producer.parent_a,
                        0 if parent_a_producer is None else parent_a_producer.generation,
                    ),
                    parent_b=cls._state(
                        producer.parent_b,
                        0 if parent_b_producer is None else parent_b_producer.generation,
                    ),
                    child=cls._state(producer.child, producer.generation),
                    result_kind=producer.rule.result_kind,
                    source_record_hash=producer.rule.source_record_hash,
                )
            )
        return SuccessfulGenderRouteResult(
            target=cls._state(plan.target, plan.generation),
            steps=tuple(steps),
            cost=GenderRouteCost(
                generations=plan.generation,
                breeding_steps=len(steps),
            ),
        )
