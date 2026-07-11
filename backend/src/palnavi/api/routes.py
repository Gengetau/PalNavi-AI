"""HTTP route adapters for health and deterministic breeding planning."""

from fastapi import APIRouter

from palnavi.api.schemas import (
    HealthResponse,
    RouteCostResponse,
    RouteRequestBody,
    RouteResponse,
    RouteStepResponse,
)
from palnavi.application.fixtures import load_synthetic_dataset
from palnavi.domain.breeding import (
    BreedingRelationship,
    BreedingRoutePlanner,
    InvalidRouteResult,
    OwnedSpeciesInventory,
    RouteObjective,
    RoutePlanningRequest,
    SpeciesId,
    SuccessfulRouteResult,
    UnreachableRouteResult,
)

router = APIRouter()
planner = BreedingRoutePlanner()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.post("/api/v1/breeding/routes", response_model=RouteResponse)
def plan_breeding_route(body: RouteRequestBody) -> RouteResponse:
    data_source = "explicit-request"
    try:
        target = SpeciesId(body.target_id)
        inventory = OwnedSpeciesInventory.from_ids(
            {SpeciesId(species_id) for species_id in body.owned_species_ids}
        )
        if body.relationships is None:
            dataset = load_synthetic_dataset()
            relationships = dataset.relationships
            data_source = dataset.dataset_id
        else:
            relationships = tuple(
                BreedingRelationship(
                    parent_a=SpeciesId(item.parent_a),
                    parent_b=SpeciesId(item.parent_b),
                    child=SpeciesId(item.child),
                )
                for item in body.relationships
            )
    except (KeyError, OSError, TypeError, ValueError) as error:
        return RouteResponse(
            status="invalid",
            target_id=body.target_id,
            data_source=data_source,
            errors=[str(error)],
            message="request or relationship data is invalid",
        )

    result = planner.plan(
        RoutePlanningRequest(
            target=target,
            inventory=inventory,
            objective=RouteObjective(body.objective),
        ),
        relationships,
    )
    if isinstance(result, SuccessfulRouteResult):
        return RouteResponse(
            status="success",
            target_id=result.target.value,
            data_source=data_source,
            steps=[
                RouteStepResponse(
                    order=step.order,
                    generation=step.generation,
                    parent_a=step.parent_a.value,
                    parent_b=step.parent_b.value,
                    child=step.child.value,
                )
                for step in result.steps
            ],
            cost=RouteCostResponse(
                generations=result.cost.generations,
                breeding_steps=result.cost.breeding_steps,
                new_capture_count=result.cost.new_capture_count,
            ),
        )
    if isinstance(result, UnreachableRouteResult):
        return RouteResponse(
            status="unreachable",
            target_id=result.target.value,
            data_source=data_source,
            reachable_species_ids=[species.value for species in result.reachable_species],
            message=result.reason,
        )
    if isinstance(result, InvalidRouteResult):
        return RouteResponse(
            status="invalid",
            target_id=result.target.value,
            data_source=data_source,
            errors=list(result.errors),
            message="relationship set is invalid",
        )
    raise AssertionError("planner returned an unsupported result type")
