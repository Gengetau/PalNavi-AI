import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from palnavi.api.schemas import (
    DirectBreedingRequestBody,
    DirectBreedingResponse,
    GenderRouteRequestBody,
    GenderRouteResponse,
    KnowledgeExplanationErrorResponse,
    KnowledgeExplanationRequestBody,
    KnowledgeExplanationSuccessResponse,
    KnowledgeExplanationUnsupportedResponse,
    KnowledgeSearchRequestBody,
    KnowledgeSearchResponse,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "tests"
    / "golden"
    / "knowledge-contracts.json"
)


def test_frontend_golden_fixtures_match_backend_pydantic_contracts() -> None:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    request_json = json.dumps(fixtures["request"])

    for request_model in (
        KnowledgeSearchRequestBody,
        KnowledgeExplanationRequestBody,
    ):
        parsed_request = request_model.model_validate_json(request_json, strict=True)
        assert parsed_request.model_dump(mode="json") == fixtures["request"]

    KnowledgeSearchResponse.model_validate_json(json.dumps(fixtures["search_success"]), strict=True)
    KnowledgeSearchResponse.model_validate_json(json.dumps(fixtures["search_error"]), strict=True)
    KnowledgeExplanationSuccessResponse.model_validate_json(
        json.dumps(fixtures["explain_success"]), strict=True
    )
    KnowledgeExplanationUnsupportedResponse.model_validate_json(
        json.dumps(fixtures["explain_unsupported"]), strict=True
    )
    KnowledgeExplanationErrorResponse.model_validate_json(
        json.dumps(fixtures["explain_error"]), strict=True
    )
    direct_request = DirectBreedingRequestBody.model_validate_json(
        json.dumps(fixtures["direct_request"]),
        strict=True,
    )
    assert direct_request.model_dump(mode="json") == fixtures["direct_request"]
    for fixture_name in (
        "direct_success",
        "direct_gender_required",
        "direct_invalid",
        "direct_not_found",
    ):
        DirectBreedingResponse.model_validate_json(
            json.dumps(fixtures[fixture_name]),
            strict=True,
        )
    gender_route_request = GenderRouteRequestBody.model_validate_json(
        json.dumps(fixtures["gender_route_request"]),
        strict=True,
    )
    assert gender_route_request.model_dump(mode="json") == fixtures["gender_route_request"]
    for fixture_name in (
        "gender_route_success",
        "gender_route_gender_required",
    ):
        GenderRouteResponse.model_validate_json(
            json.dumps(fixtures[fixture_name]),
            strict=True,
        )


def test_frontend_golden_request_rejects_backend_type_coercion() -> None:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    coercive_request = {**fixtures["request"], "limit": "3"}
    request_json = json.dumps(coercive_request)

    for request_model in (
        KnowledgeSearchRequestBody,
        KnowledgeExplanationRequestBody,
    ):
        with pytest.raises(ValidationError):
            request_model.model_validate_json(request_json, strict=True)
