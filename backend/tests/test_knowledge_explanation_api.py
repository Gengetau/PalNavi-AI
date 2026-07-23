from __future__ import annotations

import asyncio
import socket
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import httpx
import pytest

import palnavi.api.dependencies as api_dependencies
import palnavi.infrastructure.model.adapters as model_adapters
from palnavi.api.dependencies import (
    get_knowledge_explanation_service,
    get_knowledge_retrieval_service,
)
from palnavi.api.main import app
from palnavi.api.schemas import (
    KnowledgeExplanationErrorResponse,
    KnowledgeExplanationSuccessResponse,
    KnowledgeExplanationUnsupportedResponse,
    KnowledgeSearchResponse,
    RequestValidationErrorResponse,
)
from palnavi.application import (
    KnowledgeExplanationCitation,
    KnowledgeExplanationInvalidOutputFailure,
    KnowledgeExplanationInvalidOutputKind,
    KnowledgeExplanationModelFailure,
    KnowledgeExplanationOutcome,
    KnowledgeExplanationRequest,
    KnowledgeExplanationRetrievalFailure,
    KnowledgeExplanationSuccess,
    KnowledgeExplanationUnsupported,
    ModelErrorCategory,
    ModelGatewayError,
    ModelProviderId,
    ModelTokenUsage,
)
from palnavi.domain.knowledge import (
    KnowledgeChunkId,
    KnowledgeCitation,
    KnowledgeClassification,
    KnowledgeDocumentId,
    KnowledgeQuery,
    KnowledgeRepositoryFailureKind,
    KnowledgeSearchOutcome,
    KnowledgeSearchResult,
    KnowledgeSearchSuccess,
    KnowledgeVersionScope,
    KnowledgeVersionScopeKind,
    LanguageIdentifier,
)
from palnavi.infrastructure.model.config import ModelProviderConfig

pytestmark = pytest.mark.anyio

_ASGI_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def block_external_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external I/O is forbidden in explanation API tests")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket, "gethostbyname", blocked)
    monkeypatch.setattr(socket, "gethostbyname_ex", blocked)
    monkeypatch.setattr(socket, "gethostbyaddr", blocked)
    monkeypatch.setattr(socket, "getnameinfo", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket.socket, "sendto", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", blocked)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", blocked)


class FakeExplanationService:
    def __init__(self, outcome: KnowledgeExplanationOutcome) -> None:
        self.outcome = outcome
        self.requests: list[KnowledgeExplanationRequest] = []

    async def explain(
        self,
        request: KnowledgeExplanationRequest,
    ) -> KnowledgeExplanationOutcome:
        self.requests.append(request)
        return self.outcome


class StubKnowledgeService:
    def __init__(self, outcome: KnowledgeSearchOutcome) -> None:
        self.outcome = outcome
        self.queries: list[KnowledgeQuery] = []

    def search(self, query: KnowledgeQuery) -> KnowledgeSearchOutcome:
        self.queries.append(query)
        return self.outcome


class ControlledProviderTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        status_code: int = 200,
        *,
        block: bool = False,
    ) -> None:
        self.status_code = status_code
        self.block = block
        self.requests: list[httpx.Request] = []
        self.request_started = asyncio.Event()
        self.release_request = asyncio.Event()
        self.closed = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.request_started.set()
        if self.block:
            await self.release_request.wait()

        if self.status_code == 200:
            payload: dict[str, object] = {
                "id": "fake-provider-request-001",
                "choices": [
                    {
                        "message": {
                            "content": "Synthetic fixture explanation. [K1]",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 5,
                    "total_tokens": 13,
                },
            }
        else:
            payload = {
                "error": {
                    "type": "synthetic_provider_failure",
                }
            }

        return httpx.Response(
            self.status_code,
            json=payload,
            request=request,
        )

    async def aclose(self) -> None:
        self.closed = True


class TrackedOwnedAsyncClient(httpx.AsyncClient):
    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        super().__init__(transport=transport, timeout=1.0)
        self.close_calls = 0

    async def aclose(self) -> None:
        self.close_calls += 1
        await super().aclose()


@contextmanager
def explanation_service_override(service: FakeExplanationService) -> Iterator[None]:
    app.dependency_overrides[get_knowledge_explanation_service] = lambda: service
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_knowledge_explanation_service, None)


@contextmanager
def retrieval_service_override(service: StubKnowledgeService) -> Iterator[None]:
    app.dependency_overrides[get_knowledge_retrieval_service] = lambda: service
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_knowledge_retrieval_service, None)


