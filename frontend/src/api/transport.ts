export interface HttpResponse {
  ok: boolean;
  status: number;
  statusText: string;
  contentType: string | null;
  bodyText: string;
  bodyTooLarge: boolean;
  bodyEncodingInvalid: boolean;
}

export interface HttpTransport {
  postJson(
    url: string,
    body: unknown,
    signal: AbortSignal,
  ): Promise<HttpResponse>;
}

export function createFetchTransport(
  fetchImplementation?: typeof fetch,
): HttpTransport {
  return {
    async postJson(url, body, signal) {
      const performFetch = fetchImplementation ?? globalThis.fetch;
      const response = await performFetch(url, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
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
        };
      }
      const responseBody = await readBoundedBody(response);
      return {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        contentType: response.headers.get("content-type"),
        bodyText: responseBody.text,
        bodyTooLarge: responseBody.tooLarge,
        bodyEncodingInvalid: responseBody.encodingInvalid,
      };
    },
  };
}

export const MAX_RESPONSE_BYTES = 1_048_576;

function cancelBodyWithoutWaiting(response: Response): void {
  try {
    void response.body?.cancel().catch(() => undefined);
  } catch {
    // Cancellation is best effort; status rejection must not wait on the body.
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

function cancelReaderWithoutWaiting(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): void {
  try {
    void reader.cancel().catch(() => undefined);
  } catch {
    // Invalid-response classification must not wait on untrusted cleanup.
  }
}
