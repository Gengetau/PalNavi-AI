import {
  BREEDING_CONTENT_SHA256,
  BREEDING_DATASET_ID,
} from "./breedingContract";
import type { HttpInvalidFailure } from "./contract";

export const SPECIES_CATALOG_LOCALE_TAGS = [
  "de",
  "en",
  "es",
  "es-MX",
  "fr",
  "id",
  "it",
  "ja",
  "ko",
  "pl",
  "pt-BR",
  "ru",
  "th",
  "tr",
  "vi",
  "zh-Hans",
  "zh-Hant",
] as const;

export type SpeciesCatalogLocale =
  (typeof SPECIES_CATALOG_LOCALE_TAGS)[number];

export interface SpeciesCatalogRecord {
  species_id: string;
  paldeck_number: number;
  paldeck_suffix: string | null;
  is_variant: boolean;
  localized_names: Record<SpeciesCatalogLocale, string>;
  source_record_sha256: string;
}

export interface SpeciesCatalogSuccessResponse {
  status: "success";
  dataset_id: typeof BREEDING_DATASET_ID;
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  locale_tags: [...typeof SPECIES_CATALOG_LOCALE_TAGS];
  records: SpeciesCatalogRecord[];
  error_category: null;
  errors: [];
  message: null;
}

export interface SpeciesCatalogBackendFailureResponse {
  status: "not_found" | "invalid";
  dataset_id: typeof BREEDING_DATASET_ID;
  content_sha256: null;
  locale_tags: [];
  records: [];
  error_category: string;
  errors: { code: string; field: string; message: string }[];
  message: string;
}

export type SpeciesCatalogResponse =
  | SpeciesCatalogSuccessResponse
  | SpeciesCatalogBackendFailureResponse;

export type SpeciesCatalogCallResult =
  | { kind: "success"; response: SpeciesCatalogSuccessResponse }
  | {
      kind: "backend-invalid";
      response: SpeciesCatalogBackendFailureResponse;
      httpStatus: number;
    }
  | HttpInvalidFailure
  | { kind: "network-error"; message: string }
  | { kind: "aborted" };

export interface SpeciesCatalogClient {
  load(options: { signal: AbortSignal }): Promise<SpeciesCatalogCallResult>;
}

type DecodeResult =
  | { ok: true; value: SpeciesCatalogResponse }
  | { ok: false };

const RESPONSE_KEYS = [
  "status",
  "dataset_id",
  "content_sha256",
  "locale_tags",
  "records",
  "error_category",
  "errors",
  "message",
] as const;
const RECORD_KEYS = [
  "species_id",
  "paldeck_number",
  "paldeck_suffix",
  "is_variant",
  "localized_names",
  "source_record_sha256",
] as const;
const ERROR_KEYS = ["code", "field", "message"] as const;
const SPECIES_ID_PATTERN = /^[a-z][a-z0-9_]{0,63}$/;
const HASH_PATTERN = /^[0-9a-f]{64}$/;
const PALDECK_SUFFIX_PATTERN = /^[A-Z0-9]{1,8}$/;
const MAX_LOCALIZED_NAME_LENGTH = 80;
const EXPECTED_RECORD_COUNT = 299;

function isObject(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  return (
    actual.length === wanted.length &&
    actual.every((key, index) => key === wanted[index])
  );
}

