"""Deterministic minimum-generation route search over explicit relationships."""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import count

from palnavi.domain.breeding.models import (
    BreedingRelationship,
    InvalidRouteResult,
    RouteCost,
    RoutePlanningRequest,
    RouteResult,
    RouteStep,
    SpeciesId,
    SuccessfulRouteResult,
    UnreachableRouteResult,
)

RouteSignature = tuple[tuple[int, str, str, str], ...]
Priority = tuple[int, int, RouteSignature]
StateKey = tuple[tuple[SpeciesId, int], ...]


@dataclass(frozen=True, slots=True)
class _SearchState:
    available: frozenset[SpeciesId]
    generations: StateKey
    steps: tuple[RouteStep, ...]

    def generation_map(self) -> dict[SpeciesId, int]:
        return dict(self.generations)


class BreedingRoutePlanner:
    """Find an executable route, minimizing depth before step count and stable signature."""

    def plan(
        self,
        request: RoutePlanningRequest,
        relationships: Iterable[BreedingRelationship],
    ) -> RouteResult:
        normalized, errors = self._normalize_relationships(relationships)
        if errors:
            return InvalidRouteResult(target=request.target, errors=errors)

        owned = request.inventory.species
        if request.target in owned:
            return SuccessfulRouteResult(
                target=request.target,
                steps=(),
                cost=RouteCost(generations=0, breeding_steps=0, new_capture_count=0),
            )

        reachable = self._reachable_closure(owned, normalized)
        if request.target not in reachable:
            return UnreachableRouteResult(
                target=request.target,
                reachable_species=tuple(sorted(reachable)),
                reason=(
                    "target cannot be produced from the supplied owned species and relationships"
                ),
            )

        return self._search(request, normalized)

    @staticmethod
    def _normalize_relationships(
        relationships: Iterable[BreedingRelationship],
    ) -> tuple[tuple[BreedingRelationship, ...], tuple[str, ...]]:
        by_parents: dict[tuple[SpeciesId, SpeciesId], BreedingRelationship] = {}
        errors: list[str] = []

        for relationship in relationships:
            existing = by_parents.get(relationship.parent_key)
            if existing is not None and existing.child != relationship.child:
                errors.append(
                    "conflicting children for parent pair "
                    f"{relationship.parent_a}+{relationship.parent_b}: "
                    f"{existing.child} and {relationship.child}"
                )
                continue
            by_parents[relationship.parent_key] = relationship

        ordered = tuple(
            sorted(
                by_parents.values(),
                key=lambda item: (
                    item.child.value,
                    item.parent_a.value,
                    item.parent_b.value,
                ),
            )
        )
        return ordered, tuple(sorted(set(errors)))

    @staticmethod
    def _reachable_closure(
        owned: frozenset[SpeciesId],
        relationships: tuple[BreedingRelationship, ...],
    ) -> frozenset[SpeciesId]:
        reachable = set(owned)
        changed = True
        while changed:
            changed = False
            for relationship in relationships:
                if (
                    relationship.parent_a in reachable
                    and relationship.parent_b in reachable
                    and relationship.child not in reachable
                ):
                    reachable.add(relationship.child)
                    changed = True
        return frozenset(reachable)

    def _search(
        self,
        request: RoutePlanningRequest,
        relationships: tuple[BreedingRelationship, ...],
    ) -> SuccessfulRouteResult:
        initial_generations = tuple((species, 0) for species in sorted(request.inventory.species))
        initial = _SearchState(
            available=request.inventory.species,
            generations=initial_generations,
            steps=(),
        )
        serial = count()
        heap: list[tuple[Priority, int, _SearchState]] = [((0, 0, ()), next(serial), initial)]
        best: dict[StateKey, Priority] = {initial.generations: (0, 0, ())}

        while heap:
            priority, _, state = heapq.heappop(heap)
            if best.get(state.generations) != priority:
                continue
            if request.target in state.available:
                return SuccessfulRouteResult(
                    target=request.target,
                    steps=state.steps,
                    cost=RouteCost(
                        generations=priority[0],
                        breeding_steps=len(state.steps),
                        new_capture_count=0,
                    ),
                )

            generation_by_species = state.generation_map()
            for relationship in relationships:
                if relationship.child in state.available:
                    continue
                if (
                    relationship.parent_a not in state.available
                    or relationship.parent_b not in state.available
                ):
                    continue

                child_generation = 1 + max(
                    generation_by_species[relationship.parent_a],
                    generation_by_species[relationship.parent_b],
                )
                step = RouteStep(
                    order=len(state.steps) + 1,
                    generation=child_generation,
                    parent_a=relationship.parent_a,
                    parent_b=relationship.parent_b,
                    child=relationship.child,
                )
                steps = (*state.steps, step)
                signature = self._signature(steps)
                next_priority: Priority = (
                    max(priority[0], child_generation),
                    len(steps),
                    signature,
                )
                next_generation_map = dict(generation_by_species)
                next_generation_map[relationship.child] = child_generation
                next_generations = tuple(sorted(next_generation_map.items()))

                previous = best.get(next_generations)
                if previous is not None and previous <= next_priority:
                    continue

                best[next_generations] = next_priority
                next_state = _SearchState(
                    available=state.available | {relationship.child},
                    generations=next_generations,
                    steps=steps,
                )
                heapq.heappush(heap, (next_priority, next(serial), next_state))

        raise RuntimeError("reachable closure and route search produced inconsistent results")

    @staticmethod
    def _signature(steps: tuple[RouteStep, ...]) -> RouteSignature:
        return tuple(
            (
                step.generation,
                step.parent_a.value,
                step.parent_b.value,
                step.child.value,
            )
            for step in steps
        )
