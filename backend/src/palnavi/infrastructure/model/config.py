"""Safe model-provider configuration from explicit values or environment variables."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Never, final
from urllib.parse import SplitResult, urlsplit, urlunsplit

from palnavi.application import ModelErrorCategory, ModelGatewayError, ModelProviderId


@final
class SecretValue:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(***)"

    def __str__(self) -> str:
        return "***"


@dataclass(frozen=True, slots=True)
class ModelProviderConfig:
    provider_id: ModelProviderId
    model_id: str
    base_url: str
    api_key: SecretValue | None = field(default=None, repr=False)
    timeout_seconds: float = 30.0
    default_max_output_tokens: int = 1024


_DEFAULT_BASE_URLS: dict[ModelProviderId, str] = {
    ModelProviderId.OPENAI: "https://api.openai.com/v1",
    ModelProviderId.ANTHROPIC: "https://api.anthropic.com",
    ModelProviderId.DEEPSEEK: "https://api.deepseek.com",
    ModelProviderId.ZHIPU: "https://open.bigmodel.cn/api/paas/v4",
}

_API_KEY_ENV: dict[ModelProviderId, str] = {
    ModelProviderId.OPENAI: "OPENAI_API_KEY",
    ModelProviderId.ANTHROPIC: "ANTHROPIC_API_KEY",
    ModelProviderId.DEEPSEEK: "DEEPSEEK_API_KEY",
    ModelProviderId.ZHIPU: "ZAI_API_KEY",
    ModelProviderId.BAILIAN: "DASHSCOPE_API_KEY",
    ModelProviderId.CUSTOM: "PALNAVI_CUSTOM_API_KEY",
}

_BASE_URL_ENV: dict[ModelProviderId, str] = {
    ModelProviderId.OPENAI: "OPENAI_BASE_URL",
    ModelProviderId.ANTHROPIC: "ANTHROPIC_BASE_URL",
    ModelProviderId.DEEPSEEK: "DEEPSEEK_BASE_URL",
    ModelProviderId.ZHIPU: "ZHIPU_BASE_URL",
    ModelProviderId.BAILIAN: "PALNAVI_BAILIAN_BASE_URL",
    ModelProviderId.CUSTOM: "PALNAVI_CUSTOM_BASE_URL",
}


def load_model_provider_config(
    environ: Mapping[str, str] | None = None,
) -> ModelProviderConfig:
    values = os.environ if environ is None else environ
    provider_text = values.get("PALNAVI_MODEL_PROVIDER", "").strip().lower()
    try:
        provider_id = ModelProviderId(provider_text)
    except ValueError:
        category = (
            ModelErrorCategory.CONFIGURATION_INVALID
            if not provider_text
            else ModelErrorCategory.UNKNOWN_PROVIDER
        )
        raise ModelGatewayError(category, "model provider is missing or unsupported") from None

    model_id = values.get("PALNAVI_MODEL_NAME", "").strip()
    base_url = values.get(_BASE_URL_ENV[provider_id], "").strip()
    if not base_url:
        base_url = _DEFAULT_BASE_URLS.get(provider_id, "")

    key_text = values.get(_API_KEY_ENV[provider_id], "").strip()
    config = ModelProviderConfig(
        provider_id=provider_id,
        model_id=model_id,
        base_url=base_url,
        api_key=SecretValue(key_text) if key_text else None,
        timeout_seconds=_positive_float(values, "PALNAVI_MODEL_TIMEOUT_SECONDS", 30.0),
        default_max_output_tokens=_positive_int(values, "PALNAVI_MODEL_MAX_OUTPUT_TOKENS", 1024),
    )
    validate_model_provider_config(config)
    return config


def validate_model_provider_config(config: ModelProviderConfig) -> None:
    if not config.model_id.strip():
        _configuration_error("model name is required", config.provider_id)
    if not math.isfinite(config.timeout_seconds) or config.timeout_seconds <= 0:
        _configuration_error("timeout must be a positive finite number", config.provider_id)
    if config.default_max_output_tokens <= 0:
        _configuration_error("default max output tokens must be positive", config.provider_id)
    if not config.base_url.strip():
        _configuration_error("provider base URL is required", config.provider_id)

    parsed = _validated_url(config.base_url, config.provider_id)
    loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        _configuration_error(
            "provider base URL must use HTTPS except for loopback HTTP",
            config.provider_id,
        )
    has_api_key = config.api_key is not None and bool(config.api_key.value.strip())
    if config.provider_id is not ModelProviderId.CUSTOM and not has_api_key:
        _configuration_error("provider API key is required", config.provider_id)
    if config.provider_id is ModelProviderId.CUSTOM and not loopback and not has_api_key:
        _configuration_error("remote custom providers require an API key", config.provider_id)


def normalized_base_url(config: ModelProviderConfig) -> str:
    parsed = _validated_url(config.base_url, config.provider_id)
    normalized = SplitResult(
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        "",
        "",
    )
    return urlunsplit(normalized)


def _validated_url(value: str, provider_id: ModelProviderId) -> SplitResult:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        _configuration_error("provider base URL must be absolute", provider_id)
    if parsed.username is not None or parsed.password is not None:
        _configuration_error("provider base URL must not contain credentials", provider_id)
    if parsed.query or parsed.fragment:
        _configuration_error("provider base URL must not contain a query or fragment", provider_id)
    return parsed


def _positive_float(values: Mapping[str, str], name: str, default: float) -> float:
    raw = values.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ModelGatewayError(
            ModelErrorCategory.CONFIGURATION_INVALID,
            f"{name} must be numeric",
        ) from None
    if not math.isfinite(value) or value <= 0:
        raise ModelGatewayError(
            ModelErrorCategory.CONFIGURATION_INVALID,
            f"{name} must be a positive finite number",
        )
    return value


def _positive_int(values: Mapping[str, str], name: str, default: int) -> int:
    raw = values.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ModelGatewayError(
            ModelErrorCategory.CONFIGURATION_INVALID,
            f"{name} must be an integer",
        ) from None
    if value <= 0:
        raise ModelGatewayError(
            ModelErrorCategory.CONFIGURATION_INVALID,
            f"{name} must be positive",
        )
    return value


def _configuration_error(message: str, provider_id: ModelProviderId) -> Never:
    raise ModelGatewayError(
        ModelErrorCategory.CONFIGURATION_INVALID,
        message,
        provider_id=provider_id.value,
    )
