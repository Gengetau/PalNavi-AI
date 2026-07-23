import type { KnowledgeRequest } from "../api/contract";

export interface KnowledgeFormModel {
  query: string;
  language: string;
  exactGameVersion: string;
  syntheticOnly: boolean;
  limit: string;
}

export const INITIAL_FORM: KnowledgeFormModel = {
  query: "",
  language: "",
  exactGameVersion: "",
  syntheticOnly: true,
  limit: "5",
};

export type FormField = "query" | "language" | "exactGameVersion" | "limit";
export type FieldErrors = Partial<Record<FormField, string>>;
export type RequestValidationResult =
  | { ok: true; request: KnowledgeRequest }
  | { ok: false; errors: FieldErrors };

const languagePattern = /^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$/;
const lineSeparatorPattern = /[\r\n\u2028\u2029]/;
const codePointLength = (value: string): number => [...value].length;

export function validateAndBuildRequest(
  model: Readonly<KnowledgeFormModel>,
): RequestValidationResult {
  const query = model.query.trim();
  const language = model.language.trim();
  const exactGameVersion = model.exactGameVersion.trim();
  const rawLimit = model.limit.trim();
  const errors: FieldErrors = {};

  if (codePointLength(query) === 0 || codePointLength(query) > 500) {
    errors.query = "Enter a question between 1 and 500 characters.";
  }
  if (
    lineSeparatorPattern.test(model.language) ||
    (language &&
      (codePointLength(language) > 35 ||
        language.match(languagePattern)?.[0] !== language))
  ) {
    errors.language = "Use a language tag such as en, en-US, or zh_Hant.";
  }
  if (codePointLength(exactGameVersion) > 64) {
    errors.exactGameVersion = "Use at most 64 characters for the exact version.";
  }
  if (!/^\d+$/.test(rawLimit)) {
    errors.limit = "Enter a whole-number limit from 1 through 20.";
  } else {
    const limit = Number(rawLimit);
    if (!Number.isInteger(limit) || limit < 1 || limit > 20) {
      errors.limit = "Enter a whole-number limit from 1 through 20.";
    }
  }

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors };
  }

  const request: KnowledgeRequest = {
    query,
    synthetic_only: model.syntheticOnly,
    limit: Number(rawLimit),
  };
  if (language) {
    request.language = language;
  }
  if (exactGameVersion) {
    request.exact_game_version = exactGameVersion;
  }
  return { ok: true, request };
}
