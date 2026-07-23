import { describe, expect, it } from "vitest";

import { safeLanguageTag } from "../src/presentation/language";

describe("safe language presentation", () => {
  it("normalizes a validated underscore tag for the DOM", () => {
    expect(safeLanguageTag("zh_Hant")).toBe("zh-Hant");
  });

  it.each([
    "bad tag",
    "e",
    "en-A",
    "en-ABCDEFGHI",
    "x".repeat(36),
    "en\n",
    "en\r",
    "en\u2028",
    "en\u2029",
  ])(
    "does not expose invalid backend language value %s as a DOM attribute",
    (value) => {
      expect(safeLanguageTag(value)).toBeUndefined();
    },
  );
});