def api_client() -> httpx.AsyncClient:
    return _ASGI_ASYNC_CLIENT(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


def test_external_io_guard_blocks_reverse_dns_and_udp() -> None:
    with pytest.raises(AssertionError, match="external I/O"):
        socket.gethostbyaddr("192.0.2.1")

    datagram = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(AssertionError, match="external I/O"):
            datagram.sendto(
                b"offline",
                ("192.0.2.1", 9),
            )
    finally:
        datagram.close()


def search_result() -> KnowledgeSearchResult:
    document_id = KnowledgeDocumentId("synthetic-explanation-guide")
    chunk_id = KnowledgeChunkId("synthetic-explanation-guide-0123456789abcdef-0000")
    citation = KnowledgeCitation(
        document_id=document_id,
        chunk_id=chunk_id,
        title="Synthetic Explanation Guide",
        section_path=("Imaginary Routes",),
        source_id="synthetic-explanation-source",
        source_locator="project-authored://synthetic-explanation/guide",
        retrieved_at=datetime(2026, 7, 11, tzinfo=UTC),
        license_or_usage_note="Project-authored synthetic fixture; test use only.",
    )
    return KnowledgeSearchResult(
        score=4.25,
        document_id=document_id,
        chunk_id=chunk_id,
        title="Synthetic Explanation Guide",
        section_path=("Imaginary Routes",),
        text="Synthetic crystal paths remain entirely inside this deterministic fixture.",
        language=LanguageIdentifier("en"),
        classification=KnowledgeClassification.SYNTHETIC,
        game_version_scope=KnowledgeVersionScope(
            KnowledgeVersionScopeKind.EXPLICIT_GAME_VERSION,
            "synthetic-api-1.0",
        ),
        citation=citation,
    )


def fake_success() -> KnowledgeExplanationSuccess:
    result = search_result()
    return KnowledgeExplanationSuccess(
        answer="Synthetic fixture explanation. [K1]",
        citations=(KnowledgeExplanationCitation("[K1]", result.citation),),
        usage=ModelTokenUsage(input_tokens=8, output_tokens=5, total_tokens=13),
    )


def fake_provider_config() -> ModelProviderConfig:
    return ModelProviderConfig(
        provider_id=ModelProviderId.CUSTOM,
        model_id="fake-api-explanation-model",
        base_url="http://localhost:65535",
    )


def install_owned_gateway(
    monkeypatch: pytest.MonkeyPatch,
    provider_client: TrackedOwnedAsyncClient,
) -> list[dict[str, object]]:
    config = fake_provider_config()
    constructor_calls: list[dict[str, object]] = []

    def tracked_client_factory(
        *_args: object,
        **kwargs: object,
    ) -> TrackedOwnedAsyncClient:
        constructor_calls.append(dict(kwargs))
        return provider_client

    monkeypatch.setattr(api_dependencies, "load_model_provider_config", lambda: config)
    monkeypatch.setattr(
        model_adapters.httpx,
        "AsyncClient",
        tracked_client_factory,
    )
    return constructor_calls


async def test_success_response_preserves_query_and_canonical_citation() -> None:
    result = search_result()
    service = FakeExplanationService(fake_success())

    with explanation_service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={
                    "query": "synthetic crystals",
                    "language": "en-US",
                    "exact_game_version": "synthetic-api-1.0",
                    "synthetic_only": True,
                    "limit": 3,
                },
            )

    assert response.status_code == 200
    parsed = KnowledgeExplanationSuccessResponse.model_validate(response.json())
    assert parsed.status == "success"
    assert parsed.answer == "Synthetic fixture explanation. [K1]"
    assert parsed.citations[0].marker == "[K1]"
    assert parsed.citations[0].citation.document_id == result.citation.document_id.value
    assert parsed.citations[0].citation.source_locator == result.citation.source_locator
    assert parsed.usage is not None
    assert parsed.usage.total_tokens == 13
    assert service.requests == [
        KnowledgeExplanationRequest(
            KnowledgeQuery(
                "synthetic crystals",
                language=LanguageIdentifier("en-US"),
                exact_game_version="synthetic-api-1.0",
                synthetic_only=True,
                limit=3,
            )
        )
    ]


async def test_unsupported_response_is_explicit_and_sanitized() -> None:
    service = FakeExplanationService(
        KnowledgeExplanationUnsupported("INTERNAL_DETAIL_MUST_NOT_ESCAPE")
    )

    with explanation_service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "unsupported synthetic question"},
            )

    assert response.status_code == 200
    parsed = KnowledgeExplanationUnsupportedResponse.model_validate(response.json())
    assert parsed.status == "unsupported"
    assert parsed.message == "No usable knowledge evidence was found."
    assert "INTERNAL_DETAIL_MUST_NOT_ESCAPE" not in response.text


