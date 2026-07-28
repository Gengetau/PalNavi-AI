import {
  CAPTURE_ACQUISITION_MESSAGE,
  CAPTURE_ROUTE_CONTENT_SHA256,
  CAPTURE_ROUTE_DATASET_ID,
  CAPTURE_ROUTE_GENDER_CONTENT_SHA256,
  type CaptureGenderRequiredResponse,
  type CaptureInvalidResponse,
  type CaptureRouteRequest,
  type CaptureSearchLimitResponse,
  type CaptureSuccessResponse,
  type CaptureUnreachableResponse,
} from "../src/api/captureRouteContract";

export function captureRequest(
  overrides: Partial<CaptureRouteRequest> = {},
): CaptureRouteRequest {
  return {
    dataset_id: CAPTURE_ROUTE_DATASET_ID,
    target: { species_id: "anubis", gender: "female" },
    inventory: [
      {
        instance_id: "lamball-m",
        species_id: "lamball",
        gender: "male",
      },
    ],
    capture_candidates: [
      {
        candidate_id: "anubis-f",
        species_id: "anubis",
        gender: "female",
      },
    ],
    objective: "minimum_new_captures",
    ...overrides,
  };
}

const boundary = {
  candidates_are_user_supplied: true as const,
  catchability_verified: false as const,
  message: CAPTURE_ACQUISITION_MESSAGE,
} as const;

export function captureSuccess(): CaptureSuccessResponse {
  return {
    status: "success",
    dataset_id: CAPTURE_ROUTE_DATASET_ID,
    content_sha256: CAPTURE_ROUTE_CONTENT_SHA256,
    gender_data_content_sha256: CAPTURE_ROUTE_GENDER_CONTENT_SHA256,
    target: {
      species_id: "anubis",
      gender: "female",
      required_passive_ids: [],
      required_iv_constraints: [],
      generation_depth: 0,
    },
    steps: [],
    capture_requirements: [
      {
        candidate_id: "anubis-f",
        species_id: "anubis",
        gender: "female",
      },
    ],
    cost: {
      new_capture_count: 1,
      generations: 0,
      breeding_steps: 0,
      probability_dependent_cost_available: false,
      expected_attempts: null,
    },
    acquisition_boundary: { ...boundary },
    reachable_states: [],
    unknown_instance_ids: [],
    error_category: null,
    errors: [],
    message: null,
  };
}

export function captureGenderRequired(): CaptureGenderRequiredResponse {
  return {
    status: "gender_required",
    dataset_id: CAPTURE_ROUTE_DATASET_ID,
    content_sha256: CAPTURE_ROUTE_CONTENT_SHA256,
    gender_data_content_sha256: CAPTURE_ROUTE_GENDER_CONTENT_SHA256,
    target: null,
    steps: [],
    capture_requirements: [],
    cost: null,
    acquisition_boundary: { ...boundary },
    reachable_states: [],
    unknown_instance_ids: ["lamball-unknown"],
    error_category: null,
    errors: [],
    message: "Concrete inventory gender is required.",
  };
}

export function captureUnreachable(): CaptureUnreachableResponse {
  return {
    status: "unreachable",
    dataset_id: CAPTURE_ROUTE_DATASET_ID,
    content_sha256: CAPTURE_ROUTE_CONTENT_SHA256,
    gender_data_content_sha256: CAPTURE_ROUTE_GENDER_CONTENT_SHA256,
    target: {
      species_id: "anubis",
      gender: "female",
      required_passive_ids: [],
      required_iv_constraints: [],
      generation_depth: 0,
    },
    steps: [],
    capture_requirements: [],
    cost: null,
    acquisition_boundary: { ...boundary },
    reachable_states: [],
    unknown_instance_ids: [],
    error_category: null,
    errors: [],
    message: "No exact route reaches the target.",
  };
}

export function captureSearchLimit(): CaptureSearchLimitResponse {
  return {
    status: "search_limit_exceeded",
    dataset_id: CAPTURE_ROUTE_DATASET_ID,
    content_sha256: CAPTURE_ROUTE_CONTENT_SHA256,
    gender_data_content_sha256: CAPTURE_ROUTE_GENDER_CONTENT_SHA256,
    target: null,
    steps: [],
    capture_requirements: [],
    cost: null,
    acquisition_boundary: { ...boundary },
    reachable_states: [],
    unknown_instance_ids: [],
    error_category: null,
    errors: [],
    message: "Exact search exceeded its label bound.",
  };
}

export function captureInvalid(): CaptureInvalidResponse {
  return {
    status: "invalid",
    dataset_id: CAPTURE_ROUTE_DATASET_ID,
    content_sha256: null,
    gender_data_content_sha256: null,
    target: null,
    steps: [],
    capture_requirements: [],
    cost: null,
    acquisition_boundary: { ...boundary },
    reachable_states: [],
    unknown_instance_ids: [],
    error_category: "request_invalid",
    errors: [
      {
        code: "invalid_capture_route_request",
        field: "capture_candidates",
        message: "Capture candidates are invalid.",
      },
    ],
    message: "The request was rejected.",
  };
}
