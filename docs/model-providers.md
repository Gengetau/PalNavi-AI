# Model Provider Gateway

PalNavi exposes one asynchronous text-generation contract while keeping credentials and HTTP
protocol details in infrastructure. Model identifiers are configuration values rather than an
allowlist, so a provider can add models without a code change. An unknown provider identifier
fails with a structured error and never falls back to another provider.

This gateway is not called by breeding planning or by a public API route. Exact breeding data,
probabilities, and costs remain the responsibility of versioned structured data and the
deterministic planner.

## Providers and protocols

| Provider ID | Protocol | Default base URL |
| --- | --- | --- |
| `openai` | native Responses API | `https://api.openai.com/v1` |
| `anthropic` | native Messages API | `https://api.anthropic.com` |
| `deepseek` | OpenAI-compatible Chat Completions | `https://api.deepseek.com` |
| `zhipu` | OpenAI-compatible Chat Completions | `https://open.bigmodel.cn/api/paas/v4` |
| `bailian` | OpenAI-compatible Chat Completions | required explicitly |
| `custom` | OpenAI-compatible Chat Completions | required explicitly |

The protocol mapping follows the providers' current official interfaces:

- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create)
- [DeepSeek chat completion API](https://api-docs.deepseek.com/api/create-chat-completion/)
- [Zhipu OpenAI SDK compatibility](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)
- [Alibaba Model Studio regional base URLs](https://help.aliyun.com/en/model-studio/base-url)

Alibaba Model Studio keys and endpoints are region-specific. Consequently,
`PALNAVI_BAILIAN_BASE_URL` has no default and must identify the correct region or workspace.

## Configuration

Copy `.env.example` only as a local reference. The application reads the process environment;
an IDE, shell, container runtime, or secret manager must inject those variables. The real
repository-root `.env` is ignored by Git and must never be committed.

Common variables:

| Variable | Purpose |
| --- | --- |
| `PALNAVI_MODEL_PROVIDER` | One of the six provider IDs above |
| `PALNAVI_MODEL_NAME` | Provider model identifier |
| `PALNAVI_MODEL_TIMEOUT_SECONDS` | Optional positive timeout; default `30` |
| `PALNAVI_MODEL_MAX_OUTPUT_TOKENS` | Anthropic fallback and smoke limit; default `1024` |

Provider credentials and optional base overrides:

| Provider | Credential | Base URL override |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL` |
| Zhipu | `ZAI_API_KEY` | `ZHIPU_BASE_URL` |
| Bailian | `DASHSCOPE_API_KEY` | `PALNAVI_BAILIAN_BASE_URL` (required) |
| custom | `PALNAVI_CUSTOM_API_KEY` | `PALNAVI_CUSTOM_BASE_URL` (required) |

For the selected DeepSeek setup, set `PALNAVI_MODEL_PROVIDER` to `deepseek` and
`PALNAVI_MODEL_NAME` to `deepseek-v4-flash`; inject `DEEPSEEK_API_KEY` from the local secret
source. Do not place the key in Python, tests, documentation, command history, or reports.

Configuration objects hide their credential field from `repr`. Gateway errors contain only a
normalized category, safe message, provider ID, status code, and request ID. Provider response
bodies are deliberately excluded because they can echo request or credential material.

## Custom endpoints

Custom providers must implement non-streaming OpenAI-compatible `/chat/completions` behavior.
Remote endpoints require HTTPS and an API key. Plain HTTP and a missing API key are allowed only
for `localhost`, `127.0.0.1`, or `::1`. Base URLs containing usernames, passwords, query strings,
or fragments are rejected.

## Offline tests and explicit live smoke

The automated suite uses `httpx.MockTransport`; it never contacts a provider and never consumes
paid tokens. Run it from `backend`:

```powershell
python -m pytest tests/test_model_config.py tests/test_model_adapters.py
```

A real call is available only through an explicit local command after the process environment
has been configured. It prints the generated text but never configuration or credentials:

```powershell
python -m palnavi.infrastructure.model.smoke --live --message "Reply with OK."
```

Omitting `--live` exits before configuration loading or network access. Never run the live smoke
command in CI. Missing or invalid configuration is reported through a normalized safe message
without a traceback or network call. The gateway is non-streaming and does not retry failed calls.
