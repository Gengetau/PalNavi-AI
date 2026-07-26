import { BREEDING_DATASET_ID } from "./breedingContract";
import {
  decodeSpeciesCatalogResponse,
  type SpeciesCatalogCallResult,
  type SpeciesCatalogClient,
} from "./breedingCatalogContract";
import type { HttpInvalidFailure } from "./contract";
import {
  MAX_RESPONSE_BYTES,
  type HttpResponse,
} from "./transport";

const CATALOG_URL =
  `/api/v1/palworld/species-catalog?dataset_id=${BREEDING_DATASET_ID}`;
const NETWORK_MESSAGE =
  "The species catalog could not be reached. Manual stable-ID entry remains available.";
const INVALID_MESSAGE =
  "The species catalog returned a response that did not match its contract.";

export interface SpeciesCatalogHttpResponse extends HttpResponse {
  redirected: boolean;
}

export interface SpeciesCatalogTransport {
  getJson(
    url: string,
    signal: AbortSignal,
  ): Promise<SpeciesCatalogHttpResponse>;
}

function cancelBodyWithoutWaiting(response: Response): void {
  try {
    void response.body?.cancel().catch(() => undefined);
  } catch {
    // Bounded rejection must not wait on cleanup.
  }
}

function cancelReaderWithoutWaiting(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): void {
  try {
    void reader.cancel().catch(() => undefined);
  } catch {
    // Bounded rejection must not wait on cleanup.
  }
}

async function readBoundedBody(
  response: Response,
): Promise<{ text: string; tooLarge: boolean; encodingInvalid: boolean }> {
  const declaredLength = response.headers.get("content-length");
  if (
    declaredLength !== null &&
    /^\d+$/.test(declaredLength) &&
    Number(declaredLength) > MAX_RESPONSE_BYTES
  ) {
    cancelBodyWithoutWaiting(response);
    return { text: "", tooLarge: true, encodingInvalid: false };
  }
  if (response.body === null) {
    return { text: "", tooLarge: false, encodingInvalid: false };
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const parts: string[] = [];
  let received = 0;
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) {
      try {
        parts.push(decoder.decode());
        return {
          text: parts.join(""),
          tooLarge: false,
          encodingInvalid: false,
        };
      } catch {
        cancelReaderWithoutWaiting(reader);
        return { text: "", tooLarge: false, encodingInvalid: true };
      }
    }
    received += chunk.value.byteLength;
    if (received > MAX_RESPONSE_BYTES) {
      cancelReaderWithoutWaiting(reader);
      return { text: "", tooLarge: true, encodingInvalid: false };
    }
    try {
      parts.push(decoder.decode(chunk.value, { stream: true }));
    } catch {
      cancelReaderWithoutWaiting(reader);
      return { text: "", tooLarge: false, encodingInvalid: true };
    }
  }
}

export function createSpeciesCatalogFetchTransport(
  fetchImplementation?: typeof fetch,
): SpeciesCatalogTransport {
  return {
    async getJson(url, signal) {
      const performFetch = fetchImplementation ?? globalThis.fetch;
      const response = await performFetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal,
        credentials: "omit",
        mode: "same-origin",
        redirect: "error",
        cache: "no-store",
      });
      if (response.ok && response.status !== 200) {
        cancelBodyWithoutWaiting(response);
        return {
          ok: response.ok,
          status: response.status,
          statusText: response.statusText,
          contentType: response.headers.get("content-type"),
          bodyText: "",
          bodyTooLarge: false,
          bodyEncodingInvalid: false,
          redirected: response.redirected,
        };
      }
      const body = await readBoundedBody(response);
      return {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        contentType: response.headers.get("content-type"),
        bodyText: body.text,
        bodyTooLarge: body.tooLarge,
        bodyEncodingInvalid: body.encodingInvalid,
        redirected: response.redirected,
      };
    },
  };
}

function invalid(
  response: SpeciesCatalogHttpResponse,
  reason: HttpInvalidFailure["reason"],
): HttpInvalidFailure {
  return {
    kind: "http-invalid",
    reason,
    httpStatus: response.status,
    message: INVALID_MESSAGE,
  };
}

function parseBody(response: SpeciesCatalogHttpResponse):
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
    /[\r\n\u2028\u2029]/u.test(contentType) ||
    mediaType.match(
      /^application\/(?:json|[a-z0-9!#$&^_.+-]+\+json)$/iu,
    )?.[0] !== mediaType
  ) {
    return { ok: false, failure: invalid(response, "content-type") };
  }
  if (response.bodyText.trim().length === 0) {
    return { ok: false, failure: invalid(response, "empty-body") };
  }
  try {
    return { ok: true, value: JSON.parse(response.bodyText) as unknown };
  } catch {
    return { ok: false, failure: invalid(response, "malformed-json") };
  }
}

export function createSpeciesCatalogClient(
  transport: SpeciesCatalogTransport = createSpeciesCatalogFetchTransport(),
): SpeciesCatalogClient {
  return {
    async load({ signal }): Promise<SpeciesCatalogCallResult> {
      if (signal.aborted) {
        return { kind: "aborted" };
      }
      let response: SpeciesCatalogHttpResponse;
      try {
        response = await transport.getJson(CATALOG_URL, signal);
      } catch {
        return signal.aborted
          ? { kind: "aborted" }
          : { kind: "network-error", message: NETWORK_MESSAGE };
      }
      if (response.redirected) {
        return invalid(response, "http-status");
      }
      if (response.ok && response.status !== 200) {
        return invalid(response, "http-status-contract-conflict");
      }
      const parsed = parseBody(response);
      if (!parsed.ok) {
        return parsed.failure;
      }
      const decoded = decodeSpeciesCatalogResponse(parsed.value);
      if (!decoded.ok) {
        return invalid(
          response,
          response.ok ? "response-shape" : "http-status",
        );
      }
      if (decoded.value.status === "success") {
        return response.ok && response.status === 200
          ? { kind: "success", response: decoded.value }
          : invalid(response, "http-status-contract-conflict");
      }
      return !response.ok &&
        ((decoded.value.status === "not_found" && response.status === 404) ||
          (decoded.value.status === "invalid" && response.status === 422))
        ? {
            kind: "backend-invalid",
            response: decoded.value,
            httpStatus: response.status,
          }
        : invalid(response, "http-status-contract-conflict");
    },
  };
}
