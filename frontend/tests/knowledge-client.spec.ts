import { describe, expect, it, vi } from "vitest";

import { createKnowledgeClient } from "../src/api/knowledgeClient";
import type { HttpResponse, HttpTransport } from "../src/api/transport";
import {
  syntheticExplainCitation,
  syntheticRequest,
  syntheticSearchItem,
} from "./fixtures";

function transportReturning(response: HttpResponse): HttpTransport {
  return {
    postJson: vi.fn(async () => response),
  };
}

function jsonResponse(
  body: unknown,
  status = 200,
  ok = status >= 200 && status < 300,
): HttpResponse {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    contentType: "application/json",
    bodyText: JSON.stringify(body),
    bodyTooLarge: false,
  };
}

describe("knowledge client", () => {
  it("uses fixed relative endpoints and maps both success contracts", async () => {
    const searchTransport = transportReturning(
      jsonResponse({
        status: "success",
        results: [syntheticSearchItem()],
        message: null,
      }),
    );
    const searchClient = createKnowledgeClient(searchTransport);
    const controller = new AbortController();
    const request = syntheticRequest();
    await expect(
      searchClient.search(request, { signal: controller.signal }),
    ).resolves.toMatchObject({ kind: "search-success" });
    expect(searchTransport.postJson).toHaveBeenCalledWith(
      "/api/v1/knowledge/search",
      request,
      controller.signal,
    );

    const explainTransport = transportReturning(
      jsonResponse({
        status: "success",
        answer: "Fictional answer. [K1]",
        citations: [syntheticExplainCitation()],
        usage: null,
      }),
    );
    const explainClient = createKnowledgeClient(explainTransport);
    await expect(
      explainClient.explain(request, { signal: controller.signal }),
    ).resolves.toMatchObject({
      kind: "explain-success",
      answer: "Fictional answer. [K1]",
    });
    expect(explainTransport.postJson).toHaveBeenCalledWith(
      "/api/v1/knowledge/explain",
      request,
      controller.signal,
    );
  });

  it("maps unsupported and structured errors without throwing", async () => {
    const request = syntheticRequest();
    const signal = new AbortController().signal;
    const unsupported = createKnowledgeClient(
      transportReturning(
        jsonResponse({ status: "unsupported", message: "No evidence." }),
      ),
    );
    await expect(
      unsupported.explain(request, { signal }),
    ).resolves.toEqual({ kind: "unsupported", message: "No evidence." });

    const backend = createKnowledgeClient(
      transportReturning(
        jsonResponse(
          {
            status: "error",
            error_category: "timeout",
            message: "Provider timed out.",
          },
          504,
        ),
      ),
    );
    await expect(backend.explain(request, { signal })).resolves.toEqual({
      kind: "backend-error",
      errorCategory: "timeout",
      message: "Provider timed out.",
      httpStatus: 504,
    });
  });

  it("summarizes FastAPI validation without exposing submitted input", async () => {
    const client = createKnowledgeClient(
      transportReturning(
        jsonResponse(
          {
            detail: [
              {
                loc: ["body", "query"],
                msg: "Invalid query.",
                input: "DO_NOT_EXPOSE",
              },
            ],
          },
          422,
        ),
      ),
    );
    const result = await client.search(syntheticRequest(), {
      signal: new AbortController().signal,
    });
    expect(result).toMatchObject({
      kind: "http-invalid",
      reason: "http-status",
      httpStatus: 422,
    });
    expect("message" in result ? result.message : "").toContain("body.query");
    expect("message" in result ? result.message : "").not.toContain(
      "DO_NOT_EXPOSE",
    );
  });

  it.each([
    {
      response: {
        ok: false,
        status: 500,
        statusText: "Error",
        contentType: "text/html",
        bodyText: "<html>secret failure</html>",
        bodyTooLarge: false,
      },
      reason: "content-type",
    },
    {
      response: {
        ok: true,
        status: 204,
        statusText: "No Content",
        contentType: "application/json",
        bodyText: "",
        bodyTooLarge: false,
      },
      reason: "empty-body",
    },
    {
      response: jsonResponse({ status: "success", results: "wrong" }),
      reason: "response-shape",
    },
    {
      response: jsonResponse(
        { status: "success", results: [] },
        503,
        false,
      ),
      reason: "http-status-contract-conflict",
    },
  ])("maps unusable HTTP response to $reason", async ({ response, reason }) => {
    const client = createKnowledgeClient(transportReturning(response));
    const result = await client.search(syntheticRequest(), {
      signal: new AbortController().signal,
    });
    expect(result).toMatchObject({ kind: "http-invalid", reason });
    expect("message" in result ? result.message : "").not.toContain("secret");
  });

  it("rejects missing JSON media type and an oversized response", async () => {
    const signal = new AbortController().signal;
    const wrongType = createKnowledgeClient(
      transportReturning({
        ok: true,
        status: 200,
        statusText: "OK",
        contentType: "text/plain",
        bodyText: JSON.stringify({ status: "success", results: [] }),
        bodyTooLarge: false,
      }),
    );
    await expect(
      wrongType.search(syntheticRequest(), { signal }),
    ).resolves.toMatchObject({ kind: "http-invalid", reason: "content-type" });
    for (const separator of ["\n", "\r", "\u2028", "\u2029"]) {
      const separatedType = createKnowledgeClient(
        transportReturning({
          ok: true,
          status: 200,
          statusText: "OK",
          contentType: `application/json; charset=utf-8${separator}`,
          bodyText: JSON.stringify({ status: "success", results: [] }),
          bodyTooLarge: false,
        }),
      );
      await expect(
        separatedType.search(syntheticRequest(), { signal }),
      ).resolves.toMatchObject({
        kind: "http-invalid",
        reason: "content-type",
      });
    }

    const oversized = createKnowledgeClient(
      transportReturning({
        ok: true,
        status: 200,
        statusText: "OK",
        contentType: "application/json",
        bodyText: "",
        bodyTooLarge: true,
      }),
    );
    await expect(
      oversized.search(syntheticRequest(), { signal }),
    ).resolves.toMatchObject({
      kind: "http-invalid",
      reason: "response-too-large",
    });
  });

  it("rejects a result count above the submitted request limit", async () => {
    const client = createKnowledgeClient(
      transportReturning(
        jsonResponse({
          status: "success",
          results: [syntheticSearchItem(), syntheticSearchItem()],
          error_category: null,
          message: null,
        }),
      ),
    );
    await expect(
      client.search(syntheticRequest({ limit: 1 }), {
        signal: new AbortController().signal,
      }),
    ).resolves.toMatchObject({
      kind: "http-invalid",
      reason: "response-shape",
    });
  });

  it("maps transport failures to a generic network error without retrying", async () => {
    const transport: HttpTransport = {
      postJson: vi.fn(async () => {
        throw new Error("PRIVATE_NETWORK_DETAIL");
      }),
    };
    const client = createKnowledgeClient(transport);
    const result = await client.search(syntheticRequest(), {
      signal: new AbortController().signal,
    });
    expect(result).toMatchObject({ kind: "network-error" });
    expect("message" in result ? result.message : "").not.toContain("PRIVATE");
    expect(transport.postJson).toHaveBeenCalledTimes(1);
  });

  it("does not call transport for an already aborted request", async () => {
    const transport = transportReturning(
      jsonResponse({ status: "success", results: [] }),
    );
    const client = createKnowledgeClient(transport);
    const controller = new AbortController();
    controller.abort();
    await expect(
      client.search(syntheticRequest(), { signal: controller.signal }),
    ).resolves.toEqual({ kind: "aborted" });
    expect(transport.postJson).not.toHaveBeenCalled();
  });

  it("maps abort rejection to cancellation", async () => {
    const transport: HttpTransport = {
      postJson: vi.fn(async (_url, _body, signal) => {
        const error = new DOMException("Aborted", "AbortError");
        if (!signal.aborted) {
          throw error;
        }
        throw error;
      }),
    };
    const client = createKnowledgeClient(transport);
    await expect(
      client.search(syntheticRequest(), {
        signal: new AbortController().signal,
      }),
    ).resolves.toEqual({ kind: "aborted" });
  });
});
