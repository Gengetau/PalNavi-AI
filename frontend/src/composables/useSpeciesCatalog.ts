import { shallowRef, type Ref } from "vue";

import type {
  SpeciesCatalogClient,
  SpeciesCatalogSuccessResponse,
} from "../api/breedingCatalogContract";
import type { HttpInvalidReason } from "../api/contract";

export type SpeciesCatalogViewState =
  | { kind: "idle" }
  | { kind: "loading"; requestId: number }
  | {
      kind: "success";
      requestId: number;
      response: SpeciesCatalogSuccessResponse;
    }
  | {
      kind: "backend-invalid";
      requestId: number;
      message: string;
      httpStatus: number;
    }
  | {
      kind: "http-invalid";
      requestId: number;
      reason: HttpInvalidReason;
      message: string;
      httpStatus: number;
    }
  | {
      kind: "network-error";
      requestId: number;
      message: string;
    };

export interface SpeciesCatalogController {
  state: Readonly<Ref<SpeciesCatalogViewState>>;
  load(): Promise<void>;
  dispose(): void;
}

export function useSpeciesCatalog(
  client: SpeciesCatalogClient,
): SpeciesCatalogController {
  const state = shallowRef<SpeciesCatalogViewState>({ kind: "idle" });
  let latestRequestId = 0;
  let active: { requestId: number; controller: AbortController } | null = null;

  async function load(): Promise<void> {
    const requestId = ++latestRequestId;
    active?.controller.abort();
    const controller = new AbortController();
    active = { requestId, controller };
    state.value = { kind: "loading", requestId };
    try {
      const result = await client.load({ signal: controller.signal });
      if (requestId !== latestRequestId) {
        return;
      }
      if (result.kind === "aborted") {
        if (!controller.signal.aborted) {
          state.value = {
            kind: "network-error",
            requestId,
            message: "The species catalog request ended unexpectedly.",
          };
        }
        return;
      }
      if (result.kind === "success") {
        state.value = { kind: "success", requestId, response: result.response };
      } else if (result.kind === "backend-invalid") {
        state.value = {
          kind: "backend-invalid",
          requestId,
          message: result.response.message,
          httpStatus: result.httpStatus,
        };
      } else {
        state.value = { ...result, requestId };
      }
    } catch {
      if (requestId === latestRequestId && !controller.signal.aborted) {
        state.value = {
          kind: "network-error",
          requestId,
          message: "The species catalog could not be reached.",
        };
      }
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

  return { state, load, dispose };
}
