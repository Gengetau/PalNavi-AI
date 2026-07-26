import json
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest

from palnavi.api.dependencies import (
    get_dataset_repository,
    get_direct_breeding_repository,
    get_species_catalog_repository,
)
from palnavi.api.main import app
from palnavi.api.schemas import (
    DirectBreedingResponse,
    GenderRouteResponse,
    RequestValidationErrorResponse,
    RouteResponse,
    SpeciesCatalogResponse,
)
from palnavi.domain.data import (
    DatasetInvalid,
    DatasetLoadResult,
    DatasetNotFound,
    DatasetValidationCode,
    DatasetValidationIssue,
    GenderAwareDatasetLoadResult,
    SpeciesCatalogLoadResult,
)
from palnavi.infrastructure.palworld_dataset_repository import (
    PALWORLD_DATASET_ID,
    default_palworld_dataset_root,
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


class StubDirectRepository:
    def __init__(self, result: GenderAwareDatasetLoadResult) -> None:
        self.result = result
        self.requested_ids: list[str] = []

    def load(self, dataset_id: str) -> GenderAwareDatasetLoadResult:
        self.requested_ids.append(dataset_id)
        return self.result


class StubSpeciesCatalogRepository:
    def __init__(self, result: SpeciesCatalogLoadResult) -> None:
        self.result = result
        self.requested_ids: list[str] = []

    def load(self, dataset_id: str) -> SpeciesCatalogLoadResult:
        self.requested_ids.append(dataset_id)
        return self.result


@contextmanager
def repository_override(repository: StubRepository) -> Iterator[None]:
    app.dependency_overrides[get_dataset_repository] = lambda: repository
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_dataset_repository, None)


@contextmanager
def direct_repository_override(repository: StubDirectRepository) -> Iterator[None]:
    app.dependency_overrides[get_direct_breeding_repository] = lambda: repository
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_direct_breeding_repository, None)


@contextmanager
def species_catalog_repository_override(
    repository: StubSpeciesCatalogRepository,
) -> Iterator[None]:
    app.dependency_overrides[get_species_catalog_repository] = lambda: repository
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_species_catalog_repository, None)


async def test_health() -> None:
    async with api_client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_species_catalog_returns_exact_versioned_presentation_records() -> None:
    async with api_client() as client:
        response = await client.get(
            "/api/v1/palworld/species-catalog",
            params={"dataset_id": PALWORLD_DATASET_ID},
        )

    assert response.status_code == 200
    payload = response.json()
    SpeciesCatalogResponse.model_validate(payload)
    assert set(payload) == {
        "status",
        "dataset_id",
        "content_sha256",
        "locale_tags",
        "records",
        "error_category",
        "errors",
        "message",
    }
    assert payload["status"] == "success"
    assert len(payload["locale_tags"]) == 17
    assert len(payload["records"]) == 299
    source = json.loads(
        (default_palworld_dataset_root() / PALWORLD_DATASET_ID / "pals.json").read_text(
            encoding="utf-8"
        )
    )
    expected_records = sorted(
        [
            {
                "species_id": record["internal_id"],
                "paldeck_number": record["paldex_number"],
                "paldeck_suffix": record["paldex_suffix"],
                "is_variant": record["is_variant"],
                "localized_names": record["localized_names"],
                "source_record_sha256": record["source_record_hash"],
            }
            for record in source["records"]
        ],
        key=lambda record: record["species_id"],
    )
    assert payload["records"] == expected_records
    assert len(response.content) < 1_048_576
    anubis = next(record for record in payload["records"] if record["species_id"] == "anubis")
    assert {
        locale: anubis["localized_names"][locale] for locale in ("en", "ja", "zh-Hans", "zh-Hant")
    } == {
        "en": "Anubis",
        "ja": "アヌビス",
        "zh-Hans": "阿努比斯",
        "zh-Hant": "阿努比斯",
    }
    assert set(anubis) == {
        "species_id",
        "paldeck_number",
        "paldeck_suffix",
        "is_variant",
        "localized_names",
        "source_record_sha256",
    }


async def test_species_catalog_unknown_dataset_has_deterministic_not_found_shape() -> None:
    repository = StubSpeciesCatalogRepository(DatasetNotFound(dataset_id="unknown"))

    with species_catalog_repository_override(repository):
        async with api_client() as client:
            response = await client.get(
                "/api/v1/palworld/species-catalog",
                params={"dataset_id": "unknown"},
            )

    assert response.status_code == 404
    assert response.json() == {
        "status": "not_found",
        "dataset_id": "unknown",
        "content_sha256": None,
        "locale_tags": [],
        "records": [],
        "error_category": "dataset_not_found",
        "errors": [
            {
                "code": "dataset_not_found",
                "field": "dataset_id",
                "message": "requested species catalog was not found",
            }
        ],
        "message": "species catalog could not be validated",
    }
    assert repository.requested_ids == ["unknown"]


