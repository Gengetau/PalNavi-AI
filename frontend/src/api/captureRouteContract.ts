import type { HttpInvalidFailure } from "./contract";
import {
  BREEDING_CONTENT_SHA256,
  BREEDING_DATASET_ID,
  BREEDING_GENDER_CONTENT_SHA256,
  type BreedingInventoryItem,
  type BreedingResultKind,
  type BreedingRouteState,
  type BreedingRouteStep,
  type BreedingTarget,
  type BreedingValidationIssue,
  type ConcreteGender,
} from "./breedingContract";

export {
  BREEDING_CONTENT_SHA256 as CAPTURE_ROUTE_CONTENT_SHA256,
  BREEDING_DATASET_ID as CAPTURE_ROUTE_DATASET_ID,
  BREEDING_GENDER_CONTENT_SHA256 as CAPTURE_ROUTE_GENDER_CONTENT_SHA256,
};

export const CAPTURE_ACQUISITION_MESSAGE =
  "Capture candidates are user-supplied hypothetical individuals; PalNavi does not verify catchability or encounter availability.";

export interface CaptureCandidate {
  candidate_id: string;
  species_id: string;
  gender: ConcreteGender;
}

export interface CaptureRouteRequest {
  dataset_id: typeof BREEDING_DATASET_ID;
  target: BreedingTarget;
  inventory: BreedingInventoryItem[];
  capture_candidates: CaptureCandidate[];
  objective: "minimum_new_captures";
}

export interface CaptureRequirement extends CaptureCandidate {}

export interface CaptureRouteCost {
  new_capture_count: number;
  generations: number;
  breeding_steps: number;
  probability_dependent_cost_available: false;
  expected_attempts: null;
}

export interface CaptureAcquisitionBoundary {
  candidates_are_user_supplied: true;
  catchability_verified: false;
  message: typeof CAPTURE_ACQUISITION_MESSAGE;
}

interface CaptureResponseBase {
  dataset_id: typeof BREEDING_DATASET_ID;
  content_sha256: typeof BREEDING_CONTENT_SHA256 | null;
  gender_data_content_sha256:
    | typeof BREEDING_GENDER_CONTENT_SHA256
    | null;
  acquisition_boundary: CaptureAcquisitionBoundary;
  reachable_states: BreedingRouteState[];
  unknown_instance_ids: string[];
  error_category: string | null;
  errors: BreedingValidationIssue[];
  message: string | null;
}

export interface CaptureSuccessResponse extends CaptureResponseBase {
  status: "success";
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  gender_data_content_sha256: typeof BREEDING_GENDER_CONTENT_SHA256;
  target: BreedingRouteState;
  steps: BreedingRouteStep[];
  capture_requirements: CaptureRequirement[];
  cost: CaptureRouteCost;
  reachable_states: [];
  unknown_instance_ids: [];
  error_category: null;
  errors: [];
  message: null;
}

export interface CaptureGenderRequiredResponse
  extends CaptureResponseBase {
  status: "gender_required";
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  gender_data_content_sha256: typeof BREEDING_GENDER_CONTENT_SHA256;
  target: null;
  steps: [];
  capture_requirements: [];
  cost: null;
  reachable_states: [];
  error_category: null;
  errors: [];
  message: string;
}

export interface CaptureUnreachableResponse extends CaptureResponseBase {
  status: "unreachable";
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  gender_data_content_sha256: typeof BREEDING_GENDER_CONTENT_SHA256;
  target: BreedingRouteState;
  steps: [];
  capture_requirements: [];
  cost: null;
  unknown_instance_ids: [];
  error_category: null;
  errors: [];
  message: string;
}

export interface CaptureSearchLimitResponse extends CaptureResponseBase {
  status: "search_limit_exceeded";
  content_sha256: typeof BREEDING_CONTENT_SHA256;
  gender_data_content_sha256: typeof BREEDING_GENDER_CONTENT_SHA256;
  target: null;
  steps: [];
  capture_requirements: [];
  cost: null;
  reachable_states: [];
  unknown_instance_ids: [];
  error_category: null;
  errors: [];
  message: string;
}

export interface CaptureInvalidResponse extends CaptureResponseBase {
  status: "invalid";
  target: null;
  steps: [];
  capture_requirements: [];
  cost: null;
  reachable_states: [];
  unknown_instance_ids: [];
  error_category: string;
  message: string;
}

export type CaptureRouteResponse =
  | CaptureSuccessResponse
  | CaptureGenderRequiredResponse
  | CaptureUnreachableResponse
  | CaptureSearchLimitResponse
  | CaptureInvalidResponse;

export type CaptureRouteCallResult =
  | { kind: "success"; response: CaptureSuccessResponse }
  | {
      kind: "gender-required";
      response: CaptureGenderRequiredResponse;
    }
  | { kind: "unreachable"; response: CaptureUnreachableResponse }
  | {
      kind: "search-limit-exceeded";
      response: CaptureSearchLimitResponse;
    }
  | {
      kind: "backend-invalid";
      response: CaptureInvalidResponse;
      httpStatus: number;
    }
  | HttpInvalidFailure
  | { kind: "network-error"; message: string }
  | { kind: "aborted" };

export interface CaptureRouteClient {
  plan(
    request: Readonly<CaptureRouteRequest>,
    options: { signal: AbortSignal },
  ): Promise<CaptureRouteCallResult>;
}

export type {
  BreedingInventoryItem,
  BreedingResultKind,
  BreedingRouteState,
  BreedingRouteStep,
  BreedingTarget,
  BreedingValidationIssue,
  ConcreteGender,
};
