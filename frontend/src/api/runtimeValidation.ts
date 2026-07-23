import {
  EXPLAIN_ERROR_CATEGORIES,
  SEARCH_ERROR_CATEGORIES,
  type Citation,
  type ExplainCitation,
  type KnowledgeExplainResponse,
  type KnowledgeSearchItem,
  type KnowledgeSearchResponse,
  type TokenUsage,
} from "./contract";

export type DecodeResult<T> =
  | { ok: true; value: T }
  | { ok: false; issue: string };

type UnknownRecord = Record<string, unknown>;

const own = (value: UnknownRecord, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key);
const ownsAny = (value: UnknownRecord, keys: readonly string[]): boolean =>
  keys.some((key) => own(value, key));

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const fail = <T>(issue: string): DecodeResult<T> => ({ ok: false, issue });
const pass = <T>(value: T): DecodeResult<T> => ({ ok: true, value });
const nonBlank = (value: string): boolean => value.trim().length > 0;
const bounded = (value: string, max: number): boolean =>
  nonBlank(value) && value.length <= max;

function stringValue(record: UnknownRecord, key: string): string | null {
  const value = record[key];
  return typeof value === "string" ? value : null;
}

function stringArray(value: unknown): string[] | null {
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? [...value]
    : null;
}

function optionalNullableString(
  record: UnknownRecord,
  key: string,
): DecodeResult<string | null | undefined> {
  if (!own(record, key)) {
    return pass(undefined);
  }
  const value = record[key];
  return typeof value === "string" || value === null
    ? pass(value)
    : fail(`${key} must be a string or null`);
}

function decodeCitation(value: unknown): DecodeResult<Citation> {
  if (!isRecord(value)) {
    return fail("citation must be an object");
  }
  const documentId = stringValue(value, "document_id");
  const chunkId = stringValue(value, "chunk_id");
  const title = stringValue(value, "title");
  const sectionPath = stringArray(value.section_path);
  const sourceId = stringValue(value, "source_id");
  const sourceLocator = stringValue(value, "source_locator");
  const retrievedAt = stringValue(value, "retrieved_at");
  const licenseNote = stringValue(value, "license_or_usage_note");
  if (
    documentId === null ||
    chunkId === null ||
    title === null ||
    sectionPath === null ||
    sourceId === null ||
    sourceLocator === null ||
    retrievedAt === null ||
    licenseNote === null ||
    !bounded(documentId, 256) ||
    !bounded(chunkId, 256) ||
    !bounded(title, 1_000) ||
    sectionPath.length > 32 ||
    sectionPath.some((part) => part.length > 512) ||
    !bounded(sourceId, 512) ||
    !bounded(sourceLocator, 4_096) ||
    !bounded(retrievedAt, 128) ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      retrievedAt,
    ) ||
    Number.isNaN(Date.parse(retrievedAt)) ||
    !bounded(licenseNote, 4_096)
  ) {
    return fail("citation is missing a required field");
  }
  return pass({
    document_id: documentId,
    chunk_id: chunkId,
    title,
    section_path: sectionPath,
    source_id: sourceId,
    source_locator: sourceLocator,
    retrieved_at: retrievedAt,
    license_or_usage_note: licenseNote,
  });
}

function decodeSearchItem(value: unknown): DecodeResult<KnowledgeSearchItem> {
  if (!isRecord(value)) {
    return fail("search result must be an object");
  }
  const score = value.score;
  const documentId = stringValue(value, "document_id");
  const chunkId = stringValue(value, "chunk_id");
  const title = stringValue(value, "title");
  const sectionPath = stringArray(value.section_path);
  const text = stringValue(value, "text");
  const language = stringValue(value, "language");
  const classification = stringValue(value, "classification");
  if (
    typeof score !== "number" ||
    !Number.isFinite(score) ||
    documentId === null ||
    chunkId === null ||
    title === null ||
    sectionPath === null ||
    text === null ||
    language === null ||
    classification === null
  ) {
    return fail("search result is missing a required field");
  }
  if (!isRecord(value.game_version_scope)) {
    return fail("game version scope must be an object");
  }
  const scopeKind = stringValue(value.game_version_scope, "kind");
  const scopeValue = value.game_version_scope.value;
  if (
    scopeKind === null ||
    (typeof scopeValue !== "string" && scopeValue !== null)
  ) {
    return fail("game version scope is invalid");
  }
  const citation = decodeCitation(value.citation);
  if (!citation.ok) {
    return citation;
  }
  if (
    documentId !== citation.value.document_id ||
    chunkId !== citation.value.chunk_id ||
    title !== citation.value.title ||
    sectionPath.length !== citation.value.section_path.length ||
    sectionPath.some(
      (part, index) => part !== citation.value.section_path[index],
    )
  ) {
    return fail("search result identity does not match its citation");
  }
  return pass({
    score,
    document_id: documentId,
    chunk_id: chunkId,
    title,
    section_path: sectionPath,
    text,
    language,
    classification,
    game_version_scope: { kind: scopeKind, value: scopeValue },
    citation: citation.value,
  });
}

