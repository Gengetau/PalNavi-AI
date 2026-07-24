"""HTTP adapters for health and repository-backed deterministic planning."""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from palnavi.api.dependencies import (
    get_breeding_planning_service,
    get_direct_breeding_service,
    get_gender_route_planning_service,
    get_knowledge_explanation_service,
    get_knowledge_retrieval_service,
)
from palnavi.api.schemas import (
    DatasetMetadataResponse,
    DirectBreedingPossibleResultResponse,
    DirectBreedingRequestBody,
    DirectBreedingResponse,
    GameVersionScopeResponse,
    GenderRouteCostResponse,
    GenderRouteRequestBody,
    GenderRouteResponse,
    GenderRouteStateResponse,
    GenderRouteStepResponse,
    HealthResponse,
    KnowledgeCitationResponse,
    KnowledgeExplanationCitationResponse,
    KnowledgeExplanationErrorCategory,
    KnowledgeExplanationErrorResponse,
    KnowledgeExplanationRequestBody,
    KnowledgeExplanationSuccessResponse,
    KnowledgeExplanationTokenUsageResponse,
    KnowledgeExplanationUnsupportedResponse,
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
    DirectBreedingQueryFailure,
    DirectBreedingQueryFailureKind,
    DirectBreedingQuerySuccess,
    DirectBreedingService,
    GenderRoutePlanningFailure,
    GenderRoutePlanningFailureKind,
    GenderRoutePlanningService,
    GenderRoutePlanningSuccess,
    KnowledgeExplanationInvalidOutputFailure,
    KnowledgeExplanationModelFailure,
    KnowledgeExplanationRequest,
    KnowledgeExplanationRetrievalFailure,
    KnowledgeExplanationService,
    KnowledgeExplanationSuccess,
    KnowledgeExplanationUnsupported,
    KnowledgeRetrievalService,
    ModelErrorCategory,
    PlanningFailure,
    PlanningFailureKind,
    PlanningSuccess,
)
from palnavi.domain.breeding import (
    DirectBreedingGenderRequired,
    DirectBreedingInvalid,
    DirectBreedingNotFound,
    DirectBreedingRequest,
    DirectBreedingSuccess,
    GenderRequiredRouteResult,
    GenderRoutePlanningRequest,
    GenderRouteState,
    InvalidGenderRouteResult,
    InvalidRouteResult,
    InventoryGender,
    OwnedBreedingCandidate,
    OwnedSpeciesInventory,
    RouteObjective,
    RoutePlanningRequest,
    SpeciesId,
    SuccessfulGenderRouteResult,
    SuccessfulRouteResult,
    UnreachableGenderRouteResult,
    UnreachableRouteResult,
)
from palnavi.domain.data import BreedingDatasetSnapshot, DatasetValidationIssue
from palnavi.domain.knowledge import (
    KnowledgeQuery,
    KnowledgeRepositoryFailure,
    KnowledgeRepositoryFailureKind,
    KnowledgeSearchSuccess,
    LanguageIdentifier,
)

router = APIRouter()

_RETRIEVAL_FAILURE_RESPONSES: dict[
    KnowledgeRepositoryFailureKind,
    tuple[int, KnowledgeExplanationErrorCategory, str],
] = {
    KnowledgeRepositoryFailureKind.UNAVAILABLE: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "repository_unavailable",
        "Knowledge retrieval is unavailable.",
    ),
    KnowledgeRepositoryFailureKind.INVALID_STATE: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "repository_invalid_state",
        "Knowledge retrieval could not use the repository state.",
    ),
}

