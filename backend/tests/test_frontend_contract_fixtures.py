import json
from pathlib import Path

from palnavi.api.schemas import (
    KnowledgeExplanationErrorResponse,
    KnowledgeExplanationRequestBody,
    KnowledgeExplanationSuccessResponse,
    KnowledgeExplanationUnsupportedResponse,
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

    KnowledgeExplanationRequestBody.model_validate(fixtures["request"])
    KnowledgeSearchResponse.model_validate(fixtures["search_success"])
    KnowledgeSearchResponse.model_validate(fixtures["search_error"])
    KnowledgeExplanationSuccessResponse.model_validate(fixtures["explain_success"])
    KnowledgeExplanationUnsupportedResponse.model_validate(fixtures["explain_unsupported"])
    KnowledgeExplanationErrorResponse.model_validate(fixtures["explain_error"])
