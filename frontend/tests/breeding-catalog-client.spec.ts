import { describe, expect, it, vi } from "vitest";

import {
  createSpeciesCatalogClient,
  createSpeciesCatalogFetchTransport,
  type SpeciesCatalogHttpResponse,
  type SpeciesCatalogTransport,
} from "../src/api/breedingCatalogClient";
import type {
  SpeciesCatalogCallResult,
  SpeciesCatalogClient,
} from "../src/api/breedingCatalogContract";
import { BREEDING_DATASET_ID } from "../src/api/breedingContract";
import { useSpeciesCatalog } from "../src/composables/useSpeciesCatalog";
import { speciesCatalogSuccess } from "./breeding-fixtures";

function response(
  overrides: Partial<SpeciesCatalogHttpResponse> = {},
): SpeciesCatalogHttpResponse {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    contentType: "application/json; charset=utf-8",
    bodyText: JSON.stringify(speciesCatalogSuccess()),
    bodyTooLarge: false,
    bodyEncodingInvalid: false,
    redirected: false,
    ...overrides,
  };
}

function clientFromResponse(
  value: SpeciesCatalogHttpResponse,
): SpeciesCatalogClient {
  const transport: SpeciesCatalogTransport = {
    getJson: vi.fn(async () => value),
  };
  return createSpeciesCatalogClient(transport);
}

describe("species catalog client", () => {
  it("requests only the fixed same-origin dataset with bounded fetch options", async () => {
    const fetchImplementation = vi.fn(
      async () =>
        new Response(JSON.stringify(speciesCatalogSuccess()), {
          status: 200,
          headers: { "Content-Type": "application/json; charset=utf-8" },
        }),
    );
    const transport = createSpeciesCatalogFetchTransport(fetchImplementation);

    const result = await transport.getJson(
      `/api/v1/palworld/species-catalog?dataset_id=${BREEDING_DATASET_ID}`,
      new AbortController().signal,
    );

    expect(result.bodyTooLarge).toBe(false);
    expect(fetchImplementation).toHaveBeenCalledWith(
      `/api/v1/palworld/species-catalog?dataset_id=${BREEDING_DATASET_ID}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: expect.any(AbortSignal),
        credentials: "omit",
        mode: "same-origin",
        redirect: "error",
        cache: "no-store",
      },
    );
  });

  it("returns the strict complete catalog on HTTP 200", async () => {
    const result = await clientFromResponse(response()).load({
      signal: new AbortController().signal,
    });

    expect(result.kind).toBe("success");
    if (result.kind === "success") {
      expect(result.response.records).toHaveLength(299);
    }
  });

  it.each([
    ["oversized body", response({ bodyTooLarge: true }), "response-too-large"],
    [
      "invalid encoding",
      response({ bodyEncodingInvalid: true }),
      "malformed-encoding",
    ],
    ["wrong content type", response({ contentType: "text/html" }), "content-type"],
    ["malformed JSON", response({ bodyText: "{" }), "malformed-json"],
    ["redirected response", response({ redirected: true }), "http-status"],
    [
      "wrong shape",
      response({ bodyText: JSON.stringify({ status: "success" }) }),
      "response-shape",
    ],
  ])("rejects %s", async (_name, value, reason) => {
    const result = await clientFromResponse(value).load({
      signal: new AbortController().signal,
    });

    expect(result).toMatchObject({ kind: "http-invalid", reason });
  });

  it("rejects success payloads paired with a conflicting HTTP status", async () => {
    const result = await clientFromResponse(
      response({ ok: false, status: 422, statusText: "Unprocessable Content" }),
    ).load({ signal: new AbortController().signal });

    expect(result).toMatchObject({
      kind: "http-invalid",
      reason: "http-status-contract-conflict",
    });
  });

  it("classifies transport rejection and pre-aborted requests", async () => {
    const transport: SpeciesCatalogTransport = {
      getJson: vi.fn(async () => {
        throw new Error("offline");
      }),
    };
    const client = createSpeciesCatalogClient(transport);
    const controller = new AbortController();
    const network = await client.load({ signal: controller.signal });
    controller.abort();
    const aborted = await client.load({ signal: controller.signal });

    expect(network.kind).toBe("network-error");
    expect(aborted).toEqual({ kind: "aborted" });
  });
});

describe("species catalog request lifecycle", () => {
  it("prevents an older replaced request from overwriting the newer catalog", async () => {
    let resolveFirst!: (value: SpeciesCatalogCallResult) => void;
    let resolveSecond!: (value: SpeciesCatalogCallResult) => void;
    const first = new Promise<SpeciesCatalogCallResult>((resolve) => {
      resolveFirst = resolve;
    });
    const second = new Promise<SpeciesCatalogCallResult>((resolve) => {
      resolveSecond = resolve;
    });
    const signals: AbortSignal[] = [];
    const client: SpeciesCatalogClient = {
      load: vi
        .fn<SpeciesCatalogClient["load"]>()
        .mockImplementationOnce(({ signal }) => {
          signals.push(signal);
          return first;
        })
        .mockImplementationOnce(({ signal }) => {
          signals.push(signal);
          return second;
        }),
    };
    const controller = useSpeciesCatalog(client);

    const firstLoad = controller.load();
    const secondLoad = controller.load();
    expect(signals[0]?.aborted).toBe(true);
    resolveSecond({ kind: "success", response: speciesCatalogSuccess() });
    await secondLoad;
    expect(controller.state.value.kind).toBe("success");

    resolveFirst({
      kind: "network-error",
      message: "stale failure",
    });
    await firstLoad;
    expect(controller.state.value.kind).toBe("success");
  });

  it("aborts active catalog work on disposal", async () => {
    let signal: AbortSignal | undefined;
    const client: SpeciesCatalogClient = {
      load: vi.fn(
        ({ signal: activeSignal }) =>
          new Promise<SpeciesCatalogCallResult>(() => {
            signal = activeSignal;
          }),
      ),
    };
    const controller = useSpeciesCatalog(client);

    void controller.load();
    controller.dispose();

    expect(signal?.aborted).toBe(true);
  });
});
