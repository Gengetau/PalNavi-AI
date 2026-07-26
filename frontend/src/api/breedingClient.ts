import type { HttpInvalidFailure } from "./contract";
import {
  type BreedingCallResult,
  type BreedingClient,
} from "./breedingContract";
import {
  decodeBreedingResponse,
  responseMatchesRequest,
} from "./breedingRuntimeValidation";
import { summarizeFastApiDetail } from "./runtimeValidation";
import {
  createFetchTransport,
  type HttpResponse,
  type HttpTransport,
} from "./transport";

const ROUTE_URL = "/api/v1/breeding/gender-aware-routes";
const NETWORK_MESSAGE =
  "The breeding service could not be reached. Check the local service and try again.";
const INVALID_MESSAGE =
  "The breeding service returned a response that did not match its contract.";

function invalid(
  response: HttpResponse,
  reason: HttpInvalidFailure["reason"],
  message = INVALID_MESSAGE,
): HttpInvalidFailure {
  return {
    kind: "http-invalid",
    reason,
    httpStatus: response.status,
    message,
  };
}

function parseBody(response: HttpResponse):
  | { ok: true; value: unknown }
  | { ok: false; failure: HttpInvalidFailure } {
  if (response.bodyTooLarge) {
    return { ok: false, failure: invalid(response, "response-too-large") };
  }
  if (response.bodyEncodingInvalid) {
    return { ok: false, failure: invalid(response, "malformed-encoding") };
  }
  const contentType = response.contentType;
  const mediaType = contentType?.split(";", 1)[0] ?? "";
  if (
    contentType === null ||
    /[\r\n\u2028\u2029]/.test(contentType) ||
    mediaType.match(
      /^application\/(?:json|[a-z0-9!#$&^_.+-]+\+json)$/i,
    )?.[0] !== mediaType
  ) {
    return { ok: false, failure: invalid(response, "content-type") };
  }
  if (response.bodyText.trim().length === 0) {
    return { ok: false, failure: invalid(response, "empty-body") };
  }
  try {
    return {
      ok: true,
      value: JSON.parse(response.bodyText) as unknown,
    };
  } catch {
    return { ok: false, failure: invalid(response, "malformed-json") };
  }
}

export function createBreedingClient(
  transport: HttpTransport = createFetchTransport(),
): BreedingClient {
  return {
    async plan(request, { signal }): Promise<BreedingCallResult> {
      if (signal.aborted) {
        return { kind: "aborted" };
      }
      let response: HttpResponse;
      try {
        response = await transport.postJson(ROUTE_URL, request, signal);
      } catch {
        return signal.aborted
          ? { kind: "aborted" }
          : { kind: "network-error", message: NETWORK_MESSAGE };
      }
      if (response.ok && response.status !== 200) {
        return invalid(response, "http-status-contract-conflict");
      }
      const parsed = parseBody(response);
      if (!parsed.ok) {
        return parsed.failure;
      }
      const decoded = decodeBreedingResponse(parsed.value);
      if (!decoded.ok) {
        if (!response.ok && response.status === 422) {
          const detail = summarizeFastApiDetail(parsed.value);
          if (detail !== null) {
            return invalid(response, "http-status", detail);
          }
        }
        return invalid(
          response,
          response.ok ? "response-shape" : "http-status",
        );
      }
      switch (decoded.value.status) {
        case "success":
          if (response.status !== 200 || !response.ok) {
            return invalid(response, "http-status-contract-conflict");
          }
          return responseMatchesRequest(decoded.value, request)
            ? { kind: "success", response: decoded.value }
            : invalid(response, "response-shape");
        case "gender_required":
          if (response.status !== 200 || !response.ok) {
            return invalid(response, "http-status-contract-conflict");
          }
          return responseMatchesRequest(decoded.value, request)
            ? { kind: "gender-required", response: decoded.value }
            : invalid(response, "response-shape");
        case "unreachable":
          if (response.status !== 200 || !response.ok) {
            return invalid(response, "http-status-contract-conflict");
          }
          return responseMatchesRequest(decoded.value, request)
            ? { kind: "unreachable", response: decoded.value }
            : invalid(response, "response-shape");
        case "invalid":
          return !response.ok &&
            (response.status === 404 || response.status === 422)
            ? {
                kind: "backend-invalid",
                response: decoded.value,
                httpStatus: response.status,
              }
            : invalid(response, "http-status-contract-conflict");
      }
    },
  };
}