async def test_species_catalog_invalid_storage_has_deterministic_invalid_shape() -> None:
    issue = DatasetValidationIssue(
        code=DatasetValidationCode.MALFORMED_PALWORLD_RECORD,
        field="pals.json.records",
        message="catalog is malformed",
    )
    repository = StubSpeciesCatalogRepository(
        DatasetInvalid(dataset_id=PALWORLD_DATASET_ID, issues=(issue,))
    )

    with species_catalog_repository_override(repository):
        async with api_client() as client:
            response = await client.get(
                "/api/v1/palworld/species-catalog",
                params={"dataset_id": PALWORLD_DATASET_ID},
            )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "invalid"
    assert payload["error_category"] == "dataset_invalid"
    assert payload["records"] == []
    assert payload["errors"] == [
        {
            "code": "malformed_palworld_record",
            "field": "pals.json.records",
            "message": "catalog is malformed",
        }
    ]


@pytest.mark.parametrize(
    ("parent_a", "gender_a", "parent_b", "gender_b", "expected_child"),
    [
        ("katress", "male", "wixen", "female", "wixen_noct"),
        ("katress", "female", "wixen", "male", "katress_ignis"),
        ("wixen", "female", "katress", "male", "wixen_noct"),
        ("wixen", "male", "katress", "female", "katress_ignis"),
    ],
)
async def test_direct_breeding_preserves_gender_orientation(
    parent_a: str,
    gender_a: str,
    parent_b: str,
    gender_b: str,
    expected_child: str,
) -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "parent_a": {"species_id": parent_a, "gender": gender_a},
                "parent_b": {"species_id": parent_b, "gender": gender_b},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    DirectBreedingResponse.model_validate(payload)
    assert payload["status"] == "success"
    assert payload["child_species_id"] == expected_child
    assert payload["result_kind"] == "gender_directed"
    assert len(payload["source_record_hash"]) == 64


