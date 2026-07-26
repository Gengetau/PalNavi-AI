import { shallowRef, type Ref } from "vue";

import type {
  CaptureGenderRequiredResponse,
  CaptureInvalidResponse,
  CaptureRouteClient,
  CaptureRouteRequest,
  CaptureSearchLimitResponse,
  CaptureSuccessResponse,
  CaptureUnreachableResponse,
} from "../api/captureRouteContract";
import type { HttpInvalidReason } from "../api/contract";

interface CaptureRequestContext {
  requestId: number;
  request: CaptureRouteRequest;
}

export type CaptureRouteViewState =
  | { kind: "idle" }
  | ({ kind: "loading" } & CaptureRequestContext)
  | ({
      kind: "success";
      response: CaptureSuccessResponse;
    } & CaptureRequestContext)
  | ({
      kind: "gender-required";
      response: CaptureGenderRequiredResponse;
    } & CaptureRequestContext)
  | ({
      kind: "unreachable";
      response: CaptureUnreachableResponse;
    } & CaptureRequestContext)
  | ({
      kind: "search-limit-exceeded";
      response: CaptureSearchLimitResponse;
    } & CaptureRequestContext)
  | ({
      kind: "backend-invalid";
      response: CaptureInvalidResponse;
      httpStatus: number;
    } & CaptureRequestContext)
  | ({
      kind: "http-invalid";
      reason: HttpInvalidReason;
      message: string;
      httpStatus: number;
    } & CaptureRequestContext)
  | ({
      kind: "network-error";
      message: string;
    } & CaptureRequestContext);

export interface CaptureRouteRequestController {
  state: Readonly<Ref<CaptureRouteViewState>>;
  run(request: Readonly<CaptureRouteRequest>): Promise<void>;
  retry(): Promise<void>;
  dispose(): void;
}

function snapshotRequest(
  request: Readonly<CaptureRouteRequest>,
): CaptureRouteRequest {
  return {
    dataset_id: request.dataset_id,
    target: { ...request.target },
    inventory: request.inventory.map((item) => ({ ...item })),
    capture_candidates: request.capture_candidates.map((item) => ({
      ...item,
    })),
    objective: "minimum_new_captures",
  };
}

export function useCaptureRouteRequest(
  client: CaptureRouteClient,
): CaptureRouteRequestController {
  const state = shallowRef<CaptureRouteViewState>({ kind: "idle" });
  let lastSettledState: CaptureRouteViewState = { kind: "idle" };
  let lastRequest: CaptureRouteRequest | null = null;
  let latestRequestId = 0;
  let active: { requestId: number; controller: AbortController } | null =
    null;

  async function run(request: Readonly<CaptureRouteRequest>): Promise<void> {
    const requestId = ++latestRequestId;
    active?.controller.abort();
    const controller = new AbortController();
    active = { requestId, controller };
    const requestSnapshot = snapshotRequest(request);
    lastRequest = snapshotRequest(requestSnapshot);
    const context: CaptureRequestContext = {
      requestId,
      request: requestSnapshot,
    };
    state.value = { kind: "loading", ...context };

    try {
      const result = await client.plan(requestSnapshot, {
        signal: controller.signal,
      });
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
        const failure: CaptureRouteViewState = {
          ...context,
          kind: "network-error",
          message: "The capture-ranked route service could not be reached.",
        };
        state.value = failure;
        lastSettledState = failure;
        return;
      }
      const nextState: CaptureRouteViewState = { ...context, ...result };
      state.value = nextState;
      lastSettledState = nextState;
    } catch {
      if (requestId !== latestRequestId) return;
      if (controller.signal.aborted) {
        state.value = lastSettledState;
        return;
      }
      const failure: CaptureRouteViewState = {
        ...context,
        kind: "network-error",
        message: "The capture-ranked route service could not be reached.",
      };
      state.value = failure;
      lastSettledState = failure;
    } finally {
      if (active?.requestId === requestId) active = null;
    }
  }

  async function retry(): Promise<void> {
    if (lastRequest !== null) await run(lastRequest);
  }

  function dispose(): void {
    ++latestRequestId;
    active?.controller.abort();
    active = null;
  }

  return { state, run, retry, dispose };
}
