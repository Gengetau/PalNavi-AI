import { shallowRef, type Ref } from "vue";

import type {
  ExplainCitation,
  HttpInvalidReason,
  KnowledgeClient,
  KnowledgeRequest,
  KnowledgeSearchItem,
  Operation,
  TokenUsage,
} from "../api/contract";

interface RequestContext {
  requestId: number;
  operation: Operation;
  request: KnowledgeRequest;
}

export type ViewState =
  | { kind: "idle" }
  | ({ kind: "loading" } & RequestContext)
  | ({
      kind: "search-success";
      results: KnowledgeSearchItem[];
      message: string | null;
    } & RequestContext)
  | ({
      kind: "explain-success";
      answer: string;
      citations: ExplainCitation[];
      usage: TokenUsage | null;
    } & RequestContext)
  | ({ kind: "unsupported"; message: string } & RequestContext)
  | ({
      kind: "backend-error";
      errorCategory: string | null;
      message: string;
      httpStatus: number;
    } & RequestContext)
  | ({
      kind: "http-invalid";
      reason: HttpInvalidReason;
      message: string;
      httpStatus: number;
    } & RequestContext)
  | ({ kind: "network-error"; message: string } & RequestContext);

export interface KnowledgeRequestController {
  state: Readonly<Ref<ViewState>>;
  run(operation: Operation, request: KnowledgeRequest): Promise<void>;
  dispose(): void;
}

export function useKnowledgeRequest(
  client: KnowledgeClient,
): KnowledgeRequestController {
  const state = shallowRef<ViewState>({ kind: "idle" });
  let lastSettledState: ViewState = { kind: "idle" };
  let latestRequestId = 0;
  let active: { requestId: number; controller: AbortController } | null = null;

  async function run(
    operation: Operation,
    request: KnowledgeRequest,
  ): Promise<void> {
    const requestId = ++latestRequestId;
    active?.controller.abort();
    const controller = new AbortController();
    active = { requestId, controller };
    const context: RequestContext = {
      requestId,
      operation,
      request: { ...request },
    };
    state.value = { kind: "loading", ...context };

    try {
      const result =
        operation === "search"
          ? await client.search(request, { signal: controller.signal })
          : await client.explain(request, { signal: controller.signal });
      if (
        requestId !== latestRequestId ||
        (controller.signal.aborted && result.kind !== "aborted")
      ) {
        return;
      }
      if (result.kind === "aborted") {
        if (controller.signal.aborted) {
          state.value = lastSettledState;
          return;
        }
        const nextState: ViewState = {
          ...context,
          kind: "network-error",
          message:
            "The knowledge service could not be reached. Check your connection and try again.",
        };
        state.value = nextState;
        lastSettledState = nextState;
        return;
      }
      let nextState: ViewState;
      switch (result.kind) {
        case "search-success":
          nextState = { ...context, ...result };
          break;
        case "explain-success":
          nextState = { ...context, ...result };
          break;
        case "unsupported":
          nextState = { ...context, ...result };
          break;
        case "backend-error":
          nextState = { ...context, ...result };
          break;
        case "http-invalid":
          nextState = { ...context, ...result };
          break;
        case "network-error":
          nextState = { ...context, ...result };
          break;
      }
      state.value = nextState;
      lastSettledState = nextState;
    } catch {
      if (requestId !== latestRequestId) {
        return;
      }
      if (controller.signal.aborted) {
        state.value = lastSettledState;
        return;
      }
      const nextState: ViewState = {
        ...context,
        kind: "network-error",
        message:
          "The knowledge service could not be reached. Check your connection and try again.",
      };
      state.value = nextState;
      lastSettledState = nextState;
    } finally {
      if (active?.requestId === requestId) {
        active = null;
      }
    }
  }

  function dispose(): void {
    ++latestRequestId;
    active?.controller.abort();
    active = null;
  }

  return {
    state,
    run,
    dispose,
  };
}
