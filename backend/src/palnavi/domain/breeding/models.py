"""Domain types for deterministic species-level breeding routes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

SPECIES_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SOURCE_RECORD_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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


class GenderConstraint(StrEnum):
    """A source-rule constraint; wildcard rules are independent of parent sex."""

    MALE = "male"
    FEMALE = "female"
    WILDCARD = "wildcard"


class InventoryGender(StrEnum):
    """The only supported gender states for a concrete inventory candidate."""

    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class BreedingResultKind(StrEnum):
    SAME_SPECIES = "same_species"
    ORDINARY_POWER = "ordinary_power"
    FIXED_SPECIAL = "fixed_special"
    GENDER_DIRECTED = "gender_directed"


@dataclass(frozen=True, slots=True)
class BreedingParentConstraint:
    species: SpeciesId
    gender: GenderConstraint


@dataclass(frozen=True, slots=True)
class BreedingRule:
    """A source-bound direct breeding fact that preserves parent/gender association."""

    source_dataset_id: str
    source_record_hash: str
    parent_a: BreedingParentConstraint
    parent_b: BreedingParentConstraint
    child: SpeciesId
    result_kind: BreedingResultKind

    def __post_init__(self) -> None:
        if not self.source_dataset_id:
            raise ValueError("breeding rule requires a source dataset identity")
        if not SOURCE_RECORD_HASH_PATTERN.fullmatch(self.source_record_hash):
            raise ValueError("breeding rule requires a lowercase SHA-256 source record hash")
        constraints = {self.parent_a.gender, self.parent_b.gender}
        if self.result_kind is BreedingResultKind.GENDER_DIRECTED:
            if constraints != {GenderConstraint.MALE, GenderConstraint.FEMALE}:
                raise ValueError("gender-directed rules require one male and one female parent")
        elif constraints != {GenderConstraint.WILDCARD}:
            raise ValueError("non-directed rules require wildcard parent constraints")


@dataclass(frozen=True, slots=True)
class DirectBreedingRequest:
    parent_a: SpeciesId
    parent_b: SpeciesId
    parent_a_gender: InventoryGender | None = None
    parent_b_gender: InventoryGender | None = None


@dataclass(frozen=True, slots=True)
class DirectBreedingPossibility:
    parent_a_gender: InventoryGender
    parent_b_gender: InventoryGender
    child: SpeciesId
    result_kind: BreedingResultKind
    source_record_hash: str


class DirectBreedingStatus(StrEnum):
    SUCCESS = "success"
    GENDER_REQUIRED = "gender_required"
    INVALID = "invalid"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class DirectBreedingSuccess:
    child: SpeciesId
    result_kind: BreedingResultKind
    source_record_hash: str
    status: DirectBreedingStatus = field(default=DirectBreedingStatus.SUCCESS, init=False)


@dataclass(frozen=True, slots=True)
class DirectBreedingGenderRequired:
    possible_results: tuple[DirectBreedingPossibility, ...]
    reason: str
    status: DirectBreedingStatus = field(
        default=DirectBreedingStatus.GENDER_REQUIRED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class DirectBreedingInvalid:
    errors: tuple[str, ...]
    status: DirectBreedingStatus = field(default=DirectBreedingStatus.INVALID, init=False)


@dataclass(frozen=True, slots=True)
class DirectBreedingNotFound:
    reason: str
    status: DirectBreedingStatus = field(default=DirectBreedingStatus.NOT_FOUND, init=False)


DirectBreedingResult = (
    DirectBreedingSuccess
    | DirectBreedingGenderRequired
    | DirectBreedingInvalid
    | DirectBreedingNotFound
)


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
