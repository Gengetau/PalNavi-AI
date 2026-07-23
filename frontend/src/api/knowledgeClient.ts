import type {
  BackendFailure,
  ExplainErrorCategory,
  ExplainCallResult,
  HttpInvalidFailure,
  KnowledgeClient,
  KnowledgeRequest,
  SearchErrorCategory,
  SearchCallResult,
} from "./contract";
import {
  decodeExplainResponse,
  decodeSearchResponse,
  summarizeFastApiDetail,
} from "./runtimeValidation";
import {
  createFetchTransport,
  type HttpResponse,
  type HttpTransport,
} from "./transport";

const SEARCH_URL = "/api/v1/knowledge/search";
const EXPLAIN_URL = "/api/v1/knowledge/explain";
const NETWORK_MESSAGE =
  "The knowledge service could not be reached. Check your connection and try again.";
const INVALID_MESSAGE =
  "The knowledge service returned a response that did not match its contract.";
const BACKEND_MESSAGE = "The knowledge service reported an error.";
const UNSUPPORTED_MESSAGE =
  "A grounded explanation is not supported for this query.";
const SEARCH_ERROR_STATUSES: Record<SearchErrorCategory, readonly number[]> = {
  request_invalid: [422],
  repository_unavailable: [503],
  repository_invalid_state: [503],
};
const EXPLAIN_ERROR_STATUSES: Record<ExplainErrorCategory, readonly number[]> = {
  request_invalid: [422, 502],
  repository_unavailable: [503],
  repository_invalid_state: [503],
  configuration_invalid: [503],
  authentication_rejected: [502],
  rate_limited: [503],
  timeout: [504],
  provider_unavailable: [503],
  malformed_response: [502],
  unknown_provider: [503],
  invalid_grounded_output: [502],
};

function aborted(_error: unknown, signal: AbortSignal): boolean {
  return signal.aborted;
}

