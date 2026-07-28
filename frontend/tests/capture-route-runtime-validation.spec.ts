import { describe, expect, it } from "vitest";

import {
  captureResponseMatchesRequest,
  decodeCaptureRouteResponse,
} from "../src/api/captureRouteRuntimeValidation";
import {
  captureGenderRequired,
  captureRequest,
  captureSuccess,
} from "./capture-route-fixtures";

describe("capture route runtime validation", () => {
  it("accepts exact direct-target success and matches the request", () => {
    const response = captureSuccess();
    const decoded = decodeCaptureRouteResponse(response);
    expect(decoded).toEqual({ ok: true, value: response });
    expect(captureResponseMatchesRequest(response, captureRequest())).toBe(
      true,
    );
  });

  it.each([
    ["extra key", (value: Record<string, unknown>) => (value.extra = true)],
    [
      "unsupported boundary claim",
      (value: Record<string, unknown>) => {
        const boundary = value.acquisition_boundary as Record<string, unknown>;
        boundary.catchability_verified = true;
      },
    ],
    [
      "count mismatch",
      (value: Record<string, unknown>) => {
        const cost = value.cost as Record<string, unknown>;
        cost.new_capture_count = 0;
      },
    ],
    [
      "unknown response gender",
      (value: Record<string, unknown>) => {
        const target = value.target as Record<string, unknown>;
        target.gender = "unknown";
      },
    ],
    [
      "bad source hash",
      (value: Record<string, unknown>) => {
        value.steps = [
          {
            order: 1,
            generation: 1,
            parent_a: {
              species_id: "a",
              gender: "male",
              required_passive_ids: [],
              required_iv_constraints: [],
              generation_depth: 0,
            },
            parent_b: {
              species_id: "b",
              gender: "female",
              required_passive_ids: [],
              required_iv_constraints: [],
              generation_depth: 0,
            },
            child: {
              species_id: "anubis",
              gender: "female",
              required_passive_ids: [],
              required_iv_constraints: [],
              generation_depth: 1,
            },
            result_kind: "ordinary_power",
            source_record_hash: "bad",
          },
        ];
      },
    ],
  ])("rejects %s", (_label, mutate) => {
    const value = structuredClone(captureSuccess()) as unknown as Record<
      string,
      unknown
    >;
    mutate(value);
    expect(decodeCaptureRouteResponse(value)).toEqual({ ok: false });
  });

  it("requires reported unknown IDs to exist in the submitted inventory", () => {
    const response = captureGenderRequired();
    expect(
      captureResponseMatchesRequest(response, captureRequest()),
    ).toBe(false);
    expect(
      captureResponseMatchesRequest(
        response,
        captureRequest({
          inventory: [
            {
              instance_id: "lamball-unknown",
              species_id: "lamball",
              gender: "unknown",
            },
          ],
        }),
      ),
    ).toBe(true);
  });

  it("rejects a reported capture requirement when the same state is owned", () => {
    expect(
      captureResponseMatchesRequest(
        captureSuccess(),
        captureRequest({
          inventory: [
            {
              instance_id: "anubis-owned",
              species_id: "anubis",
              gender: "female",
            },
          ],
        }),
      ),
    ).toBe(false);
  });
});
