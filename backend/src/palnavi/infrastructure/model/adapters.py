"""HTTP adapters for the supported model-provider protocols."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Never, cast

import httpx

from palnavi.application import (
    ModelErrorCategory,
    ModelGatewayError,
    ModelMessageRole,
    ModelProviderId,
    ModelRequest,
    ModelResponse,
    ModelTokenUsage,
)
from palnavi.infrastructure.model.config import ModelProviderConfig, normalized_base_url


class HttpModelGateway:
    def __init__(
        self,
        config: ModelProviderConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=config.timeout_seconds,
            trust_env=False,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    def _validate_request(self, request: ModelRequest) -> None:
        if request.provider_id is not self._config.provider_id:
            raise ModelGatewayError(
                ModelErrorCategory.REQUEST_INVALID,
                "request provider does not match the configured adapter",
                provider_id=self._config.provider_id.value,
            )

    async def _post(
        self,
        endpoint: str,
        headers: dict[str, str],
        payload: object,
    ) -> httpx.Response:
        url = f"{normalized_base_url(self._config)}{endpoint}"
        try:
            response = await self._client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as error:
            raise ModelGatewayError(
                ModelErrorCategory.TIMEOUT,
                "model provider request timed out",
                provider_id=self._config.provider_id.value,
            ) from error
        except httpx.RequestError as error:
            raise ModelGatewayError(
                ModelErrorCategory.PROVIDER_UNAVAILABLE,
                "model provider could not be reached",
                provider_id=self._config.provider_id.value,
            ) from error
        _raise_for_status(response, self._config.provider_id)
        return response


class OpenAIResponsesAdapter(HttpModelGateway):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        self._validate_request(request)
        system = "\n\n".join(
            message.text for message in request.messages if message.role is ModelMessageRole.SYSTEM
        )
        payload: dict[str, object] = {
            "model": request.model_id,
            "input": [
                {"role": message.role.value, "content": message.text}
                for message in request.messages
                if message.role is not ModelMessageRole.SYSTEM
            ],
        }
        if system:
            payload["instructions"] = system
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload["max_output_tokens"] = request.max_output_tokens
        response = await self._post("/responses", self._bearer_headers(), payload)
        data = _response_object(response, self._config.provider_id)
        text_parts: list[str] = []
        output = data.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, Mapping) or item.get("type") != "message":
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, Mapping) and block.get("type") == "output_text":
                        text = block.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)
        if not text_parts:
            _malformed_response(self._config.provider_id, response)
        finish_reason = _optional_string(data.get("status"))
        incomplete = data.get("incomplete_details")
        if isinstance(incomplete, Mapping):
            finish_reason = _optional_string(incomplete.get("reason")) or finish_reason
        return ModelResponse(
            text="".join(text_parts),
            finish_reason=finish_reason,
            usage=_usage(data.get("usage"), "input_tokens", "output_tokens"),
            provider_request_id=_request_id(response, data),
        )

    def _bearer_headers(self) -> dict[str, str]:
        assert self._config.api_key is not None
        return {"Authorization": f"Bearer {self._config.api_key.value}"}


class AnthropicMessagesAdapter(HttpModelGateway):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        self._validate_request(request)
        system = "\n\n".join(
            message.text for message in request.messages if message.role is ModelMessageRole.SYSTEM
        )
        messages = [
            {"role": message.role.value, "content": message.text}
            for message in request.messages
            if message.role is not ModelMessageRole.SYSTEM
        ]
        if not messages:
            raise ModelGatewayError(
                ModelErrorCategory.REQUEST_INVALID,
                "Anthropic requests require a user or assistant message",
                provider_id=self._config.provider_id.value,
            )
        payload: dict[str, object] = {
            "model": request.model_id,
            "messages": messages,
            "max_tokens": request.max_output_tokens or self._config.default_max_output_tokens,
        }
        if system:
            payload["system"] = system
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        assert self._config.api_key is not None
        response = await self._post(
            "/v1/messages",
            {
                "x-api-key": self._config.api_key.value,
                "anthropic-version": "2023-06-01",
            },
            payload,
        )
        data = _response_object(response, self._config.provider_id)
        text_parts: list[str] = []
        content = data.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, Mapping) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
        if not text_parts:
            _malformed_response(self._config.provider_id, response)
        return ModelResponse(
            text="".join(text_parts),
            finish_reason=_optional_string(data.get("stop_reason")),
            usage=_usage(data.get("usage"), "input_tokens", "output_tokens"),
            provider_request_id=_request_id(response, data),
        )


class OpenAICompatibleChatAdapter(HttpModelGateway):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        self._validate_request(request)
        payload: dict[str, object] = {
            "model": request.model_id,
            "messages": [
                {"role": message.role.value, "content": message.text}
                for message in request.messages
            ],
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        headers: dict[str, str] = {}
        if self._config.api_key is not None:
            headers["Authorization"] = f"Bearer {self._config.api_key.value}"
        response = await self._post("/chat/completions", headers, payload)
        data = _response_object(response, self._config.provider_id)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            _malformed_response(self._config.provider_id, response)
        first = cast(Mapping[str, Any], choices[0])
        message = first.get("message")
        text = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(text, str):
            _malformed_response(self._config.provider_id, response)
        return ModelResponse(
            text=text,
            finish_reason=_optional_string(first.get("finish_reason")),
            usage=_usage(data.get("usage"), "prompt_tokens", "completion_tokens"),
            provider_request_id=_request_id(response, data),
        )


def _raise_for_status(response: httpx.Response, provider_id: ModelProviderId) -> None:
    if response.is_success:
        return
    status = response.status_code
    if status in {401, 403}:
        category = ModelErrorCategory.AUTHENTICATION_REJECTED
    elif status == 429:
        category = ModelErrorCategory.RATE_LIMITED
    elif status in {400, 404, 409, 422}:
        category = ModelErrorCategory.REQUEST_INVALID
    elif status >= 500:
        category = ModelErrorCategory.PROVIDER_UNAVAILABLE
    else:
        category = ModelErrorCategory.PROVIDER_UNAVAILABLE
    raise ModelGatewayError(
        category,
        "model provider rejected the request",
        provider_id=provider_id.value,
        provider_request_id=_header_request_id(response),
        status_code=status,
    )


def _response_object(
    response: httpx.Response,
    provider_id: ModelProviderId,
) -> Mapping[str, Any]:
    try:
        data = response.json()
    except ValueError:
        _malformed_response(provider_id, response)
    if not isinstance(data, Mapping):
        _malformed_response(provider_id, response)
    return cast(Mapping[str, Any], data)


def _malformed_response(provider_id: ModelProviderId, response: httpx.Response) -> Never:
    raise ModelGatewayError(
        ModelErrorCategory.MALFORMED_RESPONSE,
        "model provider returned a malformed response",
        provider_id=provider_id.value,
        provider_request_id=_header_request_id(response),
    )


def _usage(value: object, input_name: str, output_name: str) -> ModelTokenUsage:
    if not isinstance(value, Mapping):
        return ModelTokenUsage()
    input_tokens = _optional_int(value.get(input_name))
    output_tokens = _optional_int(value.get(output_name))
    total_tokens = _optional_int(value.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return ModelTokenUsage(input_tokens, output_tokens, total_tokens)


def _request_id(response: httpx.Response, data: Mapping[str, Any]) -> str | None:
    return _header_request_id(response) or _optional_string(data.get("id"))


def _header_request_id(response: httpx.Response) -> str | None:
    request_id: str | None = response.headers.get("request-id")
    return request_id or response.headers.get("x-request-id")


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
