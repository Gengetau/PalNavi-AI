import { spawnSync } from "node:child_process";
import {
  lookupService,
  Resolver as PromiseResolver,
} from "node:dns/promises";
import { createSocket } from "node:dgram";
import { createServer, Socket } from "node:net";

import { describe, expect, it } from "vitest";

describe("offline guard conformance", () => {
  it("blocks ESM DNS promise APIs and resolvers", () => {
    expect(() => lookupService("127.0.0.1", 80)).toThrow(
      "Offline test guard blocked",
    );
    expect(() =>
      new PromiseResolver().resolve4("synthetic.example.invalid"),
    ).toThrow("Offline test guard blocked");
  });

  it("blocks ESM TCP and UDP bind paths", () => {
    expect(() => createServer()).toThrow("Offline test guard blocked");
    expect(() => new Socket().connect(80, "127.0.0.1")).toThrow(
      "Offline test guard blocked",
    );
    expect(() => createSocket("udp4")).toThrow("Offline test guard blocked");
  });

  it("blocks synchronous subprocess APIs through ESM bindings", () => {
    expect(() => spawnSync("synthetic-command")).toThrow(
      "Offline test guard blocked",
    );
  });
});
