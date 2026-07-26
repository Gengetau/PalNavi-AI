import { describe, expect, it } from "vitest";

import {
  decodeSpeciesCatalogResponse,
  SPECIES_CATALOG_LOCALE_TAGS,
} from "../src/api/breedingCatalogContract";
import { BREEDING_DATASET_ID } from "../src/api/breedingContract";
import { speciesCatalogSuccess } from "./breeding-fixtures";

const clone = <T>(value: T): T =>
  JSON.parse(JSON.stringify(value)) as T;

describe("species catalog runtime contract", () => {
  it("accepts the exact complete sorted catalog", () => {
    const result = decodeSpeciesCatalogResponse(speciesCatalogSuccess());

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.status).toBe("success");
      expect(result.value.records).toHaveLength(299);
      expect(result.value.locale_tags).toEqual(
        SPECIES_CATALOG_LOCALE_TAGS,
      );
    }
  });

  it.each([
    ["extra top-level key", (value: Record<string, unknown>) => {
      value.extra = true;
    }],
    ["wrong dataset", (value: Record<string, unknown>) => {
      value.dataset_id = "another-dataset";
    }],
    ["wrong content identity", (value: Record<string, unknown>) => {
      value.content_sha256 = "0".repeat(64);
    }],
    ["locale drift", (value: Record<string, unknown>) => {
      value.locale_tags = [...SPECIES_CATALOG_LOCALE_TAGS].reverse();
    }],
    ["missing record", (value: Record<string, unknown>) => {
      (value.records as unknown[]).pop();
    }],
    ["unordered records", (value: Record<string, unknown>) => {
      const records = value.records as unknown[];
      [records[0], records[1]] = [records[1], records[0]];
    }],
    ["duplicate species", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      records[1]!.species_id = records[0]!.species_id;
    }],
    ["duplicate source hash", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      records[1]!.source_record_sha256 =
        records[0]!.source_record_sha256;
    }],
    ["record extra key", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      records[0]!.raw_name = "forbidden";
    }],
    ["missing locale", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      const names = records[0]!.localized_names as Record<string, unknown>;
      delete names.ja;
    }],
    ["extra locale", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      const names = records[0]!.localized_names as Record<string, unknown>;
      names["en-US"] = "extra";
    }],
    ["empty name", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      const names = records[0]!.localized_names as Record<string, unknown>;
      names.en = "";
    }],
    ["control character name", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      const names = records[0]!.localized_names as Record<string, unknown>;
      names.en = "bad\nname";
    }],
    ["invalid Paldeck number", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      records[0]!.paldeck_number = 1.5;
    }],
    ["invalid source hash", (value: Record<string, unknown>) => {
      const records = value.records as Record<string, unknown>[];
      records[0]!.source_record_sha256 = "invalid";
    }],
  ])("rejects %s", (_name, mutate) => {
    const value = clone(speciesCatalogSuccess()) as unknown as Record<
      string,
      unknown
    >;
    mutate(value);

    expect(decodeSpeciesCatalogResponse(value)).toEqual({ ok: false });
  });

  it("strictly accepts a deterministic backend invalid response", () => {
    const response = {
      status: "invalid",
      dataset_id: BREEDING_DATASET_ID,
      content_sha256: null,
      locale_tags: [],
      records: [],
      error_category: "dataset_invalid",
      errors: [
        {
          code: "malformed_palworld_record",
          field: "pals.json.records",
          message: "Catalog is malformed.",
        },
      ],
      message: "Species catalog could not be validated.",
    };

    expect(decodeSpeciesCatalogResponse(response).ok).toBe(true);
    expect(
      decodeSpeciesCatalogResponse({ ...response, unexpected: true }),
    ).toEqual({ ok: false });
  });
});