_MODEL_FAILURE_RESPONSES: dict[
    ModelErrorCategory,
    tuple[int, KnowledgeExplanationErrorCategory, str],
] = {
    ModelErrorCategory.CONFIGURATION_INVALID: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "configuration_invalid",
        "Model generation is not configured.",
    ),
    ModelErrorCategory.AUTHENTICATION_REJECTED: (
        status.HTTP_502_BAD_GATEWAY,
        "authentication_rejected",
        "Model authentication was rejected.",
    ),
    ModelErrorCategory.RATE_LIMITED: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "rate_limited",
        "Model generation is temporarily rate limited.",
    ),
    ModelErrorCategory.REQUEST_INVALID: (
        status.HTTP_502_BAD_GATEWAY,
        "request_invalid",
        "The model request was rejected.",
    ),
    ModelErrorCategory.TIMEOUT: (
        status.HTTP_504_GATEWAY_TIMEOUT,
        "timeout",
        "Model generation timed out.",
    ),
    ModelErrorCategory.PROVIDER_UNAVAILABLE: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "provider_unavailable",
        "The model provider is unavailable.",
    ),
    ModelErrorCategory.MALFORMED_RESPONSE: (
        status.HTTP_502_BAD_GATEWAY,
        "malformed_response",
        "The model provider returned an unusable response.",
    ),
    ModelErrorCategory.UNKNOWN_PROVIDER: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "unknown_provider",
        "The configured model provider is unsupported.",
    ),
}

_INVALID_GROUNDED_OUTPUT_MESSAGE = (
    "The model response could not be safely grounded in retrieved evidence."
)
_UNSUPPORTED_EXPLANATION_MESSAGE = "No usable knowledge evidence was found."


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.post(
    "/api/v1/breeding/direct",
    response_model=DirectBreedingResponse,
    responses={
        404: {"model": DirectBreedingResponse},
        422: {
            "model": DirectBreedingResponse | RequestValidationErrorResponse,
            "description": (
                "Palworld data validation error or FastAPI request-body validation error"
            ),
        },
    },
)
def query_direct_breeding(
    body: DirectBreedingRequestBody,
    response: Response,
    service: Annotated[DirectBreedingService, Depends(get_direct_breeding_service)],
) -> DirectBreedingResponse:
    try:
        request = DirectBreedingRequest(
            parent_a=SpeciesId(body.parent_a.species_id),
            parent_b=SpeciesId(body.parent_b.species_id),
            parent_a_gender=(
                InventoryGender(body.parent_a.gender)
                if body.query_mode == "concrete" and body.parent_a.gender is not None
                else None
            ),
            parent_b_gender=(
                InventoryGender(body.parent_b.gender)
                if body.query_mode == "concrete" and body.parent_b.gender is not None
                else None
            ),
        )
    except ValueError:
        response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return DirectBreedingResponse(
            status="invalid",
            dataset_id=body.dataset_id,
            error_category="request_invalid",
            errors=[
                ValidationIssueResponse(
                    code="invalid_species_identifier",
                    field="parent_a.species_id_or_parent_b.species_id",
                    message="request contains an invalid stable species identifier",
                )
            ],
            message="direct breeding request is invalid",
        )

    outcome = service.query(body.dataset_id, request)
    if isinstance(outcome, DirectBreedingQueryFailure):
        if outcome.kind is DirectBreedingQueryFailureKind.DATASET_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            issues = [
                ValidationIssueResponse(
                    code="dataset_not_found",
                    field="dataset_id",
                    message="requested dataset was not found",
                )
            ]
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
            issues = [_validation_issue_response(issue) for issue in outcome.issues]
        return DirectBreedingResponse(
            status="not_found"
            if outcome.kind is DirectBreedingQueryFailureKind.DATASET_NOT_FOUND
            else "invalid",
            dataset_id=outcome.dataset_id,
            error_category=outcome.kind.value,
            errors=issues,
            message="direct breeding data could not be validated",
        )
    if not isinstance(outcome, DirectBreedingQuerySuccess):
        raise AssertionError("direct breeding service returned an unsupported result type")

    result = outcome.result
    if isinstance(result, DirectBreedingSuccess):
        return DirectBreedingResponse(
            status="success",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            child_species_id=result.child.value,
            result_kind=result.result_kind.value,
            source_record_hash=result.source_record_hash,
        )
    if isinstance(result, DirectBreedingGenderRequired):
        return DirectBreedingResponse(
            status="gender_required",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            possible_results=[
                DirectBreedingPossibleResultResponse(
                    parent_a_gender=cast(
                        Literal["male", "female"],
                        item.parent_a_gender.value,
                    ),
                    parent_b_gender=cast(
                        Literal["male", "female"],
                        item.parent_b_gender.value,
                    ),
                    child_species_id=item.child.value,
                    result_kind=item.result_kind.value,
                    source_record_hash=item.source_record_hash,
                )
                for item in result.possible_results
            ],
            message=result.reason,
        )
    if isinstance(result, DirectBreedingInvalid):
        return DirectBreedingResponse(
            status="invalid",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            error_category="parent_pair_invalid",
            errors=[
                ValidationIssueResponse(
                    code="invalid_parent_pair",
                    field="parent_a.gender_or_parent_b.gender",
                    message=message,
                )
                for message in result.errors
            ],
            message="direct breeding parent pair is invalid",
        )
    if isinstance(result, DirectBreedingNotFound):
        return DirectBreedingResponse(
            status="not_found",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            error_category="rule_not_found",
            message=result.reason,
        )
    raise AssertionError("direct breeding index returned an unsupported result type")


