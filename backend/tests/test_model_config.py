import asyncio
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
    smoke,
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
    "base_url",
    [
        "https://[::1",
        "https://api.openai.com:bad/v1",
        "https://api.openai.com:70000/v1",
    ],
)
def test_malformed_ports_and_ipv6_are_normalized_before_client_creation(
    base_url: str,
) -> None:
    with pytest.raises(ModelGatewayError) as caught:
        load_model_provider_config(
            {
                "PALNAVI_MODEL_PROVIDER": "custom",
                "PALNAVI_MODEL_NAME": "test-model",
                "PALNAVI_CUSTOM_BASE_URL": base_url,
                "PALNAVI_CUSTOM_API_KEY": "test-token",
            }
        )

    assert caught.value.category is ModelErrorCategory.CONFIGURATION_INVALID
    assert str(caught.value) == (
        "configuration_invalid: provider base URL is malformed: provider=custom"
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://models.example.test:443/v1",
        "http://[::1]:8080/v1",
    ],
)
def test_valid_https_and_ipv6_loopback_urls_are_preserved(base_url: str) -> None:
    config = load_model_provider_config(
        {
            "PALNAVI_MODEL_PROVIDER": "custom",
            "PALNAVI_MODEL_NAME": "test-model",
            "PALNAVI_CUSTOM_BASE_URL": base_url,
            "PALNAVI_CUSTOM_API_KEY": "test-token",
        }
    )

    assert config.base_url == base_url


def test_secret_bearing_malformed_url_is_redacted() -> None:
    base_url = "https://url-secret-marker@[::1"

    with pytest.raises(ModelGatewayError) as caught:
        load_model_provider_config(
            {
                "PALNAVI_MODEL_PROVIDER": "custom",
                "PALNAVI_MODEL_NAME": "test-model",
                "PALNAVI_CUSTOM_BASE_URL": base_url,
                "PALNAVI_CUSTOM_API_KEY": "api-secret-marker",
            }
        )

    rendered = f"{caught.value!s} {caught.value!r}"
    assert caught.value.category is ModelErrorCategory.CONFIGURATION_INVALID
    assert base_url not in rendered
    assert "url-secret-marker" not in rendered
    assert "api-secret-marker" not in rendered


def test_smoke_reports_malformed_url_without_traceback_or_client_creation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client_created = False

    def fail_if_client_is_created(config: ModelProviderConfig) -> None:
        nonlocal client_created
        client_created = True

    monkeypatch.setenv("PALNAVI_MODEL_PROVIDER", "custom")
    monkeypatch.setenv("PALNAVI_MODEL_NAME", "test-model")
    monkeypatch.setenv("PALNAVI_CUSTOM_BASE_URL", "https://url-secret-marker@[::1")
    monkeypatch.setenv("PALNAVI_CUSTOM_API_KEY", "api-secret-marker")
    monkeypatch.setattr(smoke, "create_model_gateway", fail_if_client_is_created)

    exit_code = asyncio.run(smoke._run("No request should be sent."))
    captured = capsys.readouterr()

    assert exit_code == 2
    assert client_created is False
    assert captured.err == ""
    assert "Traceback" not in captured.out
    assert "url-secret-marker" not in captured.out
    assert "api-secret-marker" not in captured.out
    assert "configuration_invalid" in captured.out


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
