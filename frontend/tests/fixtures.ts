import type {
  Citation,
  ExplainCitation,
  KnowledgeRequest,
  KnowledgeSearchItem,
} from "../src/api/contract";

export const syntheticRequest = (
  overrides: Partial<KnowledgeRequest> = {},
): KnowledgeRequest => ({
  query: "fictional signal route",
  synthetic_only: true,
  limit: 5,
  ...overrides,
});

export const syntheticCitation = (
  overrides: Partial<Citation> = {},
): Citation => ({
  document_id: "synthetic-document-alpha",
  chunk_id: "synthetic-document-alpha-0001",
  title: "Synthetic Signal Notes",
  section_path: ["Invented observations"],
  source_id: "project-authored-fixture",
  source_locator: "project-authored://synthetic-fixture/signal-alpha",
  retrieved_at: "2026-07-23T12:00:00+00:00",
  license_or_usage_note: "Project-authored synthetic fixture.",
  ...overrides,
});

export const syntheticSearchItem = (
  overrides: Partial<KnowledgeSearchItem> = {},
): KnowledgeSearchItem => {
  const { citation: citationOverride, ...itemOverrides } = overrides;
  const item = {
    score: 0.875,
    document_id: "synthetic-document-alpha",
    chunk_id: "synthetic-document-alpha-0001",
    title: "Synthetic Signal Notes",
    section_path: ["Invented observations"],
    text: "A fictional signal appears beside an invented arch.",
    language: "en",
    classification: "synthetic" as const,
    game_version_scope: {
      kind: "exact" as const,
      value: "synthetic-0.0.0",
    },
    ...itemOverrides,
  };
  return {
    ...item,
    citation:
      citationOverride ??
      syntheticCitation({
        document_id: item.document_id,
        chunk_id: item.chunk_id,
        title: item.title,
        section_path: item.section_path,
      }),
  };
};

export const syntheticExplainCitation = (
  marker = "[K1]",
  citation = syntheticCitation(),
): ExplainCitation => ({ marker, citation });