async def test_species_only_directed_query_returns_both_possibilities() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "query_mode": "species_only",
                "parent_a": {"species_id": "katress"},
                "parent_b": {"species_id": "wixen"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "gender_required"
    assert [
        (
            item["parent_a_gender"],
            item["parent_b_gender"],
            item["child_species_id"],
        )
        for item in payload["possible_results"]
    ] == [
        ("male", "female", "wixen_noct"),
        ("female", "male", "katress_ignis"),
    ]


async def test_species_only_wildcard_query_returns_exact_child() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "query_mode": "species_only",
                "parent_a": {"species_id": "anubis"},
                "parent_b": {"species_id": "lamball"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["child_species_id"]
    assert payload["result_kind"] != "gender_directed"


async def test_unknown_gender_returns_machine_readable_requirement() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "parent_a": {"species_id": "katress", "gender": "unknown"},
                "parent_b": {"species_id": "wixen", "gender": "female"},
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "gender_required"
    assert len(response.json()["possible_results"]) == 2


async def test_same_gender_direct_query_is_invalid() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "parent_a": {"species_id": "katress", "gender": "male"},
                "parent_b": {"species_id": "wixen", "gender": "male"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "invalid"
    assert payload["error_category"] == "parent_pair_invalid"
    assert payload["errors"][0]["code"] == "invalid_parent_pair"


@pytest.mark.parametrize(
    "parents",
    [
        (
            {"species_id": "katress"},
            {"species_id": "wixen"},
        ),
        (
            {"species_id": "katress"},
            {"species_id": "wixen", "gender": "female"},
        ),
        (
            {"species_id": "katress", "gender": None},
            {"species_id": "wixen", "gender": "female"},
        ),
        (
            {"species_id": "katress", "gender": "invalid"},
            {"species_id": "wixen", "gender": "female"},
        ),
    ],
)
async def test_concrete_direct_query_rejects_omitted_null_or_invalid_gender(
    parents: tuple[dict[str, object], dict[str, object]],
) -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "parent_a": parents[0],
                "parent_b": parents[1],
            },
        )

    assert response.status_code == 422
    RequestValidationErrorResponse.model_validate(response.json())


async def test_species_only_mode_rejects_inventory_gender_fields() -> None:
    async with api_client() as client:
        for gender in ("male", None):
            response = await client.post(
                "/api/v1/breeding/direct",
                json={
                    "dataset_id": PALWORLD_DATASET_ID,
                    "query_mode": "species_only",
                    "parent_a": {"species_id": "katress", "gender": gender},
                    "parent_b": {"species_id": "wixen"},
                },
            )
            assert response.status_code == 422


async def test_gender_aware_route_uses_directed_rule_after_an_ordinary_step() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/gender-aware-routes",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "target": {"species_id": "wixen_noct", "gender": "female"},
                "inventory": [
                    {
                        "instance_id": "dumud-1",
                        "species_id": "dumud",
                        "gender": "male",
                    },
                    {
                        "instance_id": "katress-ignis-1",
                        "species_id": "katress_ignis",
                        "gender": "female",
                    },
                    {
                        "instance_id": "wixen-1",
                        "species_id": "wixen",
                        "gender": "female",
                    },
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    GenderRouteResponse.model_validate(payload)
    assert payload["status"] == "success"
    assert payload["target"] == {
        "species_id": "wixen_noct",
        "gender": "female",
        "required_passive_ids": [],
        "required_iv_constraints": [],
        "generation_depth": 2,
    }
    assert payload["cost"] == {
        "generations": 2,
        "breeding_steps": 2,
        "probability_dependent_cost_available": False,
        "expected_attempts": None,
    }
    assert [
        (
            step["parent_a"]["species_id"],
            step["parent_a"]["gender"],
            step["parent_b"]["species_id"],
            step["parent_b"]["gender"],
            step["child"]["species_id"],
            step["child"]["gender"],
            step["result_kind"],
        )
        for step in payload["steps"]
    ] == [
        (
            "dumud",
            "male",
            "katress_ignis",
            "female",
            "katress",
            "male",
            "ordinary_power",
        ),
        (
            "katress",
            "male",
            "wixen",
            "female",
            "wixen_noct",
            "female",
            "gender_directed",
        ),
    ]


async def test_gender_aware_route_unknown_inventory_is_machine_readable() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/gender-aware-routes",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "target": {"species_id": "wixen_noct", "gender": "female"},
                "inventory": [
                    {
                        "instance_id": "katress-unknown",
                        "species_id": "katress",
                        "gender": "unknown",
                    },
                    {
                        "instance_id": "wixen-1",
                        "species_id": "wixen",
                        "gender": "female",
                    },
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "gender_required"
    assert payload["unknown_instance_ids"] == ["katress-unknown"]
    assert payload["cost"] is None


@pytest.mark.parametrize("gender_value", [None, "unknown", "invalid"])
async def test_gender_aware_route_rejects_non_concrete_target_gender(
    gender_value: object,
) -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/gender-aware-routes",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "target": {"species_id": "wixen_noct", "gender": gender_value},
                "inventory": [],
            },
        )

    assert response.status_code == 422
    RequestValidationErrorResponse.model_validate(response.json())


async def test_gender_aware_route_rejects_duplicate_instance_ids() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/gender-aware-routes",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "target": {"species_id": "wixen_noct", "gender": "female"},
                "inventory": [
                    {
                        "instance_id": "duplicate",
                        "species_id": "katress",
                        "gender": "male",
                    },
                    {
                        "instance_id": "duplicate",
                        "species_id": "wixen",
                        "gender": "female",
                    },
                ],
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "invalid"
    assert payload["error_category"] == "request_invalid"


async def test_direct_rule_not_found_is_structured() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": PALWORLD_DATASET_ID,
                "query_mode": "species_only",
                "parent_a": {"species_id": "not_in_dataset"},
                "parent_b": {"species_id": "katress"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_found"
    assert payload["error_category"] == "rule_not_found"


async def test_direct_dataset_not_found_is_structured() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/breeding/direct",
            json={
                "dataset_id": "missing-dataset",
                "parent_a": {"species_id": "katress", "gender": "male"},
                "parent_b": {"species_id": "wixen", "gender": "female"},
            },
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "not_found"
    assert payload["error_category"] == "dataset_not_found"


async def test_direct_dataset_invalid_is_sanitized() -> None:
    repository = StubDirectRepository(
        DatasetInvalid(
            dataset_id=PALWORLD_DATASET_ID,
            issues=(
                DatasetValidationIssue(
                    code=DatasetValidationCode.FILE_INTEGRITY_MISMATCH,
                    field="breeding-outcomes/part-000.json",
                    message="dataset file does not match its manifest identity",
                ),
            ),
        )
    )
    with direct_repository_override(repository):
        async with api_client() as client:
            response = await client.post(
                "/api/v1/breeding/direct",
                json={
                    "dataset_id": PALWORLD_DATASET_ID,
                    "parent_a": {"species_id": "katress", "gender": "male"},
                    "parent_b": {"species_id": "wixen", "gender": "female"},
                },
            )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "invalid"
    assert payload["error_category"] == "dataset_invalid"
    assert "\\" not in response.text
    assert ":/" not in response.text
    assert repository.requested_ids == [PALWORLD_DATASET_ID]


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
