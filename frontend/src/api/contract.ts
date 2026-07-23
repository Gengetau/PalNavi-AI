export type Operation = "search" | "explain";

export interface KnowledgeRequest {
  query: string;
  language?: string;
  exact_game_version?: string;
  synthetic_only: boolean;
  limit: number;
}

export interface GameVersionScope {
  kind: string;
  value: string | null;
}

export interface Citation {
  document_id: string;
  chunk_id: string;
  title: string;
  section_path: string[];
  source_id: string;
  source_locator: string;
  retrieved_at: string;
  license_or_usage_note: string;
}

export interface KnowledgeSearchItem {
  score: number;
  document_id: string;
  chunk_id: string;
  title: string;
  section_path: string[];
  text: string;
  language: string;
  classification: string;
  game_version_scope: GameVersionScope;
  citation: Citation;
}

export const SEARCH_ERROR_CATEGORIES = [
  "request_invalid",
  "repository_unavailable",
  "repository_invalid_state",
] as const;

export type SearchErrorCategory = (typeof SEARCH_ERROR_CATEGORIES)[number];

export type KnowledgeSearchResponse =
  | {
      status: "success";
      results: KnowledgeSearchItem[];
      error_category?: null;
      message?: null;
    }
  | {
      status: "error";
      results: [];
      error_category: SearchErrorCategory;
      message: string;
    };

export interface TokenUsage {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
}

export interface ExplainCitation {
  marker: string;
  citation: Citation;
}

export const EXPLAIN_ERROR_CATEGORIES = [
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
] as const;

export type ExplainErrorCategory = (typeof EXPLAIN_ERROR_CATEGORIES)[number];

export type KnowledgeExplainResponse =
  | {
      status: "success";
      answer: string;
      citations: ExplainCitation[];
      usage?: TokenUsage | null;
    }
  | {
      status: "unsupported";
      message: string;
    }
  | {
      status: "error";
      error_category: ExplainErrorCategory;
      message: string;
    };

export type HttpInvalidReason =
  | "empty-body"
  | "malformed-json"
  | "content-type"
  | "response-too-large"
  | "malformed-encoding"
  | "response-shape"
  | "http-status"
  | "http-status-contract-conflict";

export interface BackendFailure {
  kind: "backend-error";
  errorCategory: string | null;
  message: string;
  httpStatus: number;
}

export interface HttpInvalidFailure {
  kind: "http-invalid";
  reason: HttpInvalidReason;
  httpStatus: number;
  message: string;
}

export interface NetworkFailure {
  kind: "network-error";
  message: string;
}

export interface AbortedResult {
  kind: "aborted";
}

export type SearchCallResult =
  | {
      kind: "search-success";
      results: KnowledgeSearchItem[];
      message: string | null;
    }
  | BackendFailure
  | HttpInvalidFailure
  | NetworkFailure
  | AbortedResult;

export type ExplainCallResult =
  | {
      kind: "explain-success";
      answer: string;
      citations: ExplainCitation[];
      usage: TokenUsage | null;
    }
  | {
      kind: "unsupported";
      message: string;
    }
  | BackendFailure
  | HttpInvalidFailure
  | NetworkFailure
  | AbortedResult;

export interface KnowledgeClient {
  search(
    request: Readonly<KnowledgeRequest>,
    options: { signal: AbortSignal },
  ): Promise<SearchCallResult>;
  explain(
    request: Readonly<KnowledgeRequest>,
    options: { signal: AbortSignal },
  ): Promise<ExplainCallResult>;
}
