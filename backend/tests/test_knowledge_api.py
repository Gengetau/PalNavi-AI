from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import httpx
import pytest

from palnavi.api.dependencies import get_knowledge_retrieval_service
from palnavi.api.main import app
from palnavi.api.schemas import KnowledgeSearchResponse, RequestValidationErrorResponse
from palnavi.domain.knowledge import (
    KnowledgeChunkId,
    KnowledgeCitation,
    KnowledgeClassification,
    KnowledgeDocumentId,
    KnowledgeQuery,
    KnowledgeRepositoryFailure,
    KnowledgeRepositoryFailureKind,
    KnowledgeSearchOutcome,
    KnowledgeSearchResult,
    KnowledgeSearchSuccess,
    KnowledgeVersionScope,
    KnowledgeVersionScopeKind,
    LanguageIdentifier,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class StubKnowledgeService:
    def __init__(self, outcome: KnowledgeSearchOutcome) -> None:
        self.outcome = outcome
        self.queries: list[KnowledgeQuery] = []

    def search(self, query: KnowledgeQuery) -> KnowledgeSearchOutcome:
        self.queries.append(query)
        return self.outcome


@contextmanager
def service_override(service: StubKnowledgeService) -> Iterator[None]:
    app.dependency_overrides[get_knowledge_retrieval_service] = lambda: service
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_knowledge_retrieval_service, None)


def api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


def search_result() -> KnowledgeSearchResult:
    document_id = KnowledgeDocumentId("synthetic-guide-a")
    chunk_id = KnowledgeChunkId("synthetic-guide-a-0123456789abcdef-0000")
    citation = KnowledgeCitation(
        document_id=document_id,
        chunk_id=chunk_id,
        title="Synthetic Guide",
        section_path=("Fictional Trails",),
        source_id="synthetic-source-a",
        source_locator="project-authored://synthetic-corpus/guide-a",
        retrieved_at=datetime(2026, 7, 11, tzinfo=UTC),
        license_or_usage_note="Project-authored synthetic fixture; test use only.",
    )
    return KnowledgeSearchResult(
        score=3.5,
        document_id=document_id,
        chunk_id=chunk_id,
        title="Synthetic Guide",
        section_path=("Fictional Trails",),
        text="Crystal moss marks a fictional trail.",
        language=LanguageIdentifier("en"),
        classification=KnowledgeClassification.SYNTHETIC,
        game_version_scope=KnowledgeVersionScope(
            KnowledgeVersionScopeKind.EXPLICIT_GAME_VERSION,
            "synthetic-1.0",
        ),
        citation=citation,
    )


async def test_knowledge_search_returns_citation_complete_results() -> None:
    service = StubKnowledgeService(KnowledgeSearchSuccess((search_result(),)))

    with service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/search",
                json={
                    "query": "crystal moss",
                    "language": "en",
                    "exact_game_version": "synthetic-1.0",
                    "synthetic_only": True,
                    "limit": 3,
                },
            )

    assert response.status_code == 200
    parsed = KnowledgeSearchResponse.model_validate(response.json())
    assert parsed.status == "success"
    assert len(parsed.results) == 1
    item = parsed.results[0]
    assert item.document_id == item.citation.document_id
    assert item.chunk_id == item.citation.chunk_id
    assert item.section_path == item.citation.section_path
    assert item.game_version_scope.value == "synthetic-1.0"
    assert service.queries == [
        KnowledgeQuery(
            "crystal moss",
            language=LanguageIdentifier("en"),
            exact_game_version="synthetic-1.0",
            synthetic_only=True,
            limit=3,
        )
    ]


async def test_knowledge_search_returns_empty_results_without_answer_generation() -> None:
    service = StubKnowledgeService(KnowledgeSearchSuccess(()))

    with service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/search",
                json={"query": "no matching synthetic term"},
            )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "results": [],
        "error_category": None,
        "message": None,
    }
    assert "answer" not in response.json()


async def test_repository_failure_is_structured_and_path_safe() -> None:
    service = StubKnowledgeService(
        KnowledgeRepositoryFailure(
            KnowledgeRepositoryFailureKind.UNAVAILABLE,
            "knowledge search failed",
        )
    )

    with service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/search",
                json={"query": "crystal"},
            )

    assert response.status_code == 503
    parsed = KnowledgeSearchResponse.model_validate(response.json())
    assert parsed.error_category == "repository_unavailable"
    assert "knowledge.sqlite3" not in response.text
    assert "Traceback" not in response.text


@pytest.mark.parametrize(
    "body",
    [
        {"query": ""},
        {"query": "crystal", "limit": 21},
        {"query": "crystal", "language": "not a language"},
        {"query": "crystal", "unexpected": True},
    ],
)
async def test_request_schema_validation_is_typed(body: dict[str, object]) -> None:
    service = StubKnowledgeService(KnowledgeSearchSuccess(()))

    with service_override(service):
        async with api_client() as client:
            response = await client.post("/api/v1/knowledge/search", json=body)

    assert response.status_code == 422
    RequestValidationErrorResponse.model_validate(response.json())
    assert service.queries == []


async def test_whitespace_query_returns_structured_application_validation() -> None:
    service = StubKnowledgeService(KnowledgeSearchSuccess(()))

    with service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/search",
                json={"query": "   "},
            )

    assert response.status_code == 422
    parsed = KnowledgeSearchResponse.model_validate(response.json())
    assert parsed.status == "error"
    assert parsed.error_category == "request_invalid"
    assert service.queries == []


async def test_openapi_declares_success_and_both_validation_shapes() -> None:
    async with api_client() as client:
        document = (await client.get("/openapi.json")).json()

    operation = document["paths"]["/api/v1/knowledge/search"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/KnowledgeSearchResponse"
    }
    validation_schema = operation["responses"]["422"]["content"]["application/json"]["schema"]
    choices = validation_schema.get("anyOf") or validation_schema.get("oneOf")
    assert choices is not None
    assert {choice["$ref"] for choice in choices} == {
        "#/components/schemas/KnowledgeSearchResponse",
        "#/components/schemas/RequestValidationErrorResponse",
    }
    components = document["components"]["schemas"]
    assert all(choice["$ref"].split("/")[-1] in components for choice in choices)