@pytest.mark.parametrize(
    ("category", "expected_status"),
    [
        (ModelErrorCategory.CONFIGURATION_INVALID, 503),
        (ModelErrorCategory.AUTHENTICATION_REJECTED, 502),
        (ModelErrorCategory.RATE_LIMITED, 503),
        (ModelErrorCategory.REQUEST_INVALID, 502),
        (ModelErrorCategory.TIMEOUT, 504),
        (ModelErrorCategory.PROVIDER_UNAVAILABLE, 503),
        (ModelErrorCategory.MALFORMED_RESPONSE, 502),
        (ModelErrorCategory.UNKNOWN_PROVIDER, 503),
    ],
)
async def test_model_failure_categories_have_stable_statuses(
    category: ModelErrorCategory,
    expected_status: int,
) -> None:
    service = FakeExplanationService(
        KnowledgeExplanationModelFailure(
            category,
            "INTERNAL_DETAIL_MUST_NOT_ESCAPE",
        )
    )

    with explanation_service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "synthetic provider failure"},
            )

    assert response.status_code == expected_status
    parsed = KnowledgeExplanationErrorResponse.model_validate(response.json())
    assert parsed.status == "error"
    assert parsed.error_category == category.value
    assert "INTERNAL_DETAIL_MUST_NOT_ESCAPE" not in response.text


@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_category"),
    [
        (
            KnowledgeExplanationRetrievalFailure(
                KnowledgeRepositoryFailureKind.UNAVAILABLE,
                "INTERNAL_DETAIL_MUST_NOT_ESCAPE",
            ),
            503,
            "repository_unavailable",
        ),
        (
            KnowledgeExplanationRetrievalFailure(
                KnowledgeRepositoryFailureKind.INVALID_STATE,
                "INTERNAL_DETAIL_MUST_NOT_ESCAPE",
            ),
            503,
            "repository_invalid_state",
        ),
        (
            KnowledgeExplanationInvalidOutputFailure(
                KnowledgeExplanationInvalidOutputKind.UNKNOWN_CITATION,
                "INTERNAL_DETAIL_MUST_NOT_ESCAPE",
            ),
            502,
            "invalid_grounded_output",
        ),
    ],
)
async def test_retrieval_and_grounding_failure_mapping(
    outcome: KnowledgeExplanationOutcome,
    expected_status: int,
    expected_category: str,
) -> None:
    service = FakeExplanationService(outcome)

    with explanation_service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "synthetic controlled failure"},
            )

    assert response.status_code == expected_status
    parsed = KnowledgeExplanationErrorResponse.model_validate(response.json())
    assert parsed.error_category == expected_category
    assert "INTERNAL_DETAIL_MUST_NOT_ESCAPE" not in response.text


async def test_fastapi_request_validation_uses_declared_shape() -> None:
    service = FakeExplanationService(KnowledgeExplanationUnsupported())

    with explanation_service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "synthetic question", "unexpected": True},
            )

    assert response.status_code == 422
    RequestValidationErrorResponse.model_validate(response.json())
    assert service.requests == []


async def test_application_request_validation_uses_error_shape() -> None:
    service = FakeExplanationService(KnowledgeExplanationUnsupported())

    with explanation_service_override(service):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "   "},
            )

    assert response.status_code == 422
    parsed = KnowledgeExplanationErrorResponse.model_validate(response.json())
    assert parsed.error_category == "request_invalid"
    assert service.requests == []


async def test_search_and_no_evidence_do_not_construct_model_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieval = StubKnowledgeService(KnowledgeSearchSuccess(()))
    construction_attempts: list[str] = []

    def blocked_construction(*_args: object, **_kwargs: object) -> None:
        construction_attempts.append("attempted")
        raise AssertionError("model construction was not expected")

    monkeypatch.setattr(api_dependencies, "load_model_provider_config", blocked_construction)
    monkeypatch.setattr(api_dependencies, "create_model_gateway", blocked_construction)

    with retrieval_service_override(retrieval):
        async with api_client() as client:
            search_response = await client.post(
                "/api/v1/knowledge/search",
                json={"query": "missing synthetic evidence"},
            )
            explanation_response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "missing synthetic evidence"},
            )

    assert search_response.status_code == 200
    parsed_search = KnowledgeSearchResponse.model_validate(search_response.json())
    assert parsed_search.status == "success"
    assert explanation_response.status_code == 200
    parsed_explanation = KnowledgeExplanationUnsupportedResponse.model_validate(
        explanation_response.json()
    )
    assert parsed_explanation.status == "unsupported"
    assert construction_attempts == []


