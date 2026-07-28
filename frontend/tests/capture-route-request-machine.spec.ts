import { describe, expect, it, vi } from "vitest";

import type {
  CaptureRouteCallResult,
  CaptureRouteClient,
} from "../src/api/captureRouteContract";
import { useCaptureRouteRequest } from "../src/composables/useCaptureRouteRequest";
import {
  captureRequest,
  captureSearchLimit,
  captureSuccess,
  captureUnreachable,
} from "./capture-route-fixtures";

interface Deferred<T> {
  promise: Promise<T>;
  resolve(value: T): void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((fulfill) => {
    resolve = fulfill;
  });
  return { promise, resolve };
}

describe("capture route request state machine", () => {
  it.each([
    {
      result: {
        kind: "success",
        response: captureSuccess(),
      } satisfies CaptureRouteCallResult,
      expected: "success",
    },
    {
      result: {
        kind: "unreachable",
        response: captureUnreachable(),
      } satisfies CaptureRouteCallResult,
      expected: "unreachable",
    },
    {
      result: {
        kind: "search-limit-exceeded",
        response: captureSearchLimit(),
      } satisfies CaptureRouteCallResult,
      expected: "search-limit-exceeded",
    },
  ])("maps $expected terminal state", async ({ result, expected }) => {
    const client: CaptureRouteClient = {
      plan: vi.fn(async () => result),
    };
    const machine = useCaptureRouteRequest(client);
    await machine.run(captureRequest());
    expect(machine.state.value.kind).toBe(expected);
  });

  it("takes an immutable snapshot including candidates", async () => {
    const pending = deferred<CaptureRouteCallResult>();
    const machine = useCaptureRouteRequest({
      plan: vi.fn(() => pending.promise),
    });
    const request = captureRequest();
    const run = machine.run(request);
    request.target.species_id = "mutated";
    request.inventory[0]!.species_id = "mutated";
    request.capture_candidates[0]!.species_id = "mutated";

    expect(machine.state.value.kind).toBe("loading");
    if (machine.state.value.kind === "loading") {
      expect(machine.state.value.request.target.species_id).toBe("anubis");
      expect(
        machine.state.value.request.capture_candidates[0]?.species_id,
      ).toBe("anubis");
    }
    pending.resolve({ kind: "success", response: captureSuccess() });
    await run;
  });

  it("aborts an older request and ignores late completion", async () => {
    const first = deferred<CaptureRouteCallResult>();
    const second = deferred<CaptureRouteCallResult>();
    const signals: AbortSignal[] = [];
    const client: CaptureRouteClient = {
      plan: vi
        .fn<CaptureRouteClient["plan"]>()
        .mockImplementationOnce((_request, { signal }) => {
          signals.push(signal);
          return first.promise;
        })
        .mockImplementationOnce(() => second.promise),
    };
    const machine = useCaptureRouteRequest(client);
    const firstRun = machine.run(captureRequest());
    const secondRun = machine.run(
      captureRequest({
        target: { species_id: "lamball", gender: "male" },
        capture_candidates: [],
      }),
    );
    expect(signals[0]?.aborted).toBe(true);

    const newest = captureUnreachable();
    newest.target.species_id = "lamball";
    newest.target.gender = "male";
    second.resolve({ kind: "unreachable", response: newest });
    await secondRun;
    const newestState = machine.state.value;
    first.resolve({ kind: "success", response: captureSuccess() });
    await firstRun;
    expect(machine.state.value).toBe(newestState);
  });

  it("retries the last immutable request and disposal aborts", async () => {
    const plan = vi
      .fn<CaptureRouteClient["plan"]>()
      .mockResolvedValueOnce({
        kind: "network-error",
        message: "Offline.",
      })
      .mockResolvedValueOnce({
        kind: "success",
        response: captureSuccess(),
      });
    const machine = useCaptureRouteRequest({ plan });
    const request = captureRequest();
    await machine.run(request);
    request.capture_candidates[0]!.candidate_id = "mutated";
    await machine.retry();
    expect(plan.mock.calls[1]?.[0]).toEqual(plan.mock.calls[0]?.[0]);
    expect(plan.mock.calls[1]?.[0].capture_candidates[0]?.candidate_id).toBe(
      "anubis-f",
    );

    const pending = deferred<CaptureRouteCallResult>();
    let signal: AbortSignal | undefined;
    const activeMachine = useCaptureRouteRequest({
      plan: vi.fn((_request, options) => {
        signal = options.signal;
        return pending.promise;
      }),
    });
    const run = activeMachine.run(captureRequest());
    activeMachine.dispose();
    expect(signal?.aborted).toBe(true);
    pending.resolve({ kind: "success", response: captureSuccess() });
    await run;
    expect(activeMachine.state.value.kind).toBe("loading");
  });
});
