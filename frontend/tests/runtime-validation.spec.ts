import { describe, expect, it } from "vitest";

import {
  decodeExplainResponse,
  decodeSearchResponse,
  summarizeFastApiDetail,
} from "../src/api/runtimeValidation";
import {
  syntheticCitation,
  syntheticExplainCitation,
  syntheticSearchItem,
} from "./fixtures";
import goldenContracts from "./golden/knowledge-contracts.json";

describe("search response decoder", () => {
  it("accepts backend-validated golden response fixtures", () => {
    expect(decodeSearchResponse(goldenContracts.search_success).ok).toBe(true);
    expect(decodeSearchResponse(goldenContracts.search_error).ok).toBe(true);
  });
  it("accepts and reconstructs a complete success response", () => {
    const decoded = decodeSearchResponse({
      status: "success",
      results: [syntheticSearchItem()],
      error_category: null,
      message: null,
      ignored: "<script>ignored</script>",
    });
    expect(decoded.ok).toBe(true);
    if (decoded.ok) {
      expect(decoded.value.results).toHaveLength(1);
      expect("ignored" in decoded.value).toBe(false);
    }
  });

  it("accepts empty results and a structured error", () => {
    expect(
      decodeSearchResponse({ status: "success", results: [] }).ok,
    ).toBe(true);
    const failure = decodeSearchResponse({
      status: "error",
      results: [],
      error_category: "repository_unavailable",
      message: "Knowledge retrieval is unavailable.",
    });
    expect(failure.ok).toBe(true);
    expect(
      decodeSearchResponse({ status: "error", results: [] }).ok,
    ).toBe(false);
  });

  it.each([
    {
      status: "success",
      results: [],
      error_category: "repository_unavailable",
      message: null,
    },
    {
      status: "success",
      results: [],
      error_category: null,
      message: "Contradictory error message.",
    },
    {
      status: "error",
      results: [],
      error_category: "repository_unavailable",
      message: "Controlled error.",
      answer: "Contradictory explanation.",
    },
  ])("rejects contradictory search outcome fields", (candidate) => {
    expect(decodeSearchResponse(candidate).ok).toBe(false);
  });

  it.each([
    { status: "success" },
    { status: "unknown", results: [] },
    { status: "success", results: [{ ...syntheticSearchItem(), score: NaN }] },
    {
      status: "success",
      results: [{ ...syntheticSearchItem(), section_path: ["ok", 1] }],
    },
    {
      status: "success",
      results: [{ ...syntheticSearchItem(), citation: { title: "partial" } }],
    },
    {
      status: "success",
      results: [
        {
          ...syntheticSearchItem(),
          document_id: "different-document",
        },
      ],
    },
  ])("rejects an invalid search shape", (candidate) => {
    expect(decodeSearchResponse(candidate).ok).toBe(false);
  });
});

