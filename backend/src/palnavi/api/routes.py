"""HTTP adapters for health and repository-backed deterministic planning."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from palnavi.api.dependencies import (
    get_breeding_planning_service,
    get_knowledge_retrieval_service,
)
from palnavi.api.schemas import (
    DatasetMetadataResponse,
    GameVersionScopeResponse,
    HealthResponse,
    KnowledgeCitationResponse,
    KnowledgeSearchItemResponse,
    KnowledgeSearchRequestBody,
    KnowledgeSearchResponse,
    ProvenanceResponse,
    RequestValidationErrorResponse,
    RouteCostResponse,
    RouteRequestBody,
    RouteResponse,
    RouteStepResponse,
    ValidationIssueResponse,
)
from palnavi.application import (
    BreedingPlanningService,
    KnowledgeRetrievalService,
    PlanningFailure,
    PlanningFailureKind,
    PlanningSuccess,
)
from palnavi.domain.breeding import (
    InvalidRouteResult,
    OwnedSpeciesInventory,
    RouteObjective,
    RoutePlanningRequest,
    SpeciesId,
    SuccessfulRouteResult,
    UnreachableRouteResult,
)
from palnavi.domain.data import BreedingDatasetSnapshot, DatasetValidationIssue
from palnavi.domain.knowledge import (
    KnowledgeQuery,
    KnowledgeRepositoryFailure,
    KnowledgeSearchSuccess,
    LanguageIdentifier,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.post(
    "/api/v1/knowledge/search",
    response_model=KnowledgeSearchResponse,
    responses={
        422: {"model": KnowledgeSearchResponse | RequestValidationErrorResponse},
        503: {"model": KnowledgeSearchResponse},
    },
)
def search_knowledge(
    body: KnowledgeSearchRequestBody,
    response: Response,
    service: Annotated[
        KnowledgeRetrievalService,
        Depends(get_knowledge_retrieval_service),
    ],
) -> KnowledgeSearchResponse:
    try:
        query = KnowledgeQuery(
            text=body.query,
            language=LanguageIdentifier(body.language) if body.language is not None else None,
            exact_game_version=body.exact_game_version,
            synthetic_only=body.synthetic_only,
            limit=body.limit,
        )
    except ValueError:
        response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return KnowledgeSearchResponse(
            status="error",
            error_category="request_invalid",
            message="knowledge search request is invalid",
        )

    outcome = service.search(query)
    if isinstance(outcome, KnowledgeRepositoryFailure):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return KnowledgeSearchResponse(
            status="error",
            error_category=outcome.kind.value,
            message=outcome.message,
        )
    if not isinstance(outcome, KnowledgeSearchSuccess):
        raise AssertionError("knowledge repository returned an unsupported result type")
    return KnowledgeSearchResponse(
        status="success",
        results=[
            KnowledgeSearchItemResponse(
                score=item.score,
                document_id=item.document_id.value,
                chunk_id=item.chunk_id.value,
                title=item.title,
                section_path=list(item.section_path),
                text=item.text,
                language=item.language.value,
                classification=item.classification.value,
                game_version_scope=GameVersionScopeResponse(
                    kind=item.game_version_scope.kind.value,
                    value=item.game_version_scope.value,
                ),
                citation=KnowledgeCitationResponse(
                    document_id=item.citation.document_id.value,
                    chunk_id=item.citation.chunk_id.value,
                    title=item.citation.title,
                    section_path=list(item.citation.section_path),
                    source_id=item.citation.source_id,
                    source_locator=item.citation.source_locator,
                    retrieved_at=item.citation.retrieved_at.isoformat(),
                    license_or_usage_note=item.citation.license_or_usage_note,
                ),
            )
            for item in outcome.results
        ],
    )


@router.post(
    "/api/v1/breeding/routes",
    response_model=RouteResponse,
    responses={
        404: {"model": RouteResponse},
        422: {
            "model": RouteResponse | RequestValidationErrorResponse,
            "description": (
                "PalNavi data validation error or FastAPI request-body validation error"
            ),
        },
    },
)
def plan_breeding_route(
    body: RouteRequestBody,
    response: Response,
    service: Annotated[
        BreedingPlanningService,
        Depends(get_breeding_planning_service),
    ],
) -> RouteResponse:
    try:
        target = SpeciesId(body.target_id)
        inventory = OwnedSpeciesInventory.from_ids(
            {SpeciesId(species_id) for species_id in body.owned_species_ids}
        )
    except ValueError:
        return RouteResponse(
            status="invalid",
            target_id=body.target_id,
            data_source=(body.fixture if body.relationships is None else "explicit-request"),
            error_category="request_invalid",
            errors=[
                ValidationIssueResponse(
                    code="invalid_species_identifier",
                    field="target_id_or_owned_species_ids",
                    message="request contains an invalid stable species identifier",
                )
            ],
            message="request or relationship data is invalid",
        )

    request = RoutePlanningRequest(
        target=target,
        inventory=inventory,
        objective=RouteObjective(body.objective),
    )
    if body.relationships is None:
        outcome = service.plan_from_dataset(request=request, dataset_id=body.fixture)
    else:
        rows = [item.model_dump() for item in body.relationships]
        outcome = service.plan_from_explicit_relationships(request, rows)

    if isinstance(outcome, PlanningFailure):
        return _planning_failure_response(body, response, outcome)
    if not isinstance(outcome, PlanningSuccess):
        raise AssertionError("planning service returned an unsupported result type")

    result = outcome.route_result
    dataset_response = _dataset_metadata_response(outcome.dataset)
    data_source = outcome.dataset.metadata.dataset_id if outcome.dataset else "explicit-request"
    if isinstance(result, SuccessfulRouteResult):
        return RouteResponse(
            status="success",
            target_id=result.target.value,
            data_source=data_source,
            dataset=dataset_response,
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
            dataset=dataset_response,
            reachable_species_ids=[species.value for species in result.reachable_species],
            message=result.reason,
        )
    if isinstance(result, InvalidRouteResult):
        return RouteResponse(
            status="invalid",
            target_id=result.target.value,
            data_source=data_source,
            dataset=dataset_response,
            error_category="route_invalid",
            errors=[
                ValidationIssueResponse(
                    code="invalid_route_relationships",
                    field="relationships",
                    message=message,
                )
                for message in result.errors
            ],
            message="relationship set is invalid",
        )
    raise AssertionError("planner returned an unsupported result type")


def _planning_failure_response(
    body: RouteRequestBody,
    response: Response,
    failure: PlanningFailure,
) -> RouteResponse:
    if failure.kind is PlanningFailureKind.DATASET_NOT_FOUND:
        response.status_code = status.HTTP_404_NOT_FOUND
        errors = [
            ValidationIssueResponse(
                code="dataset_not_found",
                field="fixture",
                message="requested dataset was not found",
            )
        ]
    else:
        response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        errors = [_validation_issue_response(issue) for issue in failure.issues]

    return RouteResponse(
        status="invalid",
        target_id=body.target_id,
        data_source=failure.data_source,
        error_category=failure.kind.value,
        errors=errors,
        message="breeding data could not be validated for planning",
    )


def _dataset_metadata_response(
    dataset: BreedingDatasetSnapshot | None,
) -> DatasetMetadataResponse | None:
    if dataset is None:
        return None
    metadata = dataset.metadata
    return DatasetMetadataResponse(
        dataset_id=metadata.dataset_id,
        schema_version=metadata.schema_version,
        classification=metadata.classification.value,
        game_version_scope=GameVersionScopeResponse(
            kind=metadata.game_version_scope.kind.value,
            value=metadata.game_version_scope.value,
        ),
        created_at=metadata.created_at.isoformat(),
        importer_version=metadata.importer_version,
        validation_status=metadata.validation_status.value,
        provenance=[
            ProvenanceResponse(
                source_id=record.source_id,
                source_type=record.source_type.value,
                locator=record.locator,
                retrieved_at=record.retrieved_at.isoformat(),
                license_or_usage_note=record.license_or_usage_note,
                evidence_quality=record.evidence_quality.value,
            )
            for record in metadata.provenance
        ],
        content_sha256=metadata.content_identity.digest,
    )


def _validation_issue_response(issue: DatasetValidationIssue) -> ValidationIssueResponse:
    return ValidationIssueResponse(
        code=issue.code.value,
        field=issue.field,
        message=issue.message,
    )
