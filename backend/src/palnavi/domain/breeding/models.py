"""Domain types for deterministic species-level breeding routes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

SPECIES_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True, order=True, slots=True)
class SpeciesId:
    """A stable internal identifier, independent from localized display names."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not SPECIES_ID_PATTERN.fullmatch(self.value):
            raise ValueError("species identifiers must match ^[a-z][a-z0-9_]{0,63}$")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class BreedingRelationship:
    """An unordered parent pair with one deterministic child species."""

    parent_a: SpeciesId
    parent_b: SpeciesId
    child: SpeciesId

    def __post_init__(self) -> None:
        if self.parent_b < self.parent_a:
            original_a = self.parent_a
            object.__setattr__(self, "parent_a", self.parent_b)
            object.__setattr__(self, "parent_b", original_a)

    @property
    def parent_key(self) -> tuple[SpeciesId, SpeciesId]:
        return (self.parent_a, self.parent_b)


@dataclass(frozen=True, slots=True)
class OwnedSpeciesInventory:
    """Species known to be available before route execution begins."""

    species: frozenset[SpeciesId]

    @classmethod
    def from_ids(cls, species: set[SpeciesId] | frozenset[SpeciesId]) -> OwnedSpeciesInventory:
        return cls(frozenset(species))


class RouteObjective(StrEnum):
    MINIMUM_GENERATIONS = "minimum_generations"


@dataclass(frozen=True, slots=True)
class RoutePlanningRequest:
    target: SpeciesId
    inventory: OwnedSpeciesInventory
    objective: RouteObjective = RouteObjective.MINIMUM_GENERATIONS


@dataclass(frozen=True, slots=True)
class RouteStep:
    order: int
    generation: int
    parent_a: SpeciesId
    parent_b: SpeciesId
    child: SpeciesId


@dataclass(frozen=True, slots=True)
class RouteCost:
    """Extensible route costs; capture optimization is intentionally not implemented yet."""

    generations: int
    breeding_steps: int
    new_capture_count: int


class RouteStatus(StrEnum):
    SUCCESS = "success"
    UNREACHABLE = "unreachable"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class SuccessfulRouteResult:
    target: SpeciesId
    steps: tuple[RouteStep, ...]
    cost: RouteCost
    status: RouteStatus = field(default=RouteStatus.SUCCESS, init=False)


@dataclass(frozen=True, slots=True)
class UnreachableRouteResult:
    target: SpeciesId
    reachable_species: tuple[SpeciesId, ...]
    reason: str
    status: RouteStatus = field(default=RouteStatus.UNREACHABLE, init=False)


@dataclass(frozen=True, slots=True)
class InvalidRouteResult:
    target: SpeciesId
    errors: tuple[str, ...]
    status: RouteStatus = field(default=RouteStatus.INVALID, init=False)


RouteResult = SuccessfulRouteResult | UnreachableRouteResult | InvalidRouteResult
