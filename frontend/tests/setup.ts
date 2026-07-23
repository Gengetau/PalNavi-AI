import "./no-network.cjs";

import { afterEach, beforeEach, vi } from "vitest";

beforeEach(() => {
  const guardedGlobal = globalThis as typeof globalThis & {
    __PALNAVI_OFFLINE_GUARD__?: boolean;
  };
  if (guardedGlobal.__PALNAVI_OFFLINE_GUARD__ !== true) {
    throw new Error("Offline test guard did not initialize.");
  }
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new Error("Unexpected network access in an offline frontend test.");
    }),
  );
});

afterEach(() => {
  document.body.innerHTML = "";
});
