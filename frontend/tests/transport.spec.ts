import { describe, expect, it, vi } from "vitest";

import { createFetchTransport } from "../src/api/transport";
import { syntheticRequest } from "./fixtures";

describe("fetch transport", () => {
  it("posts exact JSON with the supplied abort signal and safe fetch settings", async () => {
    const fetchImplementation = vi.fn(async () => {
      return new Response('{"status":"success","results":[]}', {
        status: 200,
        statusText: "OK",
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    });
    const transport = createFetchTransport(fetchImplementation);
    const controller = new AbortController();
    const request = syntheticRequest();

    const response = await transport.postJson(
      "/api/v1/knowledge/search",
      request,
      controller.signal,
    );

    expect(fetchImplementation).toHaveBeenCalledTimes(1);
    expect(fetchImplementation).toHaveBeenCalledWith(
      "/api/v1/knowledge/search",
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        signal: controller.signal,
        credentials: "same-origin",
        mode: "same-origin",
        redirect: "error",
        cache: "no-store",
      },
    );
    expect(response).toEqual({
      ok: true,
      status: 200,
      statusText: "OK",
      contentType: "application/json; charset=utf-8",
      bodyText: '{"status":"success","results":[]}',
      bodyTooLarge: false,
    });
  });

  it("rejects a declared oversized response without buffering it", async () => {
    const fetchImplementation = vi.fn(async () => {
      return new Response("ignored", {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Content-Length": "1048577",
        },
      });
    });
    const transport = createFetchTransport(fetchImplementation);
    const response = await transport.postJson(
      "/api/v1/knowledge/search",
      syntheticRequest(),
      new AbortController().signal,
    );
    expect(response.bodyTooLarge).toBe(true);
    expect(response.bodyText).toBe("");
  });

  it("stops an undeclared stream when it crosses the byte budget", async () => {
    const oversizedStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array(600_000));
        controller.enqueue(new Uint8Array(600_000));
        controller.close();
      },
    });
    const transport = createFetchTransport(
      vi.fn(async () => {
        return new Response(oversizedStream, {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    const response = await transport.postJson(
      "/api/v1/knowledge/search",
      syntheticRequest(),
      new AbortController().signal,
    );
    expect(response.bodyTooLarge).toBe(true);
    expect(response.bodyText).toBe("");
  });
});
