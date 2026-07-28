"""Exact capture-set-aware route search over immutable production rules."""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from itertools import count

from palnavi.domain.breeding.direct import GenderAwareDirectBreedingIndex
from palnavi.domain.breeding.gender_planner import GenderAwareRoutePlanner
from palnavi.domain.breeding.models import (
    BreedingResultKind,
    BreedingRule,
    CaptureCandidate,
    CaptureGenderRequiredResult,
    CaptureRequirement,
    CaptureRouteCost,
    CaptureRoutePlanningRequest,
    CaptureRouteResult,
    CaptureRouteSearchLimitExceeded,
    GenderConstraint,
    GenderRequiredRouteResult,
    GenderRoutePlanningRequest,
    GenderRouteState,
    GenderRouteStep,
    InvalidCaptureRouteResult,
    InvalidGenderRouteResult,
    InventoryGender,
    OwnedBreedingCandidate,
    SpeciesGenderFeasibility,
    SpeciesId,
    SuccessfulCaptureRouteResult,
    SuccessfulGenderRouteResult,
    UnreachableCaptureRouteResult,
    UnreachableGenderRouteResult,
)

_StateKey = tuple[SpeciesId, InventoryGender]
_ProducerSignature = tuple[int, str, str, str, str, str, str, str]
_PlanSignature = tuple[_ProducerSignature, ...]
_PlanPriority = tuple[int, int, int, tuple[str, ...], _PlanSignature]

DEFAULT_MAX_LABELS_PER_STATE = 4096
DEFAULT_MAX_TOTAL_LABELS = 200_000


@dataclass(frozen=True, slots=True)
class _Producer:
    parent_a: _StateKey
    parent_b: _StateKey
    child: _StateKey
    generation: int
    rule: BreedingRule
    _signature: _ProducerSignature = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_signature",
            (
                self.generation,
                self.parent_a[0].value,
                self.parent_a[1].value,
                self.parent_b[0].value,
                self.parent_b[1].value,
                self.child[0].value,
                self.child[1].value,
                f"{self.rule.result_kind.value}:{self.rule.source_record_hash}",
            ),
        )

    @property
    def signature(self) -> _ProducerSignature:
        return self._signature


@dataclass(frozen=True, slots=True, eq=False)
class _Plan:
    target: _StateKey
    captures: frozenset[str]
    generation: int
    producers: tuple[_Producer, ...]
    _signature: _PlanSignature = field(init=False, repr=False)
    _priority: _PlanPriority = field(init=False, repr=False)
    _producer_map: dict[_StateKey, _Producer] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        signature = tuple(producer.signature for producer in self.producers)
        capture_ids = tuple(sorted(self.captures))
        object.__setattr__(self, "_signature", signature)
        object.__setattr__(
            self,
            "_priority",
            (
                len(capture_ids),
                self.generation,
                len(self.producers),
                capture_ids,
                signature,
            ),
        )
        object.__setattr__(
            self,
            "_producer_map",
            {producer.child: producer for producer in self.producers},
        )

    @property
    def signature(self) -> _PlanSignature:
        return self._signature

    @property
    def priority(self) -> _PlanPriority:
        return self._priority

    @property
    def producer_map(self) -> dict[_StateKey, _Producer]:
        return self._producer_map


@dataclass(frozen=True, slots=True)
class _Transition:
    parent_a: _StateKey
    parent_b: _StateKey
    child: _StateKey
    rule: BreedingRule