export function decodeSearchResponse(
  value: unknown,
): DecodeResult<KnowledgeSearchResponse> {
  if (!isRecord(value) || (value.status !== "success" && value.status !== "error")) {
    return fail("search response status is invalid");
  }
  if (!Array.isArray(value.results)) {
    return fail("search response results must be an array");
  }
  if (ownsAny(value, ["answer", "citations", "usage"])) {
    return fail("search response contains contradictory outcome fields");
  }
  if (value.results.length > 20) {
    return fail("search response contains too many results");
  }
  const results: KnowledgeSearchItem[] = [];
  for (const candidate of value.results) {
    const decoded = decodeSearchItem(candidate);
    if (!decoded.ok) {
      return decoded;
    }
    results.push(decoded.value);
  }
  const errorCategory = optionalNullableString(value, "error_category");
  const message = optionalNullableString(value, "message");
  if (!errorCategory.ok || !message.ok) {
    return fail("search response optional error fields are invalid");
  }
  if (value.status === "success") {
    if (
      (errorCategory.value !== undefined && errorCategory.value !== null) ||
      (message.value !== undefined && message.value !== null)
    ) {
      return fail("search success cannot contain error fields");
    }
    return pass({
      status: "success",
      results,
      ...(errorCategory.value === null ? { error_category: null } : {}),
      ...(message.value === null ? { message: null } : {}),
    });
  }
  if (
    results.length !== 0 ||
    typeof errorCategory.value !== "string" ||
    !SEARCH_ERROR_CATEGORIES.includes(
      errorCategory.value as (typeof SEARCH_ERROR_CATEGORIES)[number],
    ) ||
    typeof message.value !== "string" ||
    !nonBlank(message.value)
  ) {
    return fail("search error fields are invalid");
  }
  return pass({
    status: "error",
    results: [],
    error_category: errorCategory.value as (typeof SEARCH_ERROR_CATEGORIES)[number],
    message: message.value,
  });
}

function decodeUsage(value: unknown): DecodeResult<TokenUsage | null> {
  if (value === null) {
    return pass(null);
  }
  if (!isRecord(value)) {
    return fail("usage must be an object or null");
  }
  const result: TokenUsage = {};
  for (const key of ["input_tokens", "output_tokens", "total_tokens"] as const) {
    if (!own(value, key)) {
      continue;
    }
    const candidate = value[key];
    if (
      candidate !== null &&
      (typeof candidate !== "number" ||
        !Number.isSafeInteger(candidate) ||
        candidate < 0)
    ) {
      return fail("usage token count is invalid");
    }
    result[key] = candidate;
  }
  return pass(result);
}

function decodeExplainCitation(value: unknown): DecodeResult<ExplainCitation> {
  if (!isRecord(value)) {
    return fail("explanation citation must be an object");
  }
  const marker = stringValue(value, "marker");
  if (marker === null || !/^\[K[1-9]\d*\]$/.test(marker)) {
    return fail("explanation citation marker is invalid");
  }
  const citation = decodeCitation(value.citation);
  return citation.ok
    ? pass({ marker, citation: citation.value })
    : citation;
}