describe("explanation response decoder", () => {
  it("accepts backend-validated golden response fixtures", () => {
    expect(decodeExplainResponse(goldenContracts.explain_success).ok).toBe(true);
    expect(
      decodeExplainResponse(goldenContracts.explain_unsupported).ok,
    ).toBe(true);
    expect(decodeExplainResponse(goldenContracts.explain_error).ok).toBe(true);
  });
  it("accepts success, null usage, and zero token counts", () => {
    const decoded = decodeExplainResponse({
      status: "success",
      answer: "A fictional answer. [K1]",
      citations: [syntheticExplainCitation()],
      usage: { input_tokens: 0, total_tokens: 0 },
      ignored: "discard",
    });
    expect(decoded.ok).toBe(true);
    if (decoded.ok && decoded.value.status === "success") {
      expect(decoded.value.usage?.input_tokens).toBe(0);
      expect("ignored" in decoded.value).toBe(false);
    }
    expect(
      decodeExplainResponse({
        status: "success",
        answer: "",
        citations: [syntheticExplainCitation()],
        usage: null,
      }).ok,
    ).toBe(false);
  });

  it("accepts explicit unsupported and every controlled error category", () => {
    expect(
      decodeExplainResponse({
        status: "unsupported",
        message: "No usable evidence.",
      }).ok,
    ).toBe(true);
    for (const category of [
      "request_invalid",
      "repository_unavailable",
      "repository_invalid_state",
      "configuration_invalid",
      "authentication_rejected",
      "rate_limited",
      "timeout",
      "provider_unavailable",
      "malformed_response",
      "unknown_provider",
      "invalid_grounded_output",
    ]) {
      expect(
        decodeExplainResponse({
          status: "error",
          error_category: category,
          message: "Controlled error.",
        }).ok,
      ).toBe(true);
    }
  });

  it.each([
    {
      status: "success",
      answer: "Synthetic answer. [K1]",
      citations: [syntheticExplainCitation()],
      error_category: "invalid_grounded_output",
    },
    {
      status: "unsupported",
      message: "No evidence.",
      citations: [syntheticExplainCitation()],
    },
    {
      status: "error",
      error_category: "provider_unavailable",
      message: "Controlled error.",
      answer: "Contradictory answer. [K1]",
    },
  ])("rejects contradictory explanation outcome fields", (candidate) => {
    expect(decodeExplainResponse(candidate).ok).toBe(false);
  });

  it.each(["K1", "[K0]", "[K01]", "[K-1]", "[X1]"])(
    "rejects malformed marker %s",
    (marker) => {
      expect(
        decodeExplainResponse({
          status: "success",
          answer: "Synthetic answer.",
          citations: [
            {
              marker,
              citation: syntheticCitation(),
            },
          ],
        }).ok,
      ).toBe(false);
    },
  );

  it("rejects duplicate markers and answers that do not map to citations", () => {
    const decoded = decodeExplainResponse({
      status: "success",
      answer: "Synthetic answer. [K2]",
      citations: [
        syntheticExplainCitation("[K2]"),
        syntheticExplainCitation("[K2]"),
      ],
    });
    expect(decoded.ok).toBe(false);
    expect(
      decodeExplainResponse({
        status: "success",
        answer: "Synthetic answer. [K2]",
        citations: [syntheticExplainCitation("[K1]")],
      }).ok,
    ).toBe(false);
  });

  it.each([
    "Supported claim. [K1] trailing [K999",
    "Supported claim. [K1] trailing [k2]",
    "Supported claim. [K1] trailing [K+2]",
    "Supported claim. [K1] trailing [K02]",
    "Supported claim. [K1] trailing [K2]",
  ])("rejects incomplete, malformed, or unknown marker text", (answer) => {
    expect(
      decodeExplainResponse({
        status: "success",
        answer,
        citations: [syntheticExplainCitation()],
      }).ok,
    ).toBe(false);
  });

  it.each([
    "Supported claim. [K1]\r\rUncited claim.",
    "Supported claim. [K1]\u2028Uncited claim.",
    "Supported claim. [K1]\u2029Uncited claim.",
  ])("rejects ungrounded paragraphs separated without LF", (answer) => {
    expect(
      decodeExplainResponse({
        status: "success",
        answer,
        citations: [syntheticExplainCitation()],
      }).ok,
    ).toBe(false);
  });

  it.each([
    {
      status: "error",
      error_category: "not-a-category",
      message: "bad",
    },
    {
      status: "success",
      answer: "bad",
      citations: [{ marker: "[K1]" }],
    },
    {
      status: "success",
      answer: "bad",
      citations: [],
      usage: { total_tokens: Number.POSITIVE_INFINITY },
    },
    {
      status: "success",
      answer: "Synthetic answer. [K1]",
      citations: [syntheticExplainCitation()],
      usage: { total_tokens: -1 },
    },
    {
      status: "success",
      answer: "Synthetic answer. [K1]",
      citations: [syntheticExplainCitation()],
      usage: { total_tokens: 1.5 },
    },
  ])("rejects an invalid explanation shape", (candidate) => {
    expect(decodeExplainResponse(candidate).ok).toBe(false);
  });
});

describe("FastAPI validation summary", () => {
  it("extracts bounded loc/message text and ignores input and context", () => {
    const summary = summarizeFastApiDetail({
      detail: [
        {
          loc: ["body", "query"],
          msg: "String should have at least 1 character",
          input: "PRIVATE_INPUT",
          ctx: { secret: "PRIVATE_CONTEXT" },
        },
        "Second safe message",
        { loc: ["body", "limit"], msg: "Must be at most 20" },
        "Fourth omitted message",
      ],
    });
    expect(summary).toContain("body.query");
    expect(summary).toContain("Second safe message");
    expect(summary).not.toContain("PRIVATE_INPUT");
    expect(summary).not.toContain("PRIVATE_CONTEXT");
    expect(summary).not.toContain("Fourth");
  });

  it("returns null for unrelated response bodies", () => {
    expect(summarizeFastApiDetail({ error: "<html>raw</html>" })).toBeNull();
  });
});
