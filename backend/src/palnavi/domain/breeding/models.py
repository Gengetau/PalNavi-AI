"""Domain types for deterministic species-level breeding routes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

SPECIES_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
INSTANCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
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
class SpeciesGenderFeasibility:
    """Validated probability values used only to decide possible offspring genders."""

    species: SpeciesId
    male_probability: float
    female_probability: float

    def __post_init__(self) -> None:
        if not 0.0 < self.male_probability <= 1.0:
            raise ValueError("male probability must be in (0, 1]")
        if not 0.0 < self.female_probability <= 1.0:
            raise ValueError("female probability must be in (0, 1]")
        if abs(self.male_probability + self.female_probability - 1.0) > 1e-12:
            raise ValueError("male and female probabilities must sum to one")

    def supports(self, gender: InventoryGender) -> bool:
        if gender is InventoryGender.MALE:
            return self.male_probability > 0.0
        if gender is InventoryGender.FEMALE:
            return self.female_probability > 0.0
        return False


@dataclass(frozen=True, slots=True)
class OwnedBreedingCandidate:
    """One concrete inventory candidate with a stable caller-owned identity."""

    instance_id: str
    species: SpeciesId
    gender: InventoryGender

    def __post_init__(self) -> None:
        if not INSTANCE_ID_PATTERN.fullmatch(self.instance_id):
            raise ValueError("instance identifiers contain unsupported characters")


@dataclass(frozen=True, order=True, slots=True)
class GenderRouteState:
    """One gender-capable route node with explicit future constraint dimensions."""

    species: SpeciesId
    gender: InventoryGender
    required_passive_set: frozenset[str] = field(default_factory=frozenset)
    required_iv_constraints: tuple[str, ...] = ()
    generation_depth: int = 0

    def __post_init__(self) -> None:
        if self.gender is InventoryGender.UNKNOWN:
            raise ValueError("route states require a concrete gender")
        if self.required_passive_set or self.required_iv_constraints:
            raise ValueError("passive and IV route constraints are not supported")
        if self.generation_depth < 0:
            raise ValueError("route generation depth cannot be negative")


@dataclass(frozen=True, slots=True)
class GenderRoutePlanningRequest:
    target_species: SpeciesId
    target_gender: InventoryGender
    inventory: tuple[OwnedBreedingCandidate, ...]

    def __post_init__(self) -> None:
        if self.target_gender is InventoryGender.UNKNOWN:
            raise ValueError("route targets require a concrete gender")
        instance_ids = [candidate.instance_id for candidate in self.inventory]
        if len(instance_ids) != len(set(instance_ids)):
            raise ValueError("route inventory contains duplicate instance identifiers")


@dataclass(frozen=True, slots=True)
class GenderRouteStep:
    order: int
    generation: int
    parent_a: GenderRouteState
    parent_b: GenderRouteState
    child: GenderRouteState
    result_kind: BreedingResultKind
    source_record_hash: str

    def __post_init__(self) -> None:
        if self.order < 1 or self.generation < 1:
            raise ValueError("route step order and generation must be positive")
        if self.parent_a.gender is self.parent_b.gender:
            raise ValueError("route steps require opposite parent genders")
        if not SOURCE_RECORD_HASH_PATTERN.fullmatch(self.source_record_hash):
            raise ValueError("route steps require a source-record SHA-256")
        if self.child.generation_depth != self.generation:
            raise ValueError("child generation depth must match the route step")


@dataclass(frozen=True, slots=True)
class GenderRouteCost:
    generations: int
    breeding_steps: int
    probability_dependent_cost_available: bool = field(default=False, init=False)
    expected_attempts: None = field(default=None, init=False)


class GenderRouteStatus(StrEnum):
    SUCCESS = "success"
    GENDER_REQUIRED = "gender_required"
    UNREACHABLE = "unreachable"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class SuccessfulGenderRouteResult:
    target: GenderRouteState
    steps: tuple[GenderRouteStep, ...]
    cost: GenderRouteCost
    status: GenderRouteStatus = field(default=GenderRouteStatus.SUCCESS, init=False)


@dataclass(frozen=True, slots=True)
class GenderRequiredRouteResult:
    unknown_instance_ids: tuple[str, ...]
    reason: str
    status: GenderRouteStatus = field(default=GenderRouteStatus.GENDER_REQUIRED, init=False)


@dataclass(frozen=True, slots=True)
class UnreachableGenderRouteResult:
    target: GenderRouteState
    reachable_states: tuple[GenderRouteState, ...]
    reason: str
    status: GenderRouteStatus = field(default=GenderRouteStatus.UNREACHABLE, init=False)


@dataclass(frozen=True, slots=True)
class InvalidGenderRouteResult:
    target_species: SpeciesId
    errors: tuple[str, ...]
    status: GenderRouteStatus = field(default=GenderRouteStatus.INVALID, init=False)


GenderRouteResult = (
    SuccessfulGenderRouteResult
    | GenderRequiredRouteResult
    | UnreachableGenderRouteResult
    | InvalidGenderRouteResult
)


class CaptureRouteObjective(StrEnum):
    """The only exact hypothetical-acquisition objective supported by v1."""

    MINIMUM_NEW_CAPTURES = "minimum_new_captures"


@dataclass(frozen=True, slots=True)
class CaptureCandidate:
    """One user-asserted concrete individual that may be newly acquired."""

    candidate_id: str
    species: SpeciesId
    gender: InventoryGender

    def __post_init__(self) -> None:
        if not INSTANCE_ID_PATTERN.fullmatch(self.candidate_id):
            raise ValueError("candidate identifiers contain unsupported characters")
        if self.gender is InventoryGender.UNKNOWN:
            raise ValueError("capture candidates require a concrete gender")


@dataclass(frozen=True, slots=True)
class CaptureRoutePlanningRequest:
    target_species: SpeciesId
    target_gender: InventoryGender
    inventory: tuple[OwnedBreedingCandidate, ...]
    capture_candidates: tuple[CaptureCandidate, ...]
    objective: CaptureRouteObjective = CaptureRouteObjective.MINIMUM_NEW_CAPTURES

    def __post_init__(self) -> None:
        if self.target_gender is InventoryGender.UNKNOWN:
            raise ValueError("route targets require a concrete gender")
        if len(self.capture_candidates) > 16:
            raise ValueError("capture candidate count exceeds sixteen")

        instance_ids = [candidate.instance_id for candidate in self.inventory]
        if len(instance_ids) != len(set(instance_ids)):
            raise ValueError("route inventory contains duplicate instance identifiers")

        candidate_ids = [candidate.candidate_id for candidate in self.capture_candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("capture candidates contain duplicate candidate identifiers")
        if set(instance_ids).intersection(candidate_ids):
            raise ValueError("capture candidate identifiers collide with inventory identifiers")

        candidate_states = [
            (candidate.species, candidate.gender) for candidate in self.capture_candidates
        ]
        if len(candidate_states) != len(set(candidate_states)):
            raise ValueError("capture candidates contain duplicate species and gender states")


@dataclass(frozen=True, slots=True)
class CaptureRequirement:
    candidate_id: str
    species: SpeciesId
    gender: InventoryGender

    def __post_init__(self) -> None:
        if self.gender is InventoryGender.UNKNOWN:
            raise ValueError("capture requirements require a concrete gender")


@dataclass(frozen=True, slots=True)
class CaptureRouteCost:
    new_capture_count: int
    generations: int
    breeding_steps: int
    probability_dependent_cost_available: bool = field(default=False, init=False)
    expected_attempts: None = field(default=None, init=False)


class CaptureRouteStatus(StrEnum):
    SUCCESS = "success"
    GENDER_REQUIRED = "gender_required"
    UNREACHABLE = "unreachable"
    INVALID = "invalid"
    SEARCH_LIMIT_EXCEEDED = "search_limit_exceeded"


@dataclass(frozen=True, slots=True)
class SuccessfulCaptureRouteResult:
    target: GenderRouteState
    steps: tuple[GenderRouteStep, ...]
    capture_requirements: tuple[CaptureRequirement, ...]
    cost: CaptureRouteCost
    status: CaptureRouteStatus = field(default=CaptureRouteStatus.SUCCESS, init=False)


@dataclass(frozen=True, slots=True)
class CaptureGenderRequiredResult:
    unknown_instance_ids: tuple[str, ...]
    reason: str
    status: CaptureRouteStatus = field(
        default=CaptureRouteStatus.GENDER_REQUIRED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class UnreachableCaptureRouteResult:
    target: GenderRouteState
    reachable_states: tuple[GenderRouteState, ...]
    reason: str
    status: CaptureRouteStatus = field(
        default=CaptureRouteStatus.UNREACHABLE,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class InvalidCaptureRouteResult:
    target_species: SpeciesId
    errors: tuple[str, ...]
    status: CaptureRouteStatus = field(default=CaptureRouteStatus.INVALID, init=False)


@dataclass(frozen=True, slots=True)
class CaptureRouteSearchLimitExceeded:
    target_species: SpeciesId
    reason: str
    status: CaptureRouteStatus = field(
        default=CaptureRouteStatus.SEARCH_LIMIT_EXCEEDED,
        init=False,
    )


CaptureRouteResult = (
    SuccessfulCaptureRouteResult
    | CaptureGenderRequiredResult
    | UnreachableCaptureRouteResult
    | InvalidCaptureRouteResult
    | CaptureRouteSearchLimitExceeded
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