class CaptureAwareRoutePlanner:
    """Find exact routes ranked by distinct user-supplied capture candidates."""

    def __init__(
        self,
        *,
        max_labels_per_state: int = DEFAULT_MAX_LABELS_PER_STATE,
        max_total_labels: int = DEFAULT_MAX_TOTAL_LABELS,
    ) -> None:
        if max_labels_per_state < 1 or max_total_labels < 1:
            raise ValueError("capture route label bounds must be positive")
        self._max_labels_per_state = max_labels_per_state
        self._max_total_labels = max_total_labels

    def plan(
        self,
        request: CaptureRoutePlanningRequest,
        rules: Iterable[BreedingRule],
        gender_feasibility: Iterable[SpeciesGenderFeasibility],
    ) -> CaptureRouteResult:
        profiles, errors = self._normalize_profiles(gender_feasibility)
        if errors:
            return InvalidCaptureRouteResult(
                target_species=request.target_species,
                errors=errors,
            )

        rule_tuple = tuple(rules)
        try:
            GenderAwareDirectBreedingIndex(rule_tuple)
        except ValueError:
            return InvalidCaptureRouteResult(
                target_species=request.target_species,
                errors=("breeding rules contain a conflicting gender-aware index",),
            )

        errors = self._validate_request(request, profiles)
        if errors:
            return InvalidCaptureRouteResult(
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
            return CaptureGenderRequiredResult(
                unknown_instance_ids=unknown_ids,
                reason="capture-ranked planning requires concrete inventory genders",
            )

        owned_only_result = self._owned_only_result(
            request,
            rule_tuple,
            tuple(profiles.values()),
        )
        if isinstance(
            owned_only_result,
            (SuccessfulCaptureRouteResult, InvalidCaptureRouteResult),
        ):
            return owned_only_result
        if not request.capture_candidates:
            return owned_only_result

        owned_keys = frozenset(
            (candidate.species, candidate.gender) for candidate in request.inventory
        )
        candidate_by_key = {
            (candidate.species, candidate.gender): candidate
            for candidate in request.capture_candidates
        }
        target_key = (request.target_species, request.target_gender)
        direct_target = candidate_by_key.get(target_key)
        if direct_target is not None:
            return SuccessfulCaptureRouteResult(
                target=self._state(target_key, 0),
                steps=(),
                capture_requirements=(
                    CaptureRequirement(
                        candidate_id=direct_target.candidate_id,
                        species=direct_target.species,
                        gender=direct_target.gender,
                    ),
                ),
                cost=CaptureRouteCost(
                    new_capture_count=1,
                    generations=0,
                    breeding_steps=0,
                ),
            )
        exact_linear_result = self._single_candidate_linear_result(
            request,
            rule_tuple,
            tuple(profiles.values()),
        )
        if exact_linear_result is not None:
            return exact_linear_result
        transitions = self._build_transitions(rule_tuple, profiles)
        labels, limit_exceeded = self._search(
            owned_keys,
            candidate_by_key,
            transitions,
        )
        if limit_exceeded:
            return CaptureRouteSearchLimitExceeded(
                target_species=request.target_species,
                reason="exact capture-set search exceeded its deterministic label bound",
            )

        target_plans = labels.get(target_key, ())
        if not target_plans:
            return UnreachableCaptureRouteResult(
                target=self._state(target_key, 0),
                reachable_states=tuple(
                    self._state(key, min(plan.generation for plan in plans))
                    for key, plans in sorted(labels.items())
                ),
                reason=(
                    "target gender state cannot be produced from the supplied inventory "
                    "and explicit capture candidates"
                ),
            )
        return self._success(min(target_plans, key=lambda plan: plan.priority), candidate_by_key)

    @staticmethod
    def _owned_only_result(
        request: CaptureRoutePlanningRequest,
        rules: tuple[BreedingRule, ...],
        profiles: tuple[SpeciesGenderFeasibility, ...],
    ) -> CaptureRouteResult:
        result = GenderAwareRoutePlanner().plan(
            GenderRoutePlanningRequest(
                target_species=request.target_species,
                target_gender=request.target_gender,
                inventory=request.inventory,
            ),
            rules,
            profiles,
        )
        if isinstance(result, SuccessfulGenderRouteResult):
            return SuccessfulCaptureRouteResult(
                target=result.target,
                steps=result.steps,
                capture_requirements=(),
                cost=CaptureRouteCost(
                    new_capture_count=0,
                    generations=result.cost.generations,
                    breeding_steps=result.cost.breeding_steps,
                ),
            )
        if isinstance(result, GenderRequiredRouteResult):
            return CaptureGenderRequiredResult(
                unknown_instance_ids=result.unknown_instance_ids,
                reason=result.reason,
            )
        if isinstance(result, UnreachableGenderRouteResult):
            return UnreachableCaptureRouteResult(
                target=result.target,
                reachable_states=result.reachable_states,
                reason=result.reason,
            )
        if isinstance(result, InvalidGenderRouteResult):
            return InvalidCaptureRouteResult(
                target_species=result.target_species,
                errors=result.errors,
            )
        raise AssertionError("owned-only route planner returned an unsupported result type")

    @staticmethod
    def _single_candidate_linear_result(
        request: CaptureRoutePlanningRequest,
        rules: tuple[BreedingRule, ...],
        profiles: tuple[SpeciesGenderFeasibility, ...],
    ) -> SuccessfulCaptureRouteResult | None:
        """Return only a one-candidate route that meets every numeric lower bound.

        The caller has already proved that owned inventory alone is unreachable and
        that the target is not the candidate itself, so one capture is minimal. The
        accepted gender-aware planner minimizes generation depth. Every breeding DAG
        has at least as many producers as its maximum generation; equality proves a
        linear route whose stable-signature tie break is extension-monotone.
        """
        if len(request.capture_candidates) != 1:
            return None
        candidate = request.capture_candidates[0]
        candidate_key = (candidate.species, candidate.gender)
        owned_keys = {
            (owned_candidate.species, owned_candidate.gender)
            for owned_candidate in request.inventory
        }
        if candidate_key in owned_keys:
            return None

        result = GenderAwareRoutePlanner().plan(
            GenderRoutePlanningRequest(
                target_species=request.target_species,
                target_gender=request.target_gender,
                inventory=(
                    *request.inventory,
                    OwnedBreedingCandidate(
                        instance_id=candidate.candidate_id,
                        species=candidate.species,
                        gender=candidate.gender,
                    ),
                ),
            ),
            rules,
            profiles,
        )
        if not isinstance(result, SuccessfulGenderRouteResult):
            return None
        if result.cost.breeding_steps != result.cost.generations:
            return None
        if {step.generation for step in result.steps} != set(range(1, result.cost.generations + 1)):
            return None

        produced_keys = {(step.child.species, step.child.gender) for step in result.steps}
        leaf_keys = {
            (parent.species, parent.gender)
            for step in result.steps
            for parent in (step.parent_a, step.parent_b)
            if (parent.species, parent.gender) not in produced_keys
        }
        if candidate_key not in leaf_keys:
            return None

        return SuccessfulCaptureRouteResult(
            target=result.target,
            steps=result.steps,
            capture_requirements=(
                CaptureRequirement(
                    candidate_id=candidate.candidate_id,
                    species=candidate.species,
                    gender=candidate.gender,
                ),
            ),
            cost=CaptureRouteCost(
                new_capture_count=1,
                generations=result.cost.generations,
                breeding_steps=result.cost.breeding_steps,
            ),
        )

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
        request: CaptureRoutePlanningRequest,
        profiles: Mapping[SpeciesId, SpeciesGenderFeasibility],
    ) -> tuple[str, ...]:
        errors: list[str] = []
        target_profile = profiles.get(request.target_species)
        if target_profile is None:
            errors.append("target species is absent from gender feasibility")
        elif not target_profile.supports(request.target_gender):
            errors.append("target gender is not feasible for the target species")

        for owned_candidate in request.inventory:
            profile = profiles.get(owned_candidate.species)
            if profile is None:
                errors.append("inventory contains a species absent from gender feasibility")
            elif owned_candidate.gender is not InventoryGender.UNKNOWN and not profile.supports(
                owned_candidate.gender
            ):
                errors.append("inventory contains an infeasible concrete gender")

        for capture_candidate in request.capture_candidates:
            profile = profiles.get(capture_candidate.species)
            if profile is None:
                errors.append("capture candidates contain a species absent from gender feasibility")
            elif not profile.supports(capture_candidate.gender):
                errors.append("capture candidates contain an infeasible concrete gender")
        return tuple(sorted(set(errors)))

    @classmethod
    def _build_transitions(
        cls,
        rules: tuple[BreedingRule, ...],
        profiles: Mapping[SpeciesId, SpeciesGenderFeasibility],
    ) -> tuple[_Transition, ...]:
        transitions: dict[tuple[_StateKey, _StateKey, _StateKey, str], _Transition] = {}
        for rule in rules:
            for parent_a, parent_b in cls._parent_orientations(rule):
                child_profile = profiles.get(rule.child)
                if child_profile is None:
                    continue
                for child_gender in (InventoryGender.MALE, InventoryGender.FEMALE):
                    if not child_profile.supports(child_gender):
                        continue
                    child = (rule.child, child_gender)
                    transitions[(parent_a, parent_b, child, rule.source_record_hash)] = _Transition(
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
                    (rule.parent_a.species, InventoryGender(rule.parent_a.gender.value)),
                    (rule.parent_b.species, InventoryGender(rule.parent_b.gender.value)),
                ),
            )
        if (
            rule.parent_a.gender is not GenderConstraint.WILDCARD
            or rule.parent_b.gender is not GenderConstraint.WILDCARD
        ):
            raise ValueError("non-directed rule contains a concrete gender constraint")
        return tuple(
            sorted(
                {
                    (
                        (rule.parent_a.species, InventoryGender.MALE),
                        (rule.parent_b.species, InventoryGender.FEMALE),
                    ),
                    (
                        (rule.parent_a.species, InventoryGender.FEMALE),
                        (rule.parent_b.species, InventoryGender.MALE),
                    ),
                }
            )
        )

    def _search(
        self,
        owned_keys: frozenset[_StateKey],
        candidate_by_key: Mapping[_StateKey, CaptureCandidate],
        transitions: tuple[_Transition, ...],
    ) -> tuple[dict[_StateKey, list[_Plan]], bool]:
        labels: dict[_StateKey, list[_Plan]] = defaultdict(list)
        serial = count()
        heap: list[tuple[_PlanPriority, int, _Plan]] = []
        expanded: set[_Plan] = set()
        total_labels = 0

        def add(plan: _Plan) -> bool | None:
            nonlocal total_labels
            current = labels[plan.target]
            if any(self._dominates(existing, plan) for existing in current):
                return False
            retained = [existing for existing in current if not self._dominates(plan, existing)]
            removed = len(current) - len(retained)
            if (
                len(retained) + 1 > self._max_labels_per_state
                or total_labels - removed + 1 > self._max_total_labels
            ):
                return None
            retained.append(plan)
            retained.sort(key=lambda item: item.priority)
            labels[plan.target] = retained
            total_labels = total_labels - removed + 1
            heapq.heappush(heap, (plan.priority, next(serial), plan))
            return True

        for key in sorted(owned_keys):
            if add(_Plan(key, frozenset(), 0, ())) is None:
                return dict(labels), True
        for key, raw_candidate in sorted(candidate_by_key.items()):
            candidate_id = raw_candidate.candidate_id
            if add(_Plan(key, frozenset({candidate_id}), 0, ())) is None:
                return dict(labels), True

        by_parent: dict[_StateKey, list[_Transition]] = defaultdict(list)
        for transition in transitions:
            by_parent[transition.parent_a].append(transition)
            if transition.parent_b != transition.parent_a:
                by_parent[transition.parent_b].append(transition)

        while heap:
            _, _, changed = heapq.heappop(heap)
            if changed not in labels.get(changed.target, ()):
                continue
            expanded.add(changed)
            for transition in by_parent.get(changed.target, ()):
                if transition.parent_a == changed.target:
                    pairs = (
                        (changed, other)
                        for other in tuple(labels.get(transition.parent_b, ()))
                        if other in expanded
                    )
                else:
                    pairs = (
                        (other, changed)
                        for other in tuple(labels.get(transition.parent_a, ()))
                        if other in expanded
                    )
                for parent_a_plan, parent_b_plan in pairs:
                    candidate = self._combine(
                        parent_a_plan,
                        parent_b_plan,
                        transition,
                        owned_keys,
                        candidate_by_key,
                    )
                    if candidate is None:
                        continue
                    added = add(candidate)
                    if added is None:
                        return dict(labels), True
        return dict(labels), False

    @staticmethod
    def _dominates(left: _Plan, right: _Plan) -> bool:
        return (
            left.captures.issubset(right.captures)
            and left.generation <= right.generation
            and len(left.producers) <= len(right.producers)
            and left.signature <= right.signature
        )

    @classmethod
    def _combine(
        cls,
        parent_a_plan: _Plan,
        parent_b_plan: _Plan,
        transition: _Transition,
        owned_keys: frozenset[_StateKey],
        candidate_by_key: Mapping[_StateKey, CaptureCandidate],
    ) -> _Plan | None:
        if transition.child in parent_a_plan.producer_map or (
            transition.child in parent_b_plan.producer_map
        ):
            return None

        producers: dict[_StateKey, _Producer] = {}
        for producer in (*parent_a_plan.producers, *parent_b_plan.producers):
            existing = producers.get(producer.child)
            if existing is None or producer.signature < existing.signature:
                producers[producer.child] = producer
        producers[transition.child] = _Producer(
            parent_a=transition.parent_a,
            parent_b=transition.parent_b,
            child=transition.child,
            generation=0,
            rule=transition.rule,
        )
        return cls._normalize_plan(
            transition.child,
            producers,
            owned_keys,
            candidate_by_key,
        )

    @classmethod
    def _normalize_plan(
        cls,
        target: _StateKey,
        producers: Mapping[_StateKey, _Producer],
        owned_keys: frozenset[_StateKey],
        candidate_by_key: Mapping[_StateKey, CaptureCandidate],
    ) -> _Plan | None:
        required: dict[_StateKey, _Producer] = {}
        generations: dict[_StateKey, int] = {}
        captures: set[str] = set()
        visiting: set[_StateKey] = set()

        def visit(key: _StateKey) -> int | None:
            if key in generations:
                return generations[key]
            if key in visiting:
                return None
            producer = producers.get(key)
            if producer is None:
                if key not in owned_keys:
                    candidate = candidate_by_key.get(key)
                    if candidate is None:
                        return None
                    captures.add(candidate.candidate_id)
                generations[key] = 0
                return 0

            visiting.add(key)
            parent_a_generation = visit(producer.parent_a)
            parent_b_generation = visit(producer.parent_b)
            visiting.remove(key)
            if parent_a_generation is None or parent_b_generation is None:
                return None
            generation = 1 + max(parent_a_generation, parent_b_generation)
            normalized = (
                producer
                if producer.generation == generation
                else replace(producer, generation=generation)
            )
            required[key] = normalized
            generations[key] = generation
            return generation

        generation = visit(target)
        if generation is None:
            return None
        ordered = tuple(sorted(required.values(), key=lambda item: item.signature))
        return _Plan(
            target=target,
            captures=frozenset(captures),
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
    def _success(
        cls,
        plan: _Plan,
        candidate_by_key: Mapping[_StateKey, CaptureCandidate],
    ) -> SuccessfulCaptureRouteResult:
        producer_by_child = plan.producer_map
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
        candidates_by_id = {
            candidate.candidate_id: candidate for candidate in candidate_by_key.values()
        }
        requirements = tuple(
            CaptureRequirement(
                candidate_id=candidate_id,
                species=candidates_by_id[candidate_id].species,
                gender=candidates_by_id[candidate_id].gender,
            )
            for candidate_id in sorted(plan.captures)
        )
        return SuccessfulCaptureRouteResult(
            target=cls._state(plan.target, plan.generation),
            steps=tuple(steps),
            capture_requirements=requirements,
            cost=CaptureRouteCost(
                new_capture_count=len(requirements),
                generations=plan.generation,
                breeding_steps=len(steps),
            ),
        )