@router.post(
    "/api/v1/breeding/gender-aware-routes",
    response_model=GenderRouteResponse,
    responses={
        404: {"model": GenderRouteResponse},
        422: {
            "model": GenderRouteResponse | RequestValidationErrorResponse,
            "description": (
                "Palworld data validation error or FastAPI request-body validation error"
            ),
        },
    },
)
def plan_gender_aware_route(
    body: GenderRouteRequestBody,
    response: Response,
    service: Annotated[
        GenderRoutePlanningService,
        Depends(get_gender_route_planning_service),
    ],
) -> GenderRouteResponse:
    try:
        request = GenderRoutePlanningRequest(
            target_species=SpeciesId(body.target.species_id),
            target_gender=InventoryGender(body.target.gender),
            inventory=tuple(
                OwnedBreedingCandidate(
                    instance_id=item.instance_id,
                    species=SpeciesId(item.species_id),
                    gender=InventoryGender(item.gender),
                )
                for item in body.inventory
            ),
        )
    except ValueError:
        response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return GenderRouteResponse(
            status="invalid",
            dataset_id=body.dataset_id,
            error_category="request_invalid",
            errors=[
                ValidationIssueResponse(
                    code="invalid_route_request",
                    field="target_or_inventory",
                    message="gender-aware route request contains invalid identifiers",
                )
            ],
            message="gender-aware route request is invalid",
        )

    outcome = service.plan(body.dataset_id, request)
    if isinstance(outcome, GenderRoutePlanningFailure):
        if outcome.kind is GenderRoutePlanningFailureKind.DATASET_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            issues = [
                ValidationIssueResponse(
                    code="dataset_not_found",
                    field="dataset_id",
                    message="requested dataset was not found",
                )
            ]
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
            issues = [_validation_issue_response(issue) for issue in outcome.issues]
        return GenderRouteResponse(
            status="invalid",
            dataset_id=outcome.dataset_id,
            error_category=outcome.kind.value,
            errors=issues,
            message="gender-aware route data could not be validated",
        )
    if not isinstance(outcome, GenderRoutePlanningSuccess):
        raise AssertionError("gender route service returned an unsupported result type")

    result = outcome.result
    if isinstance(result, SuccessfulGenderRouteResult):
        return GenderRouteResponse(
            status="success",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            target=_gender_route_state_response(result.target),
            steps=[
                GenderRouteStepResponse(
                    order=step.order,
                    generation=step.generation,
                    parent_a=_gender_route_state_response(step.parent_a),
                    parent_b=_gender_route_state_response(step.parent_b),
                    child=_gender_route_state_response(step.child),
                    result_kind=step.result_kind.value,
                    source_record_hash=step.source_record_hash,
                )
                for step in result.steps
            ],
            cost=GenderRouteCostResponse(
                generations=result.cost.generations,
                breeding_steps=result.cost.breeding_steps,
            ),
        )
    if isinstance(result, GenderRequiredRouteResult):
        return GenderRouteResponse(
            status="gender_required",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            unknown_instance_ids=list(result.unknown_instance_ids),
            message=result.reason,
        )
    if isinstance(result, UnreachableGenderRouteResult):
        return GenderRouteResponse(
            status="unreachable",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            target=_gender_route_state_response(result.target),
            reachable_states=[
                _gender_route_state_response(item) for item in result.reachable_states
            ],
            message=result.reason,
        )
    if isinstance(result, InvalidGenderRouteResult):
        response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return GenderRouteResponse(
            status="invalid",
            dataset_id=outcome.dataset_id,
            content_sha256=outcome.content_identity.digest,
            gender_data_content_sha256=outcome.gender_data_identity.digest,
            error_category="route_invalid",
            errors=[
                ValidationIssueResponse(
                    code="invalid_gender_route",
                    field="target_or_inventory_or_rules",
                    message=message,
                )
                for message in result.errors
            ],
            message="gender-aware route request or graph is invalid",
        )
    raise AssertionError("gender route planner returned an unsupported result type")


