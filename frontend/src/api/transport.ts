export interface HttpResponse {
  ok: boolean;
  status: number;
  statusText: string;
  contentType: string | null;
  bodyText: string;
  bodyTooLarge: boolean;
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
        credentials: "same-origin",
        mode: "same-origin",
        redirect: "error",
        cache: "no-store",
      });
      const responseBody = await readBoundedBody(response);
      return {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        contentType: response.headers.get("content-type"),
        bodyText: responseBody.text,
        bodyTooLarge: responseBody.tooLarge,
      };
    },
  };
}

export const MAX_RESPONSE_BYTES = 1_048_576;

async function readBoundedBody(
  response: Response,
): Promise<{ text: string; tooLarge: boolean }> {
  const declaredLength = response.headers.get("content-length");
  if (
    declaredLength !== null &&
    /^\d+$/.test(declaredLength) &&
    Number(declaredLength) > MAX_RESPONSE_BYTES
  ) {
    await response.body?.cancel();
    return { text: "", tooLarge: true };
  }
  if (response.body === null) {
    return { text: "", tooLarge: false };
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parts: string[] = [];
  let received = 0;
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) {
      parts.push(decoder.decode());
      return { text: parts.join(""), tooLarge: false };
    }
    received += chunk.value.byteLength;
    if (received > MAX_RESPONSE_BYTES) {
      await reader.cancel();
      return { text: "", tooLarge: true };
    }
    parts.push(decoder.decode(chunk.value, { stream: true }));
  }
}
