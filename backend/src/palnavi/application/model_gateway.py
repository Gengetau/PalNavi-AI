"""Provider-neutral contracts for asynchronous model text generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ModelProviderId(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    ZHIPU = "zhipu"
    BAILIAN = "bailian"
    CUSTOM = "custom"


class ModelMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: ModelMessageRole
    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("model message text must not be blank")


@dataclass(frozen=True, slots=True)
class ModelRequest:
    provider_id: ModelProviderId
    model_id: str
    messages: tuple[ModelMessage, ...]
    temperature: float | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must not be blank")
        if not self.messages:
            raise ValueError("at least one model message is required")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")


@dataclass(frozen=True, slots=True)
class ModelTokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    finish_reason: str | None
    usage: ModelTokenUsage
    provider_request_id: str | None


class ModelErrorCategory(StrEnum):
    CONFIGURATION_INVALID = "configuration_invalid"
    AUTHENTICATION_REJECTED = "authentication_rejected"
    RATE_LIMITED = "rate_limited"
    REQUEST_INVALID = "request_invalid"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_RESPONSE = "malformed_response"
    UNKNOWN_PROVIDER = "unknown_provider"


@dataclass(eq=False, slots=True)
class ModelGatewayError(Exception):
    category: ModelErrorCategory
    message: str
    provider_id: str | None = None
    provider_request_id: str | None = None
    status_code: int | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

    def __str__(self) -> str:
        details = [self.category.value, self.message]
        if self.provider_id is not None:
            details.append(f"provider={self.provider_id}")
        if self.status_code is not None:
            details.append(f"status={self.status_code}")
        if self.provider_request_id is not None:
            details.append(f"request_id={self.provider_request_id}")
        return ": ".join(details)


class ModelGateway(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...


@dataclass(frozen=True, slots=True)
class ModelGenerationService:
    gateway: ModelGateway
    provider_id: ModelProviderId
    model_id: str

    async def generate(
        self,
        messages: tuple[ModelMessage, ...],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelResponse:
        return await self.gateway.generate(
            ModelRequest(
                provider_id=self.provider_id,
                model_id=self.model_id,
                messages=messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        )
