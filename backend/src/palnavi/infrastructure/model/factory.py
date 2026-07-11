"""Provider selection for the three supported HTTP protocols."""

from __future__ import annotations

import httpx

from palnavi.application import ModelErrorCategory, ModelGatewayError, ModelProviderId
from palnavi.infrastructure.model.adapters import (
    AnthropicMessagesAdapter,
    HttpModelGateway,
    OpenAICompatibleChatAdapter,
    OpenAIResponsesAdapter,
)
from palnavi.infrastructure.model.config import (
    ModelProviderConfig,
    validate_model_provider_config,
)


def create_model_gateway(
    config: ModelProviderConfig,
    client: httpx.AsyncClient | None = None,
) -> HttpModelGateway:
    validate_model_provider_config(config)
    if config.provider_id is ModelProviderId.OPENAI:
        return OpenAIResponsesAdapter(config, client)
    if config.provider_id is ModelProviderId.ANTHROPIC:
        return AnthropicMessagesAdapter(config, client)
    if config.provider_id in {
        ModelProviderId.DEEPSEEK,
        ModelProviderId.ZHIPU,
        ModelProviderId.BAILIAN,
        ModelProviderId.CUSTOM,
    }:
        return OpenAICompatibleChatAdapter(config, client)
    raise ModelGatewayError(
        ModelErrorCategory.UNKNOWN_PROVIDER,
        "model provider is unsupported",
        provider_id=str(config.provider_id),
    )
