import { shallowRef, type Ref } from "vue";

import type {
  BreedingClient,
  BreedingGenderRequiredResponse,
  BreedingInvalidResponse,
  BreedingRequest,
  BreedingSuccessResponse,
  BreedingUnreachableResponse,
} from "../api/breedingContract";
import type { HttpInvalidReason } from "../api/contract";

interface BreedingRequestContext {
  requestId: number;
  request: BreedingRequest;
}

export type BreedingViewState =
  | { kind: "idle" }
  | ({ kind: "loading" } & BreedingRequestContext)
  | ({
      kind: "success";
      response: BreedingSuccessResponse;
    } & BreedingRequestContext)
  | ({
      kind: "gender-required";
      response: BreedingGenderRequiredResponse;
    } & BreedingRequestContext)
  | ({
      kind: "unreachable";
      response: BreedingUnreachableResponse;
    } & BreedingRequestContext)
  | ({
      kind: "backend-invalid";
      response: BreedingInvalidResponse;
      httpStatus: number;
    } & BreedingRequestContext)
  | ({
      kind: "http-invalid";
      reason: HttpInvalidReason;
      message: string;
      httpStatus: number;
    } & BreedingRequestContext)
  | ({
      kind: "network-error";
      message: string;
    } & BreedingRequestContext);

export interface BreedingRequestController {
  state: Readonly<Ref<BreedingViewState>>;
  run(request: Readonly<BreedingRequest>): Promise<void>;
  retry(): Promise<void>;
  dispose(): void;
}

function snapshotRequest(request: Readonly<BreedingRequest>): BreedingRequest {
  return {
    dataset_id: request.dataset_id,
    target: { ...request.target },
    inventory: request.inventory.map((item) => ({ ...item })),
    objective: "minimum_generations",
  };
}

export function useBreedingRequest(
  client: BreedingClient,
): BreedingRequestController {
  const state = shallowRef<BreedingViewState>({ kind: "idle" });
  let lastSettledState: BreedingViewState = { kind: "idle" };
  let lastRequest: BreedingRequest | null = null;
  let latestRequestId = 0;
  let active: { requestId: number; controller: AbortController } | null = null;

  async function run(request: Readonly<BreedingRequest>): Promise<void> {
    const requestId = ++latestRequestId;
    active?.controller.abort();
    const controller = new AbortController();
    active = { requestId, controller };
    const requestSnapshot = snapshotRequest(request);
    lastRequest = snapshotRequest(requestSnapshot);
    const context: BreedingRequestContext = {
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
        const failure: BreedingViewState = {
          ...context,
          kind: "network-error",
          message: "The breeding service could not be reached.",
        };
        state.value = failure;
        lastSettledState = failure;
        return;
      }
      const nextState: BreedingViewState = { ...context, ...result };
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
      const failure: BreedingViewState = {
        ...context,
        kind: "network-error",
        message: "The breeding service could not be reached.",
      };
      state.value = failure;
      lastSettledState = failure;
    } finally {
      if (active?.requestId === requestId) {
        active = null;
      }
    }
  }

  async function retry(): Promise<void> {
    if (lastRequest !== null) {
      await run(lastRequest);
    }
  }

  function dispose(): void {
    ++latestRequestId;
    active?.controller.abort();
    active = null;
  }

  return { state, run, retry, dispose };
}
