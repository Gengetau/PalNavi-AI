import httpx
import pytest

from palnavi.api.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


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
    assert response.json()["detail"]
