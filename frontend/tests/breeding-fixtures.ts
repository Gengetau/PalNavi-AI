import {
  BREEDING_CONTENT_SHA256,
  BREEDING_DATASET_ID,
  BREEDING_GENDER_CONTENT_SHA256,
  type BreedingGenderRequiredResponse,
  type BreedingInvalidResponse,
  type BreedingRequest,
  type BreedingRouteState,
  type BreedingSuccessResponse,
  type BreedingUnreachableResponse,
} from "../src/api/breedingContract";
import {
  SPECIES_CATALOG_LOCALE_TAGS,
  type SpeciesCatalogLocale,
  type SpeciesCatalogRecord,
  type SpeciesCatalogSuccessResponse,
} from "../src/api/breedingCatalogContract";
import goldenContracts from "./golden/knowledge-contracts.json";

const clone = <T>(value: T): T =>
  JSON.parse(JSON.stringify(value)) as T;

export function breedingRequest(
  overrides: Partial<BreedingRequest> = {},
): BreedingRequest {
  return {
    ...(clone(goldenContracts.gender_route_request) as BreedingRequest),
    ...overrides,
  };
}

export function breedingSuccess(): BreedingSuccessResponse {
  return clone(
    goldenContracts.gender_route_success,
  ) as BreedingSuccessResponse;
}

export function breedingGenderRequired(): BreedingGenderRequiredResponse {
  return clone(
    goldenContracts.gender_route_gender_required,
  ) as BreedingGenderRequiredResponse;
}

export function breedingState(
  overrides: Partial<BreedingRouteState> = {},
): BreedingRouteState {
  return {
    species_id: "dumud",
    gender: "male",
    required_passive_ids: [],
    required_iv_constraints: [],
    generation_depth: 0,
    ...overrides,
  };
}

export function breedingZeroStepSuccess(): BreedingSuccessResponse {
  return {
    status: "success",
    dataset_id: BREEDING_DATASET_ID,
    content_sha256: BREEDING_CONTENT_SHA256,
    gender_data_content_sha256: BREEDING_GENDER_CONTENT_SHA256,
    target: breedingState({
      species_id: "wixen_noct",
      gender: "female",
    }),
    steps: [],
    cost: {
      generations: 0,
      breeding_steps: 0,
      probability_dependent_cost_available: false,
      expected_attempts: null,
    },
    reachable_states: [],
    unknown_instance_ids: [],
    error_category: null,
    errors: [],
    message: null,
  };
}

export function breedingUnreachable(): BreedingUnreachableResponse {
  return {
    status: "unreachable",
    dataset_id: BREEDING_DATASET_ID,
    content_sha256: BREEDING_CONTENT_SHA256,
    gender_data_content_sha256: BREEDING_GENDER_CONTENT_SHA256,
    target: breedingState({
      species_id: "wixen_noct",
      gender: "female",
      generation_depth: 0,
    }),
    steps: [],
    cost: null,
    reachable_states: [
      breedingState({ species_id: "dumud", gender: "male" }),
      breedingState({
        species_id: "katress_ignis",
        gender: "female",
      }),
      breedingState({ species_id: "wixen", gender: "female" }),
    ],
    unknown_instance_ids: [],
    error_category: null,
    errors: [],
    message: "No route reaches the requested target.",
  };
}

export function breedingInvalid(): BreedingInvalidResponse {
  return {
    status: "invalid",
    dataset_id: BREEDING_DATASET_ID,
    content_sha256: null,
    gender_data_content_sha256: null,
    target: null,
    steps: [],
    cost: null,
    reachable_states: [],
    unknown_instance_ids: [],
    error_category: "request_invalid",
    errors: [
      {
        code: "invalid_route_request",
        field: "target_or_inventory",
        message: "The route request is invalid.",
      },
    ],
    message: "The route request was rejected.",
  };
}

function catalogNames(
  speciesId: string,
): Record<SpeciesCatalogLocale, string> {
  const anubisNames: Partial<Record<SpeciesCatalogLocale, string>> = {
    en: "Anubis",
    ja: "アヌビス",
    "zh-Hans": "阿努比斯",
    "zh-Hant": "阿努比斯",
  };
  return Object.fromEntries(
    SPECIES_CATALOG_LOCALE_TAGS.map((locale) => [
      locale,
      speciesId === "anubis"
        ? anubisNames[locale] ?? `Anubis ${locale}`
        : `${speciesId} ${locale}`,
    ]),
  ) as Record<SpeciesCatalogLocale, string>;
}

export function speciesCatalogSuccess(): SpeciesCatalogSuccessResponse {
  const speciesIds = [
    "anubis",
    ...Array.from(
      { length: 298 },
      (_value, index) => `pal_${index.toString().padStart(3, "0")}`,
    ),
  ].sort();
  const records: SpeciesCatalogRecord[] = speciesIds.map(
    (speciesId, index) => ({
      species_id: speciesId,
      paldeck_number: index + 1,
      paldeck_suffix: null,
      is_variant: false,
      localized_names: catalogNames(speciesId),
      source_record_sha256: index.toString(16).padStart(64, "0"),
    }),
  );
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
