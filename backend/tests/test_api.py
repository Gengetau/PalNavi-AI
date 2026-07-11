from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest

from palnavi.api.dependencies import get_dataset_repository
from palnavi.api.main import app
from palnavi.api.schemas import RequestValidationErrorResponse, RouteResponse
from palnavi.domain.data import (
    DatasetInvalid,
    DatasetLoadResult,
    DatasetNotFound,
    DatasetValidationCode,
    DatasetValidationIssue,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


class StubRepository:
    def __init__(self, result: DatasetLoadResult) -> None:
        self.result = result
        self.requested_ids: list[str] = []

    def load(self, dataset_id: str) -> DatasetLoadResult:
        self.requested_ids.append(dataset_id)
        return self.result


@contextmanager
def repository_override(repository: StubRepository) -> Iterator[None]:
    app.dependency_overrides[get_dataset_repository] = lambda: repository
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_dataset_repository, None)


async def test_health() -> None:
    async with api_client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_fixture_backed_route() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/routes",
            json={"target_id": "pal_d", "owned_species_ids": ["pal_a", "pal_b"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert [step["child"] for step in payload["steps"]] == ["pal_c", "pal_d"]
    assert payload["cost"]["generations"] == 2
    assert payload["data_source"] == "synthetic-v1"
    assert payload["dataset"]["classification"] == "synthetic"
    assert payload["dataset"]["game_version_scope"] == {
        "kind": "synthetic_test_only",
        "value": None,
    }
    assert len(payload["dataset"]["content_sha256"]) == 64


async def test_unreachable_route_is_structured() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/routes",
            json={"target_id": "pal_z", "owned_species_ids": ["pal_a", "pal_b"]},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "unreachable"
    assert response.json()["message"]


async def test_invalid_identifier_is_structured() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/routes",
            json={"target_id": "Pal Z", "owned_species_ids": ["pal_a"]},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert response.json()["errors"]


async def test_dataset_not_found_is_structured_and_uses_repository() -> None:
    repository = StubRepository(DatasetNotFound(dataset_id="missing-dataset"))

    with repository_override(repository):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/breeding/routes",
                json={
                    "target_id": "pal_c",
                    "owned_species_ids": ["pal_a", "pal_b"],
                    "fixture": "missing-dataset",
                },
            )

    assert response.status_code == 404
    assert response.json()["status"] == "invalid"
    assert response.json()["error_category"] == "dataset_not_found"
    assert response.json()["errors"][0]["code"] == "dataset_not_found"
    assert repository.requested_ids == ["missing-dataset"]


async def test_dataset_invalid_is_structured_and_sanitized() -> None:
    repository = StubRepository(
        DatasetInvalid(
            dataset_id="synthetic-v1",
            issues=(
                DatasetValidationIssue(
                    code=DatasetValidationCode.CONTENT_IDENTITY_MISMATCH,
                    field="content_identity.digest",
                    message="dataset content does not match the declared identity",
                ),
            ),
        )
    )

    with repository_override(repository):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/breeding/routes",
                json={"target_id": "pal_c", "owned_species_ids": ["pal_a", "pal_b"]},
            )

    assert response.status_code == 422
    payload = response.json()
    RouteResponse.model_validate(payload)
    assert payload["error_category"] == "dataset_invalid"
    assert payload["errors"][0]["code"] == "content_identity_mismatch"
    assert "\\" not in response.text
    assert ":/" not in response.text


async def test_explicit_relationships_use_shared_validation() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/routes",
            json={
                "target_id": "pal_c",
                "owned_species_ids": ["pal_a", "pal_b"],
                "relationships": [
                    {"parent_a": "pal_a", "parent_b": "pal_b", "child": "pal_c"},
                    {"parent_a": "pal_b", "parent_b": "pal_a", "child": "pal_d"},
                ],
            },
        )

    assert response.status_code == 422
    payload = response.json()
    RouteResponse.model_validate(payload)
    assert payload["error_category"] == "relationships_invalid"
    assert payload["errors"][0]["code"] == "conflicting_relationship"


async def test_valid_explicit_relationships_remain_supported() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/routes",
            json={
                "target_id": "pal_c",
                "owned_species_ids": ["pal_a", "pal_b"],
                "relationships": [{"parent_a": "pal_b", "parent_b": "pal_a", "child": "pal_c"}],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data_source"] == "explicit-request"
    assert payload["dataset"] is None
    assert payload["steps"][0]["child"] == "pal_c"


async def test_malformed_relationship_schema_gets_validation_error() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/routes",
            json={
                "target_id": "pal_c",
                "owned_species_ids": ["pal_a", "pal_b"],
                "relationships": [{"parent_a": "pal_a", "child": "pal_c"}],
            },
        )

    assert response.status_code == 422
    payload = response.json()
    RequestValidationErrorResponse.model_validate(payload)
    assert payload["detail"]


async def test_openapi_documents_both_http_422_response_shapes() -> None:
    async with api_client() as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    document = response.json()
    schema = document["paths"]["/api/v1/breeding/routes"]["post"]["responses"]["422"]["content"][
        "application/json"
    ]["schema"]
    variants = schema.get("anyOf") or schema.get("oneOf")
    assert variants is not None

    references = {variant["$ref"] for variant in variants}
    assert references == {
        "#/components/schemas/RequestValidationErrorResponse",
        "#/components/schemas/RouteResponse",
    }
    components = document["components"]["schemas"]
    for reference in references:
        assert reference.removeprefix("#/components/schemas/") in components
