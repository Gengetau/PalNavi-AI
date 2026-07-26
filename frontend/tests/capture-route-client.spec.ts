import { describe, expect, it, vi } from "vitest";

import { createCaptureRouteClient } from "../src/api/captureRouteClient";
import type { HttpResponse, HttpTransport } from "../src/api/transport";
import {
  captureGenderRequired,
  captureInvalid,
  captureRequest,
  captureSearchLimit,
  captureSuccess,
  captureUnreachable,
} from "./capture-route-fixtures";

function transportReturning(response: HttpResponse): HttpTransport {
  return { postJson: vi.fn(async () => response) };
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
    bodyEncodingInvalid: false,
  };
}

describe("capture route client", () => {
  it("uses only the dedicated endpoint and accepts exact success", async () => {
    const transport = transportReturning(jsonResponse(captureSuccess()));
    const client = createCaptureRouteClient(transport);
    const request = captureRequest();
    const signal = new AbortController().signal;

    await expect(client.plan(request, { signal })).resolves.toMatchObject({
      kind: "success",
    });
    expect(transport.postJson).toHaveBeenCalledWith(
      "/api/v1/breeding/capture-ranked-routes",
      request,
      signal,
    );
  });

  it.each([
    [captureGenderRequired(), "gender-required"],
    [captureUnreachable(), "unreachable"],
    [captureSearchLimit(), "search-limit-exceeded"],
  ] as const)("maps %s to %s", async (body, kind) => {
    const request =
      kind === "gender-required"
        ? captureRequest({
            inventory: [
              {
                instance_id: "lamball-unknown",
                species_id: "lamball",
                gender: "unknown",
              },
            ],
          })
        : captureRequest();
    const client = createCaptureRouteClient(
      transportReturning(jsonResponse(body)),
    );
    await expect(
      client.plan(request, { signal: new AbortController().signal }),
    ).resolves.toMatchObject({ kind });
  });

  it.each([404, 422])("accepts invalid only at HTTP %s", async (status) => {
    const client = createCaptureRouteClient(
      transportReturning(jsonResponse(captureInvalid(), status, false)),
    );
    await expect(
      client.plan(captureRequest(), {
        signal: new AbortController().signal,
      }),
    ).resolves.toMatchObject({ kind: "backend-invalid", httpStatus: status });
  });

  it.each([
    ["text/plain", "{}", false, false, "content-type"],
    ["application/json", "{", false, false, "malformed-json"],
    ["application/json", "", true, false, "response-too-large"],
    ["application/json", "", false, true, "malformed-encoding"],
  ] as const)(
    "rejects transport boundary as %s",
    async (contentType, bodyText, bodyTooLarge, encodingInvalid, reason) => {
      const client = createCaptureRouteClient(
        transportReturning({
          ok: true,
          status: 200,
          statusText: "OK",
          contentType,
          bodyText,
          bodyTooLarge,
          bodyEncodingInvalid: encodingInvalid,
        }),
      );
      await expect(
        client.plan(captureRequest(), {
          signal: new AbortController().signal,
        }),
      ).resolves.toMatchObject({ kind: "http-invalid", reason });
    },
  );

  it("rejects requirements not submitted byte-for-byte", async () => {
    const response = captureSuccess();
    response.capture_requirements[0]!.species_id = "lamball";
    const client = createCaptureRouteClient(
      transportReturning(jsonResponse(response)),
    );
    await expect(
      client.plan(captureRequest(), {
        signal: new AbortController().signal,
      }),
    ).resolves.toMatchObject({
      kind: "http-invalid",
      reason: "response-shape",
    });
  });

  it("maps network failure and pre-aborted calls without leaking errors", async () => {
    const client = createCaptureRouteClient({
      postJson: vi.fn(async () => {
        throw new Error("PRIVATE_FAILURE");
      }),
    });
    const result = await client.plan(captureRequest(), {
      signal: new AbortController().signal,
    });
    expect(result).toMatchObject({ kind: "network-error" });
    expect("message" in result ? result.message : "").not.toContain("PRIVATE");

    const controller = new AbortController();
    controller.abort();
    await expect(
      client.plan(captureRequest(), { signal: controller.signal }),
    ).resolves.toEqual({ kind: "aborted" });
  });
});