function isBoundedText(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.length >= 1 &&
    value.length <= maximum &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function decodeLocalizedNames(
  value: unknown,
): Record<SpeciesCatalogLocale, string> | null {
  if (!isObject(value) || !hasExactKeys(value, SPECIES_CATALOG_LOCALE_TAGS)) {
    return null;
  }
  for (const locale of SPECIES_CATALOG_LOCALE_TAGS) {
    if (!isBoundedText(value[locale], MAX_LOCALIZED_NAME_LENGTH)) {
      return null;
    }
  }
  return value as unknown as Record<SpeciesCatalogLocale, string>;
}

function decodeRecord(value: unknown): SpeciesCatalogRecord | null {
  if (!isObject(value) || !hasExactKeys(value, RECORD_KEYS)) {
    return null;
  }
  const names = decodeLocalizedNames(value.localized_names);
  if (
    typeof value.species_id !== "string" ||
    SPECIES_ID_PATTERN.exec(value.species_id)?.[0] !== value.species_id ||
    typeof value.paldeck_number !== "number" ||
    !Number.isInteger(value.paldeck_number) ||
    value.paldeck_number < 1 ||
    value.paldeck_number > 99_999 ||
    (value.paldeck_suffix !== null &&
      (typeof value.paldeck_suffix !== "string" ||
        PALDECK_SUFFIX_PATTERN.exec(value.paldeck_suffix)?.[0] !==
          value.paldeck_suffix)) ||
    typeof value.is_variant !== "boolean" ||
    names === null ||
    typeof value.source_record_sha256 !== "string" ||
    HASH_PATTERN.exec(value.source_record_sha256)?.[0] !==
      value.source_record_sha256
  ) {
    return null;
  }
  return {
    species_id: value.species_id,
    paldeck_number: value.paldeck_number,
    paldeck_suffix: value.paldeck_suffix,
    is_variant: value.is_variant,
    localized_names: names,
    source_record_sha256: value.source_record_sha256,
  };
}

function decodeSuccess(
  value: Record<string, unknown>,
): SpeciesCatalogSuccessResponse | null {
  if (
    value.dataset_id !== BREEDING_DATASET_ID ||
    value.content_sha256 !== BREEDING_CONTENT_SHA256 ||
    value.error_category !== null ||
    value.message !== null ||
    !Array.isArray(value.errors) ||
    value.errors.length !== 0 ||
    !Array.isArray(value.locale_tags) ||
    value.locale_tags.length !== SPECIES_CATALOG_LOCALE_TAGS.length ||
    !value.locale_tags.every(
      (locale, index) => locale === SPECIES_CATALOG_LOCALE_TAGS[index],
    ) ||
    !Array.isArray(value.records) ||
    value.records.length !== EXPECTED_RECORD_COUNT
  ) {
    return null;
  }

  const records: SpeciesCatalogRecord[] = [];
  const speciesIds = new Set<string>();
  const sourceHashes = new Set<string>();
  let previousSpeciesId: string | null = null;
  for (const rawRecord of value.records) {
    const record = decodeRecord(rawRecord);
    if (
      record === null ||
      (previousSpeciesId !== null &&
        record.species_id <= previousSpeciesId) ||
      speciesIds.has(record.species_id) ||
      sourceHashes.has(record.source_record_sha256)
    ) {
      return null;
    }
    records.push(record);
    speciesIds.add(record.species_id);
    sourceHashes.add(record.source_record_sha256);
    previousSpeciesId = record.species_id;
  }
  return {
    status: "success",
    dataset_id: BREEDING_DATASET_ID,
    content_sha256: BREEDING_CONTENT_SHA256,
    locale_tags: [...SPECIES_CATALOG_LOCALE_TAGS],
    records,
    error_category: null,
    errors: [],
    message: null,
  };
}

function decodeFailure(
  value: Record<string, unknown>,
): SpeciesCatalogBackendFailureResponse | null {
  if (
    (value.status !== "not_found" && value.status !== "invalid") ||
    value.dataset_id !== BREEDING_DATASET_ID ||
    value.content_sha256 !== null ||
    !Array.isArray(value.locale_tags) ||
    value.locale_tags.length !== 0 ||
    !Array.isArray(value.records) ||
    value.records.length !== 0 ||
    !isBoundedText(value.error_category, 128) ||
    !isBoundedText(value.message, 500) ||
    !Array.isArray(value.errors) ||
    value.errors.length === 0 ||
    value.errors.length > 32
  ) {
    return null;
  }
  const errors = [];
  for (const error of value.errors) {
    if (
      !isObject(error) ||
      !hasExactKeys(error, ERROR_KEYS) ||
      !isBoundedText(error.code, 128) ||
      !isBoundedText(error.field, 256) ||
      !isBoundedText(error.message, 500)
    ) {
      return null;
    }
    errors.push({
      code: error.code,
      field: error.field,
      message: error.message,
    });
  }
  return {
    status: value.status,
    dataset_id: BREEDING_DATASET_ID,
    content_sha256: null,
    locale_tags: [],
    records: [],
    error_category: value.error_category,
    errors,
    message: value.message,
  };
}

export function decodeSpeciesCatalogResponse(value: unknown): DecodeResult {
  if (!isObject(value) || !hasExactKeys(value, RESPONSE_KEYS)) {
    return { ok: false };
  }
  if (value.status === "success") {
    const decoded = decodeSuccess(value);
    return decoded === null
      ? { ok: false }
      : { ok: true, value: decoded };
  }
  const decoded = decodeFailure(value);
  return decoded === null
    ? { ok: false }
    : { ok: true, value: decoded };
}