function parseBody(response: HttpResponse):
  | { ok: true; value: unknown }
  | { ok: false; failure: HttpInvalidFailure } {
  if (response.bodyTooLarge) {
    return {
      ok: false,
      failure: {
        kind: "http-invalid",
        reason: "response-too-large",
        httpStatus: response.status,
        message: INVALID_MESSAGE,
      },
    };
  }
  if (response.bodyEncodingInvalid) {
    return {
      ok: false,
      failure: {
        kind: "http-invalid",
        reason: "malformed-encoding",
        httpStatus: response.status,
        message: INVALID_MESSAGE,
      },
    };
  }
  const contentType = response.contentType;
  const mediaType = contentType?.split(";", 1)[0] ?? "";
  const mediaTypeMatch = mediaType.match(
    /^application\/(?:json|[a-z0-9!#$&^_.+-]+\+json)$/i,
  );
  if (
    contentType === null ||
    /[\r\n\u2028\u2029]/.test(contentType) ||
    mediaTypeMatch?.[0] !== mediaType
  ) {
    return {
      ok: false,
      failure: {
        kind: "http-invalid",
        reason: "content-type",
        httpStatus: response.status,
        message: INVALID_MESSAGE,
      },
    };
  }
  if (response.bodyText.trim().length === 0) {
    return {
      ok: false,
      failure: {
        kind: "http-invalid",
        reason: "empty-body",
        httpStatus: response.status,
        message: INVALID_MESSAGE,
      },
    };
  }
  try {
    return { ok: true, value: JSON.parse(response.bodyText) as unknown };
  } catch {
    return {
      ok: false,
      failure: {
        kind: "http-invalid",
        reason: "malformed-json",
        httpStatus: response.status,
        message: INVALID_MESSAGE,
      },
    };
  }
}

function backendFailure(
  category: string | null | undefined,
  message: string | null | undefined,
  status: number,
): BackendFailure {
  return {
    kind: "backend-error",
    errorCategory: category ?? null,
    message: message?.trim() ? message : BACKEND_MESSAGE,
    httpStatus: status,
  };
}

function invalidHttp(
  response: HttpResponse,
  body: unknown,
): HttpInvalidFailure {
  return {
    kind: "http-invalid",
    reason: "http-status",
    httpStatus: response.status,
    message: summarizeFastApiDetail(body) ?? INVALID_MESSAGE,
  };
}

async function post(
  transport: HttpTransport,
  url: string,
  request: Readonly<KnowledgeRequest>,
  signal: AbortSignal,
): Promise<
  | { kind: "response"; response: HttpResponse }
  | { kind: "network-error"; message: string }
  | { kind: "aborted" }
> {
  if (signal.aborted) {
    return { kind: "aborted" };
  }
  try {
    return {
      kind: "response",
      response: await transport.postJson(url, request, signal),
    };
  } catch (error) {
    return aborted(error, signal)
      ? { kind: "aborted" }
      : { kind: "network-error", message: NETWORK_MESSAGE };
  }
}

export function createKnowledgeClient(
  transport: HttpTransport = createFetchTransport(),
): KnowledgeClient {
  return {
    async search(request, { signal }): Promise<SearchCallResult> {
      const operation = await post(transport, SEARCH_URL, request, signal);
      if (operation.kind !== "response") {
        return operation;
      }
      if (operation.response.ok && operation.response.status !== 200) {
        return {
          kind: "http-invalid",
          reason: "http-status-contract-conflict",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      const parsed = parseBody(operation.response);
      if (!parsed.ok) {
        return parsed.failure;
      }
      const decoded = decodeSearchResponse(parsed.value);
      if (!operation.response.ok) {
        if (decoded.ok && decoded.value.status === "error") {
          if (
            !SEARCH_ERROR_STATUSES[decoded.value.error_category].includes(
              operation.response.status,
            )
          ) {
            return {
              kind: "http-invalid",
              reason: "http-status-contract-conflict",
              httpStatus: operation.response.status,
              message: INVALID_MESSAGE,
            };
          }
          return backendFailure(
            decoded.value.error_category,
            decoded.value.message,
            operation.response.status,
          );
        }
        if (decoded.ok) {
          return {
            kind: "http-invalid",
            reason: "http-status-contract-conflict",
            httpStatus: operation.response.status,
            message: INVALID_MESSAGE,
          };
        }
        return invalidHttp(operation.response, parsed.value);
      }
      if (!decoded.ok) {
        return {
          kind: "http-invalid",
          reason: "response-shape",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      if (
        decoded.value.status === "success" &&
        (operation.response.status !== 200 ||
          decoded.value.results.length > request.limit ||
          (request.synthetic_only &&
            decoded.value.results.some(
              (item) => item.classification !== "synthetic",
            )))
      ) {
        return {
          kind: "http-invalid",
          reason:
            operation.response.status === 200
              ? "response-shape"
              : "http-status-contract-conflict",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      if (decoded.value.status === "error") {
        return {
          kind: "http-invalid",
          reason: "http-status-contract-conflict",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      return {
        kind: "search-success",
        results: decoded.value.results,
        message: decoded.value.message ?? null,
      };
    },

    async explain(request, { signal }): Promise<ExplainCallResult> {
      const operation = await post(transport, EXPLAIN_URL, request, signal);
      if (operation.kind !== "response") {
        return operation;
      }
      if (operation.response.ok && operation.response.status !== 200) {
        return {
          kind: "http-invalid",
          reason: "http-status-contract-conflict",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      const parsed = parseBody(operation.response);
      if (!parsed.ok) {
        return parsed.failure;
      }
      const decoded = decodeExplainResponse(parsed.value);
      if (!operation.response.ok) {
        if (decoded.ok && decoded.value.status === "error") {
          if (
            !EXPLAIN_ERROR_STATUSES[decoded.value.error_category].includes(
              operation.response.status,
            )
          ) {
            return {
              kind: "http-invalid",
              reason: "http-status-contract-conflict",
              httpStatus: operation.response.status,
              message: INVALID_MESSAGE,
            };
          }
          return backendFailure(
            decoded.value.error_category,
            decoded.value.message,
            operation.response.status,
          );
        }
        if (decoded.ok) {
          return {
            kind: "http-invalid",
            reason: "http-status-contract-conflict",
            httpStatus: operation.response.status,
            message: INVALID_MESSAGE,
          };
        }
        return invalidHttp(operation.response, parsed.value);
      }
      if (!decoded.ok) {
        return {
          kind: "http-invalid",
          reason: "response-shape",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      if (
        decoded.value.status !== "error" &&
        operation.response.status !== 200
      ) {
        return {
          kind: "http-invalid",
          reason: "http-status-contract-conflict",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      if (decoded.value.status === "error") {
        return {
          kind: "http-invalid",
          reason: "http-status-contract-conflict",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      if (decoded.value.status === "unsupported") {
        return {
          kind: "unsupported",
          message: decoded.value.message.trim()
            ? decoded.value.message
            : UNSUPPORTED_MESSAGE,
        };
      }
      if (decoded.value.citations.length > Math.min(request.limit, 5)) {
        return {
          kind: "http-invalid",
          reason: "response-shape",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      return {
        kind: "explain-success",
        answer: decoded.value.answer,
        citations: decoded.value.citations,
        usage: decoded.value.usage ?? null,
      };
    },
  };
}
