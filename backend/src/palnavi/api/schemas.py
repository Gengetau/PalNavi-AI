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


class HealthResponse(BaseModel):
    status: Literal["healthy"]
