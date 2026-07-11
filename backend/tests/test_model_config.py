from dataclasses import asdict

import pytest

from palnavi.application import ModelErrorCategory, ModelGatewayError, ModelProviderId
from palnavi.infrastructure.model import (
    AnthropicMessagesAdapter,
    ModelProviderConfig,
    OpenAICompatibleChatAdapter,
    OpenAIResponsesAdapter,
    SecretValue,
    create_model_gateway,
    load_model_provider_config,
)


def test_deepseek_v4_flash_configuration_uses_official_default_base_url() -> None:
    config = load_model_provider_config(
        {
            "PALNAVI_MODEL_PROVIDER": "deepseek",
            "PALNAVI_MODEL_NAME": "deepseek-v4-flash",
            "DEEPSEEK_API_KEY": "test-secret-marker",
        }
    )

    assert config.provider_id is ModelProviderId.DEEPSEEK
    assert config.model_id == "deepseek-v4-flash"
    assert config.base_url == "https://api.deepseek.com"
    assert "test-secret-marker" not in repr(config)
    assert "test-secret-marker" not in repr(config.api_key)
    serialized = asdict(config)
    assert serialized["api_key"] != "test-secret-marker"
    assert "test-secret-marker" not in repr(serialized)


@pytest.mark.parametrize(
    ("provider_id", "base_url", "adapter_type"),
    [
        (ModelProviderId.OPENAI, "https://api.openai.com/v1", OpenAIResponsesAdapter),
        (ModelProviderId.ANTHROPIC, "https://api.anthropic.com", AnthropicMessagesAdapter),
        (ModelProviderId.DEEPSEEK, "https://api.deepseek.com", OpenAICompatibleChatAdapter),
        (
            ModelProviderId.ZHIPU,
            "https://open.bigmodel.cn/api/paas/v4",
            OpenAICompatibleChatAdapter,
        ),
        (
            ModelProviderId.BAILIAN,
            "https://dashscope.example.test/compatible-mode/v1",
            OpenAICompatibleChatAdapter,
        ),
        (ModelProviderId.CUSTOM, "http://127.0.0.1:9000/v1", OpenAICompatibleChatAdapter),
    ],
)
def test_factory_maps_six_provider_ids_to_three_protocol_adapters(
    provider_id: ModelProviderId,
    base_url: str,
    adapter_type: type[object],
) -> None:
    config = ModelProviderConfig(
        provider_id=provider_id,
        model_id="test-model",
        base_url=base_url,
        api_key=None if provider_id is ModelProviderId.CUSTOM else SecretValue("test-token"),
    )

    assert isinstance(create_model_gateway(config), adapter_type)


def test_unknown_provider_fails_without_fallback() -> None:
    with pytest.raises(ModelGatewayError) as caught:
        load_model_provider_config(
            {
                "PALNAVI_MODEL_PROVIDER": "not-a-provider",
                "PALNAVI_MODEL_NAME": "test-model",
            }
        )

    assert caught.value.category is ModelErrorCategory.UNKNOWN_PROVIDER


def test_bailian_requires_explicit_region_or_workspace_base_url() -> None:
    with pytest.raises(ModelGatewayError) as caught:
        load_model_provider_config(
            {
                "PALNAVI_MODEL_PROVIDER": "bailian",
                "PALNAVI_MODEL_NAME": "test-model",
                "DASHSCOPE_API_KEY": "test-token",
            }
        )

    assert caught.value.category is ModelErrorCategory.CONFIGURATION_INVALID
    assert "base URL" in str(caught.value)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://models.example.test/v1",
        "https://user:password@models.example.test/v1",
        "https://models.example.test/v1?workspace=one",
        "https://models.example.test/v1#fragment",
    ],
)
def test_custom_base_url_rejects_unsafe_forms(base_url: str) -> None:
    with pytest.raises(ModelGatewayError) as caught:
        create_model_gateway(
            ModelProviderConfig(
                provider_id=ModelProviderId.CUSTOM,
                model_id="test-model",
                base_url=base_url,
                api_key=SecretValue("test-token"),
            )
        )

    assert caught.value.category is ModelErrorCategory.CONFIGURATION_INVALID


def test_remote_custom_provider_requires_key_but_loopback_does_not() -> None:
    with pytest.raises(ModelGatewayError) as caught:
        create_model_gateway(
            ModelProviderConfig(
                provider_id=ModelProviderId.CUSTOM,
                model_id="test-model",
                base_url="https://models.example.test/v1",
            )
        )

    assert caught.value.category is ModelErrorCategory.CONFIGURATION_INVALID
    local = create_model_gateway(
        ModelProviderConfig(
            provider_id=ModelProviderId.CUSTOM,
            model_id="test-model",
            base_url="http://localhost:8080/v1",
        )
    )
    assert isinstance(local, OpenAICompatibleChatAdapter)


@pytest.mark.parametrize(
    "missing_name",
    ["PALNAVI_MODEL_PROVIDER", "PALNAVI_MODEL_NAME", "DEEPSEEK_API_KEY"],
)
def test_required_configuration_is_reported_safely(missing_name: str) -> None:
    values = {
        "PALNAVI_MODEL_PROVIDER": "deepseek",
        "PALNAVI_MODEL_NAME": "deepseek-v4-flash",
        "DEEPSEEK_API_KEY": "test-secret-marker",
    }
    values.pop(missing_name)

    with pytest.raises(ModelGatewayError) as caught:
        load_model_provider_config(values)

    assert caught.value.category is ModelErrorCategory.CONFIGURATION_INVALID
    assert "test-secret-marker" not in str(caught.value)
    assert "test-secret-marker" not in repr(caught.value)