def _gender_route_state_response(state: GenderRouteState) -> GenderRouteStateResponse:
    return GenderRouteStateResponse(
        species_id=state.species.value,
        gender=cast(Literal["male", "female"], state.gender.value),
        required_passive_ids=sorted(state.required_passive_set),
        required_iv_constraints=list(state.required_iv_constraints),
        generation_depth=state.generation_depth,
    )


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
    "/api/v1/knowledge/explain",
    response_model=(KnowledgeExplanationSuccessResponse | KnowledgeExplanationUnsupportedResponse),
    responses={
        422: {
            "model": (KnowledgeExplanationErrorResponse | RequestValidationErrorResponse),
            "description": (
                "Knowledge explanation application validation error or FastAPI "
                "request-body validation error"
            ),
        },
        502: {
            "model": KnowledgeExplanationErrorResponse,
            "description": "Model provider or grounded-output failure",
        },
        503: {
            "model": KnowledgeExplanationErrorResponse,
            "description": "Knowledge retrieval or model availability failure",
        },
        504: {
            "model": KnowledgeExplanationErrorResponse,
            "description": "Model provider timeout",
        },
    },
)
async def explain_knowledge(
    body: KnowledgeExplanationRequestBody,
    service: Annotated[
        KnowledgeExplanationService,
        Depends(get_knowledge_explanation_service),
    ],
) -> KnowledgeExplanationSuccessResponse | KnowledgeExplanationUnsupportedResponse | JSONResponse:
    try:
        query = KnowledgeQuery(
            text=body.query,
            language=(LanguageIdentifier(body.language) if body.language is not None else None),
            exact_game_version=body.exact_game_version,
            synthetic_only=body.synthetic_only,
            limit=body.limit,
        )
    except ValueError:
        return _knowledge_explanation_error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "request_invalid",
            "Knowledge explanation request is invalid.",
        )

    outcome = await service.explain(KnowledgeExplanationRequest(query))
    if isinstance(outcome, KnowledgeExplanationSuccess):
        usage = (
            KnowledgeExplanationTokenUsageResponse(
                input_tokens=outcome.usage.input_tokens,
                output_tokens=outcome.usage.output_tokens,
                total_tokens=outcome.usage.total_tokens,
            )
            if outcome.usage is not None
            else None
        )
        return KnowledgeExplanationSuccessResponse(
            status="success",
            answer=outcome.answer,
            citations=[
                KnowledgeExplanationCitationResponse(
                    marker=item.marker,
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
                for item in outcome.citations
            ],
            usage=usage,
        )
    if isinstance(outcome, KnowledgeExplanationUnsupported):
        return KnowledgeExplanationUnsupportedResponse(
            status="unsupported",
            message=_UNSUPPORTED_EXPLANATION_MESSAGE,
        )
    if isinstance(outcome, KnowledgeExplanationRetrievalFailure):
        response_spec = _RETRIEVAL_FAILURE_RESPONSES[outcome.kind]
        return _knowledge_explanation_error_response(*response_spec)
    if isinstance(outcome, KnowledgeExplanationModelFailure):
        response_spec = _MODEL_FAILURE_RESPONSES[outcome.category]
        return _knowledge_explanation_error_response(*response_spec)
    if isinstance(outcome, KnowledgeExplanationInvalidOutputFailure):
        return _knowledge_explanation_error_response(
            status.HTTP_502_BAD_GATEWAY,
            "invalid_grounded_output",
            _INVALID_GROUNDED_OUTPUT_MESSAGE,
        )
    raise AssertionError("knowledge explanation service returned an unsupported outcome")


def _knowledge_explanation_error_response(
    status_code: int,
    error_category: KnowledgeExplanationErrorCategory,
    message: str,
) -> JSONResponse:
    payload = KnowledgeExplanationErrorResponse(
        status="error",
        error_category=error_category,
        message=message,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
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
