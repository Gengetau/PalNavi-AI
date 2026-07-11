import json
from collections.abc import Callable

import httpx
import pytest

from palnavi.application import (
    ModelErrorCategory,
    ModelGatewayError,
    ModelMessage,
    ModelMessageRole,
    ModelProviderId,
    ModelRequest,
)
from palnavi.infrastructure.model import (
    ModelProviderConfig,
    SecretValue,
    create_model_gateway,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def model_request(provider_id: ModelProviderId, model_id: str = "test-model") -> ModelRequest:
    return ModelRequest(
        provider_id=provider_id,
        model_id=model_id,
        messages=(
            ModelMessage(ModelMessageRole.SYSTEM, "Follow the test contract."),
            ModelMessage(ModelMessageRole.USER, "Return a short answer."),
            ModelMessage(ModelMessageRole.ASSISTANT, "Prior answer."),
        ),
        temperature=0.25,
        max_output_tokens=64,
    )


def provider_config(
    provider_id: ModelProviderId,
    base_url: str,
    *,
    key: str | None = "test-secret-marker",
) -> ModelProviderConfig:
    return ModelProviderConfig(
        provider_id=provider_id,
        model_id="configured-model",
        base_url=base_url,
        api_key=SecretValue(key) if key else None,
    )


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_openai_responses_request_and_response_mapping() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"x-request-id": "openai-request"},
            json={
                "id": "response-id",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "OpenAI answer"}],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            },
        )

    async with mock_client(handler) as client:
        gateway = create_model_gateway(
            provider_config(ModelProviderId.OPENAI, "https://api.openai.com/v1/"), client
        )
        result = await gateway.generate(model_request(ModelProviderId.OPENAI, "gpt-test"))

    assert seen[0].url == "https://api.openai.com/v1/responses"
    assert seen[0].headers["authorization"] == "Bearer test-secret-marker"
    payload = json.loads(seen[0].content)
    assert payload == {
        "model": "gpt-test",
        "input": [
            {"role": "user", "content": "Return a short answer."},
            {"role": "assistant", "content": "Prior answer."},
        ],
        "instructions": "Follow the test contract.",
        "temperature": 0.25,
        "max_output_tokens": 64,
    }
    assert result.text == "OpenAI answer"
    assert result.finish_reason == "completed"
    assert result.usage.total_tokens == 12
    assert result.provider_request_id == "openai-request"


async def test_anthropic_messages_request_and_response_mapping() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"request-id": "anthropic-request"},
            json={
                "id": "message-id",
                "content": [{"type": "text", "text": "Anthropic answer"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 8, "output_tokens": 3},
            },
        )

    async with mock_client(handler) as client:
        gateway = create_model_gateway(
            provider_config(ModelProviderId.ANTHROPIC, "https://api.anthropic.com"), client
        )
        result = await gateway.generate(model_request(ModelProviderId.ANTHROPIC, "claude-test"))

    assert seen[0].url == "https://api.anthropic.com/v1/messages"
    assert seen[0].headers["x-api-key"] == "test-secret-marker"
    assert seen[0].headers["anthropic-version"] == "2023-06-01"
    payload = json.loads(seen[0].content)
    assert payload["system"] == "Follow the test contract."
    assert payload["messages"] == [
        {"role": "user", "content": "Return a short answer."},
        {"role": "assistant", "content": "Prior answer."},
    ]
    assert payload["max_tokens"] == 64
    assert result.text == "Anthropic answer"
    assert result.finish_reason == "end_turn"
    assert result.usage.total_tokens == 11
    assert result.provider_request_id == "anthropic-request"