export function decodeExplainResponse(
  value: unknown,
): DecodeResult<KnowledgeExplainResponse> {
  if (!isRecord(value) || typeof value.status !== "string") {
    return fail("explanation response is invalid");
  }
  if (value.status === "success") {
    if (ownsAny(value, ["message", "error_category", "results"])) {
      return fail("explanation success contains contradictory outcome fields");
    }
    const answer = stringValue(value, "answer");
    if (
      answer === null ||
      !nonBlank(answer) ||
      answer.length > 250_000 ||
      !Array.isArray(value.citations) ||
      value.citations.length < 1 ||
      value.citations.length > 5
    ) {
      return fail("explanation success fields are invalid");
    }
    const citations: ExplainCitation[] = [];
    for (const candidate of value.citations) {
      const decoded = decodeExplainCitation(candidate);
      if (!decoded.ok) {
        return decoded;
      }
      citations.push(decoded.value);
    }
    const allowedMarkers = new Set(citations.map((item) => item.marker));
    if (allowedMarkers.size !== citations.length) {
      return fail("explanation citations must use unique markers");
    }
    const canonicalMarkers = answer.match(/\[K[1-9]\d*\]/g) ?? [];
    const residualMarkerText = answer.replace(/\[K[1-9]\d*\]/g, "");
    const normalizedParagraphs = answer
      .replaceAll("\r\n", "\n")
      .replace(/[\r\u2028\u2029]/g, "\n\n");
    if (
      /\[[Kk]/.test(residualMarkerText) ||
      canonicalMarkers.some((marker) => !allowedMarkers.has(marker)) ||
      citations.some((item) => !answer.includes(item.marker)) ||
      normalizedParagraphs
        .split(/\r?\n\s*\r?\n/)
        .filter((paragraph) => paragraph.trim().length > 0)
        .some(
          (paragraph) =>
            ![...allowedMarkers].some((marker) => paragraph.includes(marker)),
        )
    ) {
      return fail("explanation answer citation markers are invalid");
    }
    const usage = own(value, "usage")
      ? decodeUsage(value.usage)
      : pass<TokenUsage | null>(null);
    if (!usage.ok) {
      return usage;
    }
    return pass({
      status: "success",
      answer,
      citations,
      usage: usage.value,
    });
  }
  if (value.status === "unsupported") {
    if (ownsAny(value, ["answer", "citations", "usage", "error_category", "results"])) {
      return fail("unsupported response contains contradictory outcome fields");
    }
    const message = stringValue(value, "message");
    return message === null
      ? fail("unsupported response message is invalid")
      : pass({ status: "unsupported", message });
  }
  if (value.status === "error") {
    if (ownsAny(value, ["answer", "citations", "usage", "results"])) {
      return fail("explanation error contains contradictory outcome fields");
    }
    const message = stringValue(value, "message");
    const category = value.error_category;
    if (
      message === null ||
      typeof category !== "string" ||
      !EXPLAIN_ERROR_CATEGORIES.includes(
        category as (typeof EXPLAIN_ERROR_CATEGORIES)[number],
      )
    ) {
      return fail("explanation error fields are invalid");
    }
    return pass({
      status: "error",
      error_category: category as (typeof EXPLAIN_ERROR_CATEGORIES)[number],
      message,
    });
  }
  return fail("explanation response status is invalid");
}

function boundedText(value: string, limit: number): string {
  let result = "";
  let count = 0;
  for (const character of value) {
    if (count === limit) {
      break;
    }
    result += character;
    ++count;
  }
  return result;
}

export function summarizeFastApiDetail(value: unknown): string | null {
  if (!isRecord(value) || !Array.isArray(value.detail)) {
    return null;
  }
  const summaries: string[] = [];
  for (const item of value.detail.slice(0, 3)) {
    if (typeof item === "string") {
      summaries.push(boundedText(item, 200));
      continue;
    }
    if (!isRecord(item) || typeof item.msg !== "string") {
      continue;
    }
    const location = Array.isArray(item.loc)
      ? item.loc
          .filter(
            (part): part is string | number =>
              typeof part === "string" || typeof part === "number",
          )
          .map(String)
          .join(".")
      : "";
    const summary = location ? `${location}: ${item.msg}` : item.msg;
    summaries.push(boundedText(summary, 200));
  }
  return summaries.length === 0
    ? null
    : boundedText(summaries.join("; "), 600);
}
