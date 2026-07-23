import { describe, expect, it, vi } from "vitest";

import type {
  ExplainCallResult,
  KnowledgeClient,
  SearchCallResult,
} from "../src/api/contract";
import { useKnowledgeRequest } from "../src/composables/useKnowledgeRequest";
import {
  syntheticExplainCitation,
  syntheticRequest,
  syntheticSearchItem,
} from "./fixtures";

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

describe("knowledge request state machine", () => {
  it("starts idle and enters loading synchronously", async () => {
    const pending = deferred<SearchCallResult>();
    const client: KnowledgeClient = {
      search: vi.fn(() => pending.promise),
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({
          kind: "unsupported",
          message: "unused",
        }),
      ),
    };
    const machine = useKnowledgeRequest(client);
    expect(machine.state.value).toEqual({ kind: "idle" });

    const request = syntheticRequest();
    const run = machine.run("search", request);
    expect(machine.state.value).toMatchObject({
      kind: "loading",
      requestId: 1,
      operation: "search",
      request,
    });

    pending.resolve({
      kind: "search-success",
      results: [syntheticSearchItem()],
      message: null,
    });
    await run;
    expect(machine.state.value).toMatchObject({
      kind: "search-success",
      requestId: 1,
    });
  });

  it.each([
    {
      result: {
        kind: "explain-success",
        answer: "Synthetic answer. [K1]",
        citations: [syntheticExplainCitation()],
        usage: null,
      } satisfies ExplainCallResult,
      expected: "explain-success",
    },
    {
      result: { kind: "unsupported", message: "No evidence." } satisfies ExplainCallResult,
      expected: "unsupported",
    },
    {
      result: {
        kind: "backend-error",
        errorCategory: "timeout",
        message: "Timed out.",
        httpStatus: 504,
      } satisfies ExplainCallResult,
      expected: "backend-error",
    },
    {
      result: {
        kind: "http-invalid",
        reason: "response-shape",
        message: "Invalid.",
        httpStatus: 200,
      } satisfies ExplainCallResult,
      expected: "http-invalid",
    },
    {
      result: {
        kind: "network-error",
        message: "Offline.",
      } satisfies ExplainCallResult,
      expected: "network-error",
    },
  ])("maps $expected terminal result", async ({ result, expected }) => {
    const client: KnowledgeClient = {
      search: vi.fn(
        async (): Promise<SearchCallResult> => ({
          kind: "search-success",
          results: [],
          message: null,
        }),
      ),
      explain: vi.fn(async () => result),
    };
    const machine = useKnowledgeRequest(client);
    await machine.run("explain", syntheticRequest());
    expect(machine.state.value.kind).toBe(expected);
  });

  it("aborts and ignores a stale response even when the client ignores its signal", async () => {
    const first = deferred<SearchCallResult>();
    const second = deferred<ExplainCallResult>();
    const searchSignals: AbortSignal[] = [];
    const client: KnowledgeClient = {
      search: vi.fn((_request, { signal }) => {
        searchSignals.push(signal);
        return first.promise;
      }),
      explain: vi.fn(() => second.promise),
    };
    const machine = useKnowledgeRequest(client);

    const firstRun = machine.run(
      "search",
      syntheticRequest({ query: "first synthetic query" }),
    );
    const secondRun = machine.run(
      "explain",
      syntheticRequest({ query: "second synthetic query" }),
    );
    expect(searchSignals[0]?.aborted).toBe(true);
    expect(machine.state.value).toMatchObject({
      kind: "loading",
      requestId: 2,
      operation: "explain",
    });

    second.resolve({
      kind: "explain-success",
      answer: "Newest synthetic answer. [K1]",
      citations: [syntheticExplainCitation()],
      usage: null,
    });
    await secondRun;
    const newestState = machine.state.value;
    expect(newestState).toMatchObject({
      kind: "explain-success",
      answer: "Newest synthetic answer. [K1]",
      requestId: 2,
    });

    first.resolve({
      kind: "search-success",
      results: [syntheticSearchItem({ title: "Stale result" })],
      message: null,
    });
    await firstRun;
    expect(machine.state.value).toBe(newestState);
  });

  it("does not surface cancellation as a visible failure", async () => {
    const pending = deferred<SearchCallResult>();
    const client: KnowledgeClient = {
      search: vi.fn(() => pending.promise),
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({
          kind: "unsupported",
          message: "No evidence.",
        }),
      ),
    };
    const machine = useKnowledgeRequest(client);
    const oldRun = machine.run("search", syntheticRequest());
    await machine.run("explain", syntheticRequest({ query: "new query" }));
    pending.resolve({ kind: "aborted" });
    await oldRun;
    expect(machine.state.value.kind).toBe("unsupported");
  });

  it("ignores a stale rejection after the newest terminal state is visible", async () => {
    const stale = deferred<SearchCallResult>();
    const client: KnowledgeClient = {
      search: vi.fn(() => stale.promise),
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({
          kind: "unsupported",
          message: "Newest state.",
        }),
      ),
    };
    const machine = useKnowledgeRequest(client);
    const staleRun = machine.run("search", syntheticRequest());
    await machine.run("explain", syntheticRequest({ query: "new query" }));
    const newestState = machine.state.value;
    stale.reject(new Error("STALE_PRIVATE_FAILURE"));
    await staleRun;
    expect(machine.state.value).toBe(newestState);
  });

  it("maps an unsolicited current aborted result to a network failure", async () => {
    const client: KnowledgeClient = {
      search: vi.fn(
        async (): Promise<SearchCallResult> => ({ kind: "aborted" }),
      ),
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({
          kind: "unsupported",
          message: "unused",
        }),
      ),
    };
    const machine = useKnowledgeRequest(client);
    await machine.run("explain", syntheticRequest({ query: "settled query" }));
    expect(machine.state.value).toMatchObject({
      kind: "unsupported",
      message: "unused",
    });
    await machine.run("search", syntheticRequest());
    expect(machine.state.value).toMatchObject({
      kind: "network-error",
      requestId: 2,
    });
  });

  it("does not resurrect a pending predecessor when the current request cancels", async () => {
    const predecessor = deferred<SearchCallResult>();
    const client: KnowledgeClient = {
      search: vi
        .fn<KnowledgeClient["search"]>()
        .mockResolvedValueOnce({
          kind: "search-success",
          results: [syntheticSearchItem({ title: "Settled result" })],
          message: "Settled state.",
        })
        .mockImplementationOnce(() => predecessor.promise),
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({ kind: "aborted" }),
      ),
    };
    const machine = useKnowledgeRequest(client);
    await machine.run("search", syntheticRequest({ query: "settled query" }));
    const settledState = machine.state.value;
    expect(settledState).toMatchObject({
      kind: "search-success",
      message: "Settled state.",
    });

    const oldRun = machine.run(
      "search",
      syntheticRequest({ query: "pending predecessor" }),
    );
    await machine.run("explain", syntheticRequest({ query: "new query" }));
    expect(machine.state.value).toMatchObject({
      kind: "network-error",
      requestId: 3,
    });
    const cancellationFailure = machine.state.value;

    predecessor.resolve({
      kind: "search-success",
      results: [syntheticSearchItem({ title: "Stale result" })],
      message: null,
    });
    await oldRun;
    expect(machine.state.value).toBe(cancellationFailure);
  });

  it("maps an unexpected current client rejection to a generic network failure", async () => {
    const client: KnowledgeClient = {
      search: vi.fn(async () => {
        throw new Error("PRIVATE_CLIENT_EXCEPTION");
      }),
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({
          kind: "unsupported",
          message: "unused",
        }),
      ),
    };
    const machine = useKnowledgeRequest(client);
    await machine.run("search", syntheticRequest());
    expect(machine.state.value).toMatchObject({ kind: "network-error" });
    expect(
      machine.state.value.kind === "network-error"
        ? machine.state.value.message
        : "",
    ).not.toContain("PRIVATE");
  });

  it("dispose aborts and invalidates the active request", async () => {
    const pending = deferred<SearchCallResult>();
    let signal: AbortSignal | undefined;
    const client: KnowledgeClient = {
      search: vi.fn((_request, options) => {
        signal = options.signal;
        return pending.promise;
      }),
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({
          kind: "unsupported",
          message: "unused",
        }),
      ),
    };
    const machine = useKnowledgeRequest(client);
    const run = machine.run("search", syntheticRequest());
    machine.dispose();
    expect(signal?.aborted).toBe(true);
    pending.resolve({
      kind: "search-success",
      results: [],
      message: null,
    });
    await run;
    expect(machine.state.value.kind).toBe("loading");
  });
});
