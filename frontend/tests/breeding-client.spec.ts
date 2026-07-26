import { describe, expect, it, vi } from "vitest";

import { createBreedingClient } from "../src/api/breedingClient";
import type { HttpResponse, HttpTransport } from "../src/api/transport";
import {
  breedingGenderRequired,
  breedingInvalid,
  breedingRequest,
  breedingSuccess,
  breedingUnreachable,
} from "./breeding-fixtures";

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

describe("breeding client", () => {
  it("uses the fixed route endpoint and maps accepted success", async () => {
    const transport = transportReturning(jsonResponse(breedingSuccess()));
    const client = createBreedingClient(transport);
    const request = breedingRequest();
    const controller = new AbortController();

    await expect(
      client.plan(request, { signal: controller.signal }),
    ).resolves.toMatchObject({ kind: "success" });
    expect(transport.postJson).toHaveBeenCalledWith(
      "/api/v1/breeding/gender-aware-routes",
      request,
      controller.signal,
    );
  });

  it.each([
    {
      body: breedingGenderRequired(),
      expected: "gender-required",
    },
    { body: breedingUnreachable(), expected: "unreachable" },
  ])("maps $expected as a distinct product outcome", async ({
    body,
    expected,
  }) => {
    const client = createBreedingClient(
      transportReturning(jsonResponse(body)),
    );
    const request =
      expected === "gender-required"
        ? breedingRequest({
            inventory: [
              {
                instance_id: "katress-unknown",
                species_id: "katress",
                gender: "unknown",
              },
            ],
          })
        : breedingRequest();
    await expect(
      client.plan(request, {
        signal: new AbortController().signal,
      }),
    ).resolves.toMatchObject({ kind: expected });
  });

  it.each([404, 422])(
    "maps a strict product invalid response at HTTP %s",
    async (status) => {
      const client = createBreedingClient(
        transportReturning(
          jsonResponse(breedingInvalid(), status, false),
        ),
      );
      await expect(
        client.plan(breedingRequest(), {
          signal: new AbortController().signal,
        }),
      ).resolves.toMatchObject({
        kind: "backend-invalid",
        httpStatus: status,
      });
    },
  );

  it("keeps FastAPI validation distinct and does not expose submitted input", async () => {
    const client = createBreedingClient(
      transportReturning(
        jsonResponse(
          {
            detail: [
              {
                loc: ["body", "inventory", 0, "species_id"],
                msg: "Invalid species.",
                input: "DO_NOT_EXPOSE",
              },
            ],
          },
          422,
          false,
        ),
      ),
    );
    const result = await client.plan(breedingRequest(), {
      signal: new AbortController().signal,
    });
    expect(result).toMatchObject({
      kind: "http-invalid",
      reason: "http-status",
      httpStatus: 422,
    });
    expect("message" in result ? result.message : "").toContain(
      "body.inventory.0.species_id",
    );
    expect("message" in result ? result.message : "").not.toContain(
      "DO_NOT_EXPOSE",
    );
  });

  it.each([
    {
      response: {
        ok: true,
        status: 200,
        statusText: "OK",
        contentType: "text/plain",
        bodyText: "{}",
        bodyTooLarge: false,
        bodyEncodingInvalid: false,
      },
      reason: "content-type",
    },
    {
      response: {
        ok: true,
        status: 200,
        statusText: "OK",
        contentType: "application/json",
        bodyText: "{",
        bodyTooLarge: false,
        bodyEncodingInvalid: false,
      },
      reason: "malformed-json",
    },
    {
      response: {
        ok: true,
        status: 200,
        statusText: "OK",
        contentType: "application/json",
        bodyText: "",
        bodyTooLarge: true,
        bodyEncodingInvalid: false,
      },
      reason: "response-too-large",
    },
    {
      response: {
        ok: true,
        status: 200,
        statusText: "OK",
        contentType: "application/json",
        bodyText: "",
        bodyTooLarge: false,
        bodyEncodingInvalid: true,
      },
      reason: "malformed-encoding",
    },
  ])("maps invalid transport response to $reason", async ({
    response,
    reason,
  }) => {
    const client = createBreedingClient(
      transportReturning(response),
    );
    await expect(
      client.plan(breedingRequest(), {
        signal: new AbortController().signal,
      }),
    ).resolves.toMatchObject({ kind: "http-invalid", reason });
  });

  it.each([
    [breedingSuccess(), 201, true],
    [breedingSuccess(), 422, false],
    [breedingInvalid(), 200, true],
    [breedingGenderRequired(), 404, false],
  ] as const)(
    "rejects body/status contract conflict at HTTP %s",
    async (body, status, ok) => {
      const client = createBreedingClient(
        transportReturning(jsonResponse(body, status, ok)),
      );
      await expect(
        client.plan(breedingRequest(), {
          signal: new AbortController().signal,
        }),
      ).resolves.toMatchObject({
        kind: "http-invalid",
        reason: "http-status-contract-conflict",
      });
    },
  );

  it("rejects a valid response for a different submitted target", async () => {
    const response = breedingSuccess();
    response.target.species_id = "dumud";
    response.steps[1]!.child.species_id = "dumud";
    const client = createBreedingClient(
      transportReturning(jsonResponse(response)),
    );
    await expect(
      client.plan(breedingRequest(), {
        signal: new AbortController().signal,
      }),
    ).resolves.toMatchObject({
      kind: "http-invalid",
      reason: "response-shape",
    });
  });

  it("maps network failure and pre-aborted requests without leaking errors", async () => {
    const transport: HttpTransport = {
      postJson: vi.fn(async () => {
        throw new Error("PRIVATE_NETWORK_FAILURE");
      }),
    };
    const client = createBreedingClient(transport);
    const signal = new AbortController().signal;
    const failure = await client.plan(breedingRequest(), { signal });
    expect(failure).toMatchObject({ kind: "network-error" });
    expect("message" in failure ? failure.message : "").not.toContain(
      "PRIVATE",
    );

    const aborted = new AbortController();
    aborted.abort();
    await expect(
      client.plan(breedingRequest(), { signal: aborted.signal }),
    ).resolves.toEqual({ kind: "aborted" });
    expect(transport.postJson).toHaveBeenCalledTimes(1);
  });
});
