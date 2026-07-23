import type {
  BackendFailure,
  ExplainCallResult,
  HttpInvalidFailure,
  KnowledgeClient,
  KnowledgeRequest,
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

function aborted(error: unknown, signal: AbortSignal): boolean {
  return (
    signal.aborted ||
    (typeof DOMException !== "undefined" &&
      error instanceof DOMException &&
      error.name === "AbortError") ||
    (typeof error === "object" &&
      error !== null &&
      "name" in error &&
      error.name === "AbortError")
  );
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
      const parsed = parseBody(operation.response);
      if (!parsed.ok) {
        return parsed.failure;
      }
      const decoded = decodeSearchResponse(parsed.value);
      if (!operation.response.ok) {
        if (decoded.ok && decoded.value.status === "error") {
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
      if (decoded.value.status === "success" && decoded.value.results.length > request.limit) {
        return {
          kind: "http-invalid",
          reason: "response-shape",
          httpStatus: operation.response.status,
          message: INVALID_MESSAGE,
        };
      }
      return decoded.value.status === "error"
        ? backendFailure(
            decoded.value.error_category,
            decoded.value.message,
            operation.response.status,
          )
        : {
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
      const parsed = parseBody(operation.response);
      if (!parsed.ok) {
        return parsed.failure;
      }
      const decoded = decodeExplainResponse(parsed.value);
      if (!operation.response.ok) {
        if (decoded.ok && decoded.value.status === "error") {
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
      if (decoded.value.status === "error") {
        return backendFailure(
          decoded.value.error_category,
          decoded.value.message,
          operation.response.status,
        );
      }
      if (decoded.value.status === "unsupported") {
        return {
          kind: "unsupported",
          message: decoded.value.message.trim()
            ? decoded.value.message
            : UNSUPPORTED_MESSAGE,
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
