import { describe, expect, it, vi } from "vitest";

import type {
  BreedingCallResult,
  BreedingClient,
} from "../src/api/breedingContract";
import { useBreedingRequest } from "../src/composables/useBreedingRequest";
import {
  breedingGenderRequired,
  breedingRequest,
  breedingSuccess,
  breedingUnreachable,
} from "./breeding-fixtures";

interface Deferred<T> {
  promise: Promise<T>;
  resolve(value: T): void;
  reject(error: unknown): void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((fulfill, fail) => {
    resolve = fulfill;
    reject = fail;
  });
  return { promise, resolve, reject };
}

describe("breeding request state machine", () => {
  it.each([
    {
      result: {
        kind: "success",
        response: breedingSuccess(),
      } satisfies BreedingCallResult,
      expected: "success",
    },
    {
      result: {
        kind: "gender-required",
        response: breedingGenderRequired(),
      } satisfies BreedingCallResult,
      expected: "gender-required",
    },
    {
      result: {
        kind: "unreachable",
        response: breedingUnreachable(),
      } satisfies BreedingCallResult,
      expected: "unreachable",
    },
    {
      result: {
        kind: "network-error",
        message: "Offline.",
      } satisfies BreedingCallResult,
      expected: "network-error",
    },
  ])("maps $expected terminal state", async ({ result, expected }) => {
    const client: BreedingClient = {
      plan: vi.fn(async () => result),
    };
    const machine = useBreedingRequest(client);
    await machine.run(breedingRequest());
    expect(machine.state.value.kind).toBe(expected);
  });

  it("takes an immutable deep request snapshot", async () => {
    const pending = deferred<BreedingCallResult>();
    const client: BreedingClient = { plan: vi.fn(() => pending.promise) };
    const machine = useBreedingRequest(client);
    const request = breedingRequest();
    const run = machine.run(request);
    request.target.species_id = "mutated";
    request.inventory[0]!.species_id = "mutated";

    expect(machine.state.value.kind).toBe("loading");
    if (machine.state.value.kind === "loading") {
      expect(machine.state.value.request.target.species_id).toBe(
        "wixen_noct",
      );
      expect(machine.state.value.request.inventory[0]?.species_id).toBe(
        "dumud",
      );
    }
    pending.resolve({ kind: "success", response: breedingSuccess() });
    await run;
  });

  it("aborts the older request and ignores its late completion", async () => {
    const first = deferred<BreedingCallResult>();
    const second = deferred<BreedingCallResult>();
    const signals: AbortSignal[] = [];
    const client: BreedingClient = {
      plan: vi
        .fn<BreedingClient["plan"]>()
        .mockImplementationOnce((_request, { signal }) => {
          signals.push(signal);
          return first.promise;
        })
        .mockImplementationOnce(() => second.promise),
    };
    const machine = useBreedingRequest(client);
    const firstRun = machine.run(breedingRequest());
    const secondRun = machine.run(
      breedingRequest({
        target: { species_id: "dumud", gender: "male" },
      }),
    );
    expect(signals[0]?.aborted).toBe(true);

    const newest = breedingUnreachable();
    newest.target.species_id = "dumud";
    newest.target.gender = "male";
    second.resolve({ kind: "unreachable", response: newest });
    await secondRun;
    const newestState = machine.state.value;

    first.resolve({ kind: "success", response: breedingSuccess() });
    await firstRun;
    expect(machine.state.value).toBe(newestState);
  });

  it("retries the last immutable request snapshot", async () => {
    const plan = vi
      .fn<BreedingClient["plan"]>()
      .mockResolvedValueOnce({
        kind: "network-error",
        message: "Offline.",
      })
      .mockResolvedValueOnce({
        kind: "gender-required",
        response: breedingGenderRequired(),
      });
    const machine = useBreedingRequest({ plan });
    const request = breedingRequest();
    await machine.run(request);
    request.inventory[0]!.instance_id = "mutated";
    await machine.retry();

    expect(plan).toHaveBeenCalledTimes(2);
    expect(plan.mock.calls[1]?.[0]).toEqual(plan.mock.calls[0]?.[0]);
    expect(plan.mock.calls[1]?.[0].inventory[0]?.instance_id).toBe(
      "dumud-1",
    );
  });

  it("dispose aborts and invalidates active work", async () => {
    const pending = deferred<BreedingCallResult>();
    let signal: AbortSignal | undefined;
    const client: BreedingClient = {
      plan: vi.fn((_request, options) => {
        signal = options.signal;
        return pending.promise;
      }),
    };
    const machine = useBreedingRequest(client);
    const run = machine.run(breedingRequest());
    machine.dispose();
    expect(signal?.aborted).toBe(true);
    pending.resolve({ kind: "success", response: breedingSuccess() });
    await run;
    expect(machine.state.value.kind).toBe("loading");
  });

  it("maps a current rejection to a generic network state", async () => {
    const machine = useBreedingRequest({
      plan: vi.fn(async () => {
        throw new Error("PRIVATE_CLIENT_FAILURE");
      }),
    });
    await machine.run(breedingRequest());
    expect(machine.state.value).toMatchObject({
      kind: "network-error",
    });
    expect(
      machine.state.value.kind === "network-error"
        ? machine.state.value.message
        : "",
    ).not.toContain("PRIVATE");
  });
});