@pytest.mark.parametrize(
    ("provider_id", "base_url", "model_id", "expected_url", "key"),
    [
        (
            ModelProviderId.DEEPSEEK,
            "https://api.deepseek.com",
            "deepseek-v4-flash",
            "https://api.deepseek.com/chat/completions",
            "test-token",
        ),
        (
            ModelProviderId.ZHIPU,
            "https://open.bigmodel.cn/api/paas/v4",
            "glm-test",
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            "test-token",
        ),
        (
            ModelProviderId.BAILIAN,
            "https://dashscope.example.test/compatible-mode/v1",
            "qwen-test",
            "https://dashscope.example.test/compatible-mode/v1/chat/completions",
            "test-token",
        ),
        (
            ModelProviderId.CUSTOM,
            "http://127.0.0.1:8080/v1",
            "local-test",
            "http://127.0.0.1:8080/v1/chat/completions",
            None,
        ),
    ],
)
async def test_openai_compatible_provider_mapping(
    provider_id: ModelProviderId,
    base_url: str,
    model_id: str,
    expected_url: str,
    key: str | None,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "compatible-request",
                "choices": [{"message": {"content": "Compatible answer"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
            },
        )

    async with mock_client(handler) as client:
        gateway = create_model_gateway(
            provider_config(provider_id, base_url, key=key),
            client,
        )
        result = await gateway.generate(model_request(provider_id, model_id))

    assert str(seen[0].url) == expected_url
    payload = json.loads(seen[0].content)
    assert payload["model"] == model_id
    assert payload["stream"] is False
    assert payload["max_tokens"] == 64
    assert [message["role"] for message in payload["messages"]] == [
        "system",
        "user",
        "assistant",
    ]
    if key is None:
        assert "authorization" not in seen[0].headers
    else:
        assert seen[0].headers["authorization"] == f"Bearer {key}"
    assert result.text == "Compatible answer"
    assert result.finish_reason == "stop"
    assert result.usage.total_tokens == 9


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (400, ModelErrorCategory.REQUEST_INVALID),
        (401, ModelErrorCategory.AUTHENTICATION_REJECTED),
        (403, ModelErrorCategory.AUTHENTICATION_REJECTED),
        (429, ModelErrorCategory.RATE_LIMITED),
        (500, ModelErrorCategory.PROVIDER_UNAVAILABLE),
        (529, ModelErrorCategory.PROVIDER_UNAVAILABLE),
    ],
)
async def test_http_errors_are_normalized_without_response_or_key_leakage(
    status: int,
    category: ModelErrorCategory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers={"x-request-id": "failed-request"},
            json={"error": {"message": "test-secret-marker"}},
        )

    async with mock_client(handler) as client:
        gateway = create_model_gateway(
            provider_config(ModelProviderId.DEEPSEEK, "https://api.deepseek.com"), client
        )
        with pytest.raises(ModelGatewayError) as caught:
            await gateway.generate(model_request(ModelProviderId.DEEPSEEK))

    assert caught.value.category is category
    assert caught.value.provider_request_id == "failed-request"
    assert "test-secret-marker" not in str(caught.value)
    assert "test-secret-marker" not in repr(caught.value)


async def test_timeout_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    async with mock_client(handler) as client:
        gateway = create_model_gateway(
            provider_config(ModelProviderId.DEEPSEEK, "https://api.deepseek.com"), client
        )
        with pytest.raises(ModelGatewayError) as caught:
            await gateway.generate(model_request(ModelProviderId.DEEPSEEK))

    assert caught.value.category is ModelErrorCategory.TIMEOUT


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
    ],
)
async def test_malformed_provider_response_is_normalized(response: httpx.Response) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    async with mock_client(handler) as client:
        gateway = create_model_gateway(
            provider_config(ModelProviderId.DEEPSEEK, "https://api.deepseek.com"), client
        )
        with pytest.raises(ModelGatewayError) as caught:
            await gateway.generate(model_request(ModelProviderId.DEEPSEEK))

    assert caught.value.category is ModelErrorCategory.MALFORMED_RESPONSE


async def test_request_provider_mismatch_fails_before_network() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    async with mock_client(handler) as client:
        gateway = create_model_gateway(
            provider_config(ModelProviderId.DEEPSEEK, "https://api.deepseek.com"), client
        )
        with pytest.raises(ModelGatewayError) as caught:
            await gateway.generate(model_request(ModelProviderId.ZHIPU))

    assert caught.value.category is ModelErrorCategory.REQUEST_INVALID
    assert called is False
