"""HTTP request and response schemas; domain logic does not depend on these types."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
