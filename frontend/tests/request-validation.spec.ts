import { describe, expect, it } from "vitest";

import {
  INITIAL_FORM,
  type KnowledgeFormModel,
  validateAndBuildRequest,
} from "../src/form/knowledgeRequest";
import goldenContracts from "./golden/knowledge-contracts.json";

const valid = (
  overrides: Partial<KnowledgeFormModel> = {},
): KnowledgeFormModel => ({
  ...INITIAL_FORM,
  query: "fictional signal",
  ...overrides,
});

describe("knowledge request validation", () => {
  it("uses visible synthetic-only and bounded defaults", () => {
    expect(INITIAL_FORM.syntheticOnly).toBe(true);
    expect(INITIAL_FORM.limit).toBe("5");
  });

  it("trims surrounding whitespace and preserves internal whitespace", () => {
    const result = validateAndBuildRequest(
      valid({ query: "  fictional   signal  " }),
    );
    expect(result).toEqual({
      ok: true,
      request: {
        query: "fictional   signal",
        synthetic_only: true,
        limit: 5,
      },
    });
  });

  it("omits blank optional filters rather than sending undefined", () => {
    const result = validateAndBuildRequest(
      valid({ language: "  ", exactGameVersion: "\n" }),
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(Object.keys(result.request)).toEqual([
        "query",
        "synthetic_only",
        "limit",
      ]);
    }
  });

  it.each(["en", "eng", "pt-BR", "zh_Hant", "es-419"])(
    "accepts backend-compatible language tag %s",
    (language) => {
      const result = validateAndBuildRequest(valid({ language }));
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.request.language).toBe(language);
      }
    },
  );

  it.each(["e", "engl", "en-", "en-A", "en-ABCDEFGHI", "en US"])(
    "rejects incompatible language tag %s",
    (language) => {
      const result = validateAndBuildRequest(valid({ language }));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.errors.language).toBeDefined();
      }
    },
  );

  it.each(["en\n", "en\r", "en\u2028", "en\u2029"])(
    "rejects a raw language tag containing a line separator",
    (language) => {
      const result = validateAndBuildRequest(valid({ language }));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.errors.language).toBeDefined();
      }
    },
  );

  it("counts astral Unicode characters as one code point", () => {
    expect(validateAndBuildRequest(valid({ query: "🧭".repeat(500) })).ok).toBe(
      true,
    );
    const tooLong = validateAndBuildRequest(
      valid({ query: "🧭".repeat(501) }),
    );
    expect(tooLong.ok).toBe(false);
  });

  it.each(["", "0", "21", "1.5", "-1", "five"])(
    "rejects invalid bounded limit %s",
    (limit) => {
      const result = validateAndBuildRequest(valid({ limit }));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.errors.limit).toBeDefined();
      }
    },
  );

  it("includes synthetic false and complete optional filters", () => {
    const result = validateAndBuildRequest(
      valid({
        language: "en-US",
        exactGameVersion: "synthetic-0.0.0",
        syntheticOnly: false,
        limit: "20",
      }),
    );
    expect(result).toEqual({
      ok: true,
      request: {
        query: "fictional signal",
        language: "en-US",
        exact_game_version: "synthetic-0.0.0",
        synthetic_only: false,
        limit: 20,
      },
    });
  });

  it("normalizes and serializes the exact backend-owned golden request", () => {
    const result = validateAndBuildRequest(
      valid({
        query: "fictional signal route",
        language: "en-US",
        exactGameVersion: "synthetic-0.0.0",
        syntheticOnly: true,
        limit: "3",
      }),
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.request).toEqual(goldenContracts.request);
      expect(JSON.parse(JSON.stringify(result.request))).toEqual(
        goldenContracts.request,
      );
    }
  });

  it("reports every invalid field together", () => {
    const result = validateAndBuildRequest(
      valid({
        query: " ",
        language: "bad tag",
        exactGameVersion: "v".repeat(65),
        limit: "0",
      }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(Object.keys(result.errors).sort()).toEqual([
        "exactGameVersion",
        "language",
        "limit",
        "query",
      ]);
    }
  });
});
