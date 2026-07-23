# Model Provider Gateway

PalNavi exposes one asynchronous text-generation contract while keeping credentials and HTTP
protocol details in infrastructure. Model identifiers are configuration values rather than an
allowlist, so a provider can add models without a code change. An unknown provider identifier
fails with a structured error and never falls back to another provider.

`POST /api/v1/knowledge/explain` is the only public route that can call this gateway, and it does
so only after deterministic retrieval yields usable evidence. Breeding planning and
`POST /api/v1/knowledge/search` never load provider configuration or call a model. Exact breeding
data, probabilities, and costs remain the responsibility of versioned structured data and the
deterministic planner; model output is never their source of truth.

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

These variables are optional for the application as a whole. The explanation dependency loads
them lazily only after retrieval yields usable evidence; an unsupported response therefore causes
zero configuration, gateway, or HTTP-client calls. Search and breeding never load model settings.
The explanation service explicitly requests at most 512 output tokens; the 1024 environment
default remains an adapter fallback and smoke-command setting.

For the selected DeepSeek setup, set `PALNAVI_MODEL_PROVIDER` to `deepseek` and
`PALNAVI_MODEL_NAME` to `deepseek-v4-flash`; inject `DEEPSEEK_API_KEY` from the local secret
source. Do not place the key in Python, tests, documentation, command history, or reports.

Configuration objects hide their credential field from `repr`. Gateway errors contain only a
normalized category, safe message, provider ID, status code, and request ID. Provider response
bodies are deliberately excluded because they can echo request or credential material.

## Explanation request lifecycle

The explanation request dependency creates deferred generation ownership per request. Retrieval
runs first; when usable evidence exists, configuration is loaded and at most one gateway call is
made. Missing or invalid configuration becomes a controlled explanation error without affecting
search or deterministic breeding. Any HTTP client constructed for the request is owned by that
dependency and closed during cancellation-shielded cleanup.

## Custom endpoints

Custom providers must implement non-streaming OpenAI-compatible `/chat/completions` behavior.
Remote endpoints require HTTPS and an API key. Plain HTTP and a missing API key are allowed only
for `localhost`, `127.0.0.1`, or `::1`. Base URLs containing usernames, passwords, query strings,
or fragments are rejected.

## Offline tests and explicit live smoke

The adapter suite uses `httpx.MockTransport`, and explanation tests use a deterministic fake
gateway with synthetic fixtures. Focused guards block TCP connections, UDP sends, forward and
reverse DNS resolution, and subprocess execution. No automated test contacts a provider, consumes
paid tokens, loads a real credential, or invokes a filesystem-provider command. Run the adapter
tests from `backend`:

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
