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
    fixture: Literal["synthetic-v1"] = "synthetic-v1"
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


class RouteResponse(BaseModel):
    status: Literal["success", "unreachable", "invalid"]
    target_id: str
    data_source: str
    steps: list[RouteStepResponse] = Field(default_factory=list)
    cost: RouteCostResponse | None = None
    reachable_species_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    message: str | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy"]
