"""HTTP request and response schemas; domain logic does not depend on these types."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BreedingResultKindValue = Literal[
    "same_species",
    "ordinary_power",
    "fixed_special",
    "gender_directed",
]


class RelationshipInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_a: str
    parent_b: str
    child: str


class RouteRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    owned_species_ids: list[str] = Field(default_factory=list)
    objective: Literal["minimum_generations"] = "minimum_generations"
    fixture: str = Field(default="synthetic-v1", min_length=1, max_length=64)
    relationships: list[RelationshipInput] | None = None


class RouteStepResponse(BaseModel):
    order: int
    generation: int
    parent_a: str
    parent_b: str
    child: str


class RouteCostResponse(BaseModel):
    generations: int
    breeding_steps: int
    new_capture_count: int


class ValidationIssueResponse(BaseModel):
    code: str
    field: str
    message: str


class GameVersionScopeResponse(BaseModel):
    kind: str
    value: str | None


class ProvenanceResponse(BaseModel):
    source_id: str
    source_type: str
    locator: str
    retrieved_at: str
    license_or_usage_note: str
    evidence_quality: str


class DatasetMetadataResponse(BaseModel):
    dataset_id: str
    schema_version: int
    classification: str
    game_version_scope: GameVersionScopeResponse
    created_at: str
    importer_version: str
    validation_status: str
    provenance: list[ProvenanceResponse]
    content_sha256: str


class RouteResponse(BaseModel):
    status: Literal["success", "unreachable", "invalid"]
    target_id: str
    data_source: str
    dataset: DatasetMetadataResponse | None = None
    steps: list[RouteStepResponse] = Field(default_factory=list)
    cost: RouteCostResponse | None = None
    reachable_species_ids: list[str] = Field(default_factory=list)
    error_category: str | None = None
    errors: list[ValidationIssueResponse] = Field(default_factory=list)
    message: str | None = None


class DirectBreedingParentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_id: str
    gender: Literal["male", "female", "unknown"] | None = None


class DirectBreedingRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1, max_length=128)
    query_mode: Literal["concrete", "species_only"] = "concrete"
    parent_a: DirectBreedingParentInput
    parent_b: DirectBreedingParentInput

    @model_validator(mode="after")
    def validate_gender_shape(self) -> DirectBreedingRequestBody:
        parent_fields = (self.parent_a.model_fields_set, self.parent_b.model_fields_set)
        genders = (self.parent_a.gender, self.parent_b.gender)
        if self.query_mode == "concrete":
            if any("gender" not in fields for fields in parent_fields) or any(
                gender is None for gender in genders
            ):
                raise ValueError("concrete queries require both parent genders")
        elif any("gender" in fields for fields in parent_fields):
            raise ValueError("species-only queries must omit both parent genders")
        return self


class DirectBreedingPossibleResultResponse(BaseModel):
    parent_a_gender: Literal["male", "female"]
    parent_b_gender: Literal["male", "female"]
    child_species_id: str
    result_kind: BreedingResultKindValue
    source_record_hash: str


class DirectBreedingResponse(BaseModel):
    status: Literal["success", "gender_required", "invalid", "not_found"]
    dataset_id: str
    content_sha256: str | None = None
    gender_data_content_sha256: str | None = None
    child_species_id: str | None = None
    result_kind: BreedingResultKindValue | None = None
    source_record_hash: str | None = None
    possible_results: list[DirectBreedingPossibleResultResponse] = Field(default_factory=list)
    error_category: str | None = None
    errors: list[ValidationIssueResponse] = Field(default_factory=list)
    message: str | None = None


class GenderRouteTargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_id: str
    gender: Literal["male", "female"]


class GenderRouteInventoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: str
    species_id: str
    gender: Literal["male", "female", "unknown"]


class GenderRouteRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1, max_length=128)
    target: GenderRouteTargetInput
    inventory: list[GenderRouteInventoryInput] = Field(max_length=299)
    objective: Literal["minimum_generations"] = "minimum_generations"


class GenderRouteStateResponse(BaseModel):
    species_id: str
    gender: Literal["male", "female"]
    required_passive_ids: list[str] = Field(default_factory=list)
    required_iv_constraints: list[str] = Field(default_factory=list)
    generation_depth: int


class GenderRouteStepResponse(BaseModel):
    order: int
    generation: int
    parent_a: GenderRouteStateResponse
    parent_b: GenderRouteStateResponse
    child: GenderRouteStateResponse
    result_kind: BreedingResultKindValue
    source_record_hash: str


class GenderRouteCostResponse(BaseModel):
    generations: int
    breeding_steps: int
    probability_dependent_cost_available: Literal[False] = False
    expected_attempts: None = None


class GenderRouteResponse(BaseModel):
    status: Literal["success", "gender_required", "unreachable", "invalid"]
    dataset_id: str
    content_sha256: str | None = None
    gender_data_content_sha256: str | None = None
    target: GenderRouteStateResponse | None = None
    steps: list[GenderRouteStepResponse] = Field(default_factory=list)
    cost: GenderRouteCostResponse | None = None
    reachable_states: list[GenderRouteStateResponse] = Field(default_factory=list)
    unknown_instance_ids: list[str] = Field(default_factory=list)
    error_category: str | None = None
    errors: list[ValidationIssueResponse] = Field(default_factory=list)
    message: str | None = None


class SpeciesCatalogRecordResponse(BaseModel):
    species_id: str
    paldeck_number: int
    paldeck_suffix: str | None
    is_variant: bool
    localized_names: dict[str, str]
    source_record_sha256: str


class SpeciesCatalogResponse(BaseModel):
    status: Literal["success", "not_found", "invalid"]
    dataset_id: str
    content_sha256: str | None = None
    locale_tags: list[str] = Field(default_factory=list)
    records: list[SpeciesCatalogRecordResponse] = Field(default_factory=list)
    error_category: str | None = None
    errors: list[ValidationIssueResponse] = Field(default_factory=list)
    message: str | None = None


class RequestValidationErrorDetail(BaseModel):
    """FastAPI-compatible detail item returned before route execution."""

    type: str
    loc: list[str | int]
    msg: str
    input: object | None = None
    ctx: dict[str, object] | None = None


class RequestValidationErrorResponse(BaseModel):
    detail: list[RequestValidationErrorDetail]


class HealthResponse(BaseModel):
    status: Literal["healthy"]


class KnowledgeSearchRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=35,
        pattern=r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$",
    )
    exact_game_version: str | None = Field(default=None, min_length=1, max_length=64)
    synthetic_only: bool = False
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeCitationResponse(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    section_path: list[str]
    source_id: str
    source_locator: str
    retrieved_at: str
    license_or_usage_note: str


class KnowledgeSearchItemResponse(BaseModel):
    score: float
    document_id: str
    chunk_id: str
    title: str
    section_path: list[str]
    text: str
    language: str
    classification: str
    game_version_scope: GameVersionScopeResponse
    citation: KnowledgeCitationResponse


class KnowledgeSearchResponse(BaseModel):
    status: Literal["success", "error"]
    results: list[KnowledgeSearchItemResponse] = Field(default_factory=list)
    error_category: str | None = None
    message: str | None = None


KnowledgeExplanationErrorCategory = Literal[
    "request_invalid",
    "repository_unavailable",
    "repository_invalid_state",
    "configuration_invalid",
    "authentication_rejected",
    "rate_limited",
    "timeout",
    "provider_unavailable",
    "malformed_response",
    "unknown_provider",
    "invalid_grounded_output",
]


class KnowledgeExplanationRequestBody(KnowledgeSearchRequestBody):
    pass


class KnowledgeExplanationCitationResponse(BaseModel):
    marker: str = Field(pattern=r"^\[K[1-9][0-9]*\]$")
    citation: KnowledgeCitationResponse


class KnowledgeExplanationTokenUsageResponse(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class KnowledgeExplanationSuccessResponse(BaseModel):
    status: Literal["success"]
    answer: str = Field(min_length=1)
    citations: list[KnowledgeExplanationCitationResponse] = Field(min_length=1)
    usage: KnowledgeExplanationTokenUsageResponse | None = None


class KnowledgeExplanationUnsupportedResponse(BaseModel):
    status: Literal["unsupported"]
    message: str


class KnowledgeExplanationErrorResponse(BaseModel):
    status: Literal["error"]
    error_category: KnowledgeExplanationErrorCategory
    message: str


KnowledgeExplanationResponse = (
    KnowledgeExplanationSuccessResponse
    | KnowledgeExplanationUnsupportedResponse
    | KnowledgeExplanationErrorResponse
)