async def test_missing_provider_configuration_is_typed_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieval = StubKnowledgeService(KnowledgeSearchSuccess((search_result(),)))
    factory_calls: list[str] = []

    def missing_config() -> ModelProviderConfig:
        raise ModelGatewayError(
            ModelErrorCategory.CONFIGURATION_INVALID,
            "INTERNAL_CONFIG_DETAIL_MUST_NOT_ESCAPE",
        )

    def forbidden_gateway(
        _config: ModelProviderConfig,
    ) -> None:
        factory_calls.append("attempted")
        raise AssertionError("gateway construction was not expected")

    monkeypatch.setattr(api_dependencies, "load_model_provider_config", missing_config)
    monkeypatch.setattr(api_dependencies, "create_model_gateway", forbidden_gateway)

    with retrieval_service_override(retrieval):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "synthetic configured evidence"},
            )

    assert response.status_code == 503
    parsed = KnowledgeExplanationErrorResponse.model_validate(response.json())
    assert parsed.error_category == "configuration_invalid"
    assert "INTERNAL_CONFIG_DETAIL_MUST_NOT_ESCAPE" not in response.text
    assert factory_calls == []


@pytest.mark.parametrize(
    ("provider_status", "expected_status", "expected_category"),
    [
        (200, 200, None),
        (503, 503, "provider_unavailable"),
    ],
)
async def test_owned_real_http_gateway_closes_after_success_and_provider_failure(
    provider_status: int,
    expected_status: int,
    expected_category: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = search_result()
    provider_transport = ControlledProviderTransport(provider_status)
    provider_client = TrackedOwnedAsyncClient(provider_transport)
    constructor_calls = install_owned_gateway(monkeypatch, provider_client)
    retrieval = StubKnowledgeService(KnowledgeSearchSuccess((result,)))

    with retrieval_service_override(retrieval):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/knowledge/explain",
                json={"query": "synthetic owned-client evidence"},
            )

    assert response.status_code == expected_status
    assert len(constructor_calls) == 1
    assert constructor_calls[0]["timeout"] == 30.0
    assert provider_client.is_closed
    assert provider_client.close_calls == 1
    assert provider_transport.closed
    assert len(provider_transport.requests) == 1
    assert str(provider_transport.requests[0].url) == ("http://localhost:65535/chat/completions")

    if expected_category is None:
        parsed_success = KnowledgeExplanationSuccessResponse.model_validate(response.json())
        assert parsed_success.status == "success"
        assert parsed_success.citations[0].citation.document_id == (
            result.citation.document_id.value
        )
        assert parsed_success.citations[0].citation.source_locator == (
            result.citation.source_locator
        )
    else:
        parsed_error = KnowledgeExplanationErrorResponse.model_validate(response.json())
        assert parsed_error.error_category == expected_category
        assert "synthetic_provider_failure" not in response.text


async def test_active_asgi_request_cancellation_closes_owned_real_http_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_transport = ControlledProviderTransport(block=True)
    provider_client = TrackedOwnedAsyncClient(provider_transport)
    constructor_calls = install_owned_gateway(monkeypatch, provider_client)
    retrieval = StubKnowledgeService(KnowledgeSearchSuccess((search_result(),)))

    with retrieval_service_override(retrieval):
        async with api_client() as client:
            request_task = asyncio.create_task(
                client.post(
                    "/api/v1/knowledge/explain",
                    json={"query": "synthetic actively cancelled evidence"},
                )
            )
            await asyncio.wait_for(
                provider_transport.request_started.wait(),
                timeout=1.0,
            )
            request_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request_task

    assert len(constructor_calls) == 1
    assert provider_client.is_closed
    assert provider_client.close_calls == 1
    assert provider_transport.closed
    assert len(provider_transport.requests) == 1


async def test_openapi_declares_all_explanation_response_shapes() -> None:
    async with api_client() as client:
        document = (await client.get("/openapi.json")).json()

    operation = document["paths"]["/api/v1/knowledge/explain"]["post"]
    responses = operation["responses"]

    success_schema = responses["200"]["content"]["application/json"]["schema"]
    success_choices = success_schema.get("anyOf") or success_schema.get("oneOf")
    assert success_choices is not None
    assert {choice["$ref"] for choice in success_choices} == {
        "#/components/schemas/KnowledgeExplanationSuccessResponse",
        "#/components/schemas/KnowledgeExplanationUnsupportedResponse",
    }

    validation_schema = responses["422"]["content"]["application/json"]["schema"]
    validation_choices = validation_schema.get("anyOf") or validation_schema.get("oneOf")
    assert validation_choices is not None
    assert {choice["$ref"] for choice in validation_choices} == {
        "#/components/schemas/KnowledgeExplanationErrorResponse",
        "#/components/schemas/RequestValidationErrorResponse",
    }

    for code in ("502", "503", "504"):
        assert responses[code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/KnowledgeExplanationErrorResponse"
        }

    components = document["components"]["schemas"]
    declared_refs = [*success_choices, *validation_choices]
    assert all(choice["$ref"].split("/")[-1] in components for choice in declared_refs)
