import type { HttpInvalidFailure } from "./contract";

export const BREEDING_DATASET_ID =
  "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47";
export const BREEDING_CONTENT_SHA256 =
  "b7fbe9b7395d2aef6758ff162da8fb738cf1fcd3ec5c7d50133c3d5edafdd30b";
export const BREEDING_GENDER_CONTENT_SHA256 =
  "11173754c8dcf123df6be22823210d80f9b866732cbff80f112c70ba8208cfdf";

export type ConcreteGender = "male" | "female";
export type InventoryGender = ConcreteGender | "unknown";
export type BreedingResultKind =
  | "same_species"
  | "ordinary_power"
  | "fixed_special"
  | "gender_directed";

export interface BreedingTarget {
  species_id: string;
  gender: ConcreteGender;
}

export interface BreedingInventoryItem {
  instance_id: string;
  species_id: string;
  gender: InventoryGender;
}

export interface BreedingRequest {
  dataset_id: typeof BREEDING_DATASET_ID;
  target: BreedingTarget;
  inventory: BreedingInventoryItem[];
  objective: "minimum_generations";
}

export interface BreedingRouteState {
  species_id: string;
  gender: ConcreteGender;
  required_passive_ids: [];
  required_iv_constraints: [];
  generation_depth: number;
}

export interface BreedingRouteStep {
  order: number;
  generation: number;
  parent_a: BreedingRouteState;
  parent_b: BreedingRouteState;
  child: BreedingRouteState;
  result_kind: BreedingResultKind;
  source_record_hash: string;
}

export interface BreedingRouteCost {
  generations: number;
  breeding_steps: number;
  probability_dependent_cost_available: false;
  expected_attempts: null;
}

export interface BreedingValidationIssue {
  code: string;
  field: string;
  message: string;
}

interface BreedingResponseBase {
  dataset_id: typeof BREEDING_DATASET_ID;
  content_sha256: typeof BREEDING_CONTENT_SHA256 | null;
  gender_data_content_sha256:
    | typeof BREEDING_GENDER_CONTENT_SHA256
    | null;
  steps: BreedingRouteStep[];
  reachable_states: BreedingRouteState[];
  unknown_instance_ids: string[];
  errors: BreedingValidationIssue[];
}

export interface BreedingSuccessResponse extends BreedingResponseBase {
  status: "success";
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  gender_data_content_sha256: typeof BREEDING_GENDER_CONTENT_SHA256;
  target: BreedingRouteState;
  cost: BreedingRouteCost;
  reachable_states: [];
  unknown_instance_ids: [];
  error_category: null;
  errors: [];
  message: null;
}

export interface BreedingGenderRequiredResponse extends BreedingResponseBase {
  status: "gender_required";
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  gender_data_content_sha256: typeof BREEDING_GENDER_CONTENT_SHA256;
  target: null;
  steps: [];
  cost: null;
  reachable_states: [];
  error_category: null;
  errors: [];
  message: string;
}

export interface BreedingUnreachableResponse extends BreedingResponseBase {
  status: "unreachable";
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  gender_data_content_sha256: typeof BREEDING_GENDER_CONTENT_SHA256;
  target: BreedingRouteState;
  steps: [];
  cost: null;
  unknown_instance_ids: [];
  error_category: null;
  errors: [];
  message: string;
}

export interface BreedingInvalidResponse extends BreedingResponseBase {
  status: "invalid";
  target: null;
  steps: [];
  cost: null;
  reachable_states: [];
  unknown_instance_ids: [];
  error_category: string;
  message: string;
}

export type BreedingResponse =
  | BreedingSuccessResponse
  | BreedingGenderRequiredResponse
  | BreedingUnreachableResponse
  | BreedingInvalidResponse;

export type BreedingCallResult =
  | { kind: "success"; response: BreedingSuccessResponse }
  | {
      kind: "gender-required";
      response: BreedingGenderRequiredResponse;
    }
  | { kind: "unreachable"; response: BreedingUnreachableResponse }
  | {
      kind: "backend-invalid";
      response: BreedingInvalidResponse;
      httpStatus: number;
    }
  | HttpInvalidFailure
  | { kind: "network-error"; message: string }
  | { kind: "aborted" };

export interface BreedingClient {
  plan(
    request: Readonly<BreedingRequest>,
    options: { signal: AbortSignal },
  ): Promise<BreedingCallResult>;
}
