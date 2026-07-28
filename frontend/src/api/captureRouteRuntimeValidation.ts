import {
  CAPTURE_ACQUISITION_MESSAGE,
  CAPTURE_ROUTE_CONTENT_SHA256,
  CAPTURE_ROUTE_DATASET_ID,
  CAPTURE_ROUTE_GENDER_CONTENT_SHA256,
  type CaptureAcquisitionBoundary,
  type CaptureCandidate,
  type CaptureInvalidResponse,
  type CaptureRequirement,
  type CaptureRouteCost,
  type CaptureRouteRequest,
  type CaptureRouteResponse,
  type CaptureSuccessResponse,
  type BreedingRouteState,
  type BreedingRouteStep,
  type BreedingValidationIssue,
} from "./captureRouteContract";

const SPECIES_ID = /^[a-z][a-z0-9_]{0,63}$/;
const INSTANCE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const RESPONSE_KEYS = [
  "status",
  "dataset_id",
  "content_sha256",
  "gender_data_content_sha256",
  "target",
  "steps",
  "capture_requirements",
  "cost",
  "acquisition_boundary",
  "reachable_states",
  "unknown_instance_ids",
  "error_category",
  "errors",
  "message",
] as const;

type DecodeResult =
  | { ok: true; value: CaptureRouteResponse }
  | { ok: false };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value).sort();
  return (
    keys.length === expected.length &&
    keys.every((key, index) => key === [...expected].sort()[index])
  );
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= 0;
}

function isEmptyArray(value: unknown): value is [] {
  return Array.isArray(value) && value.length === 0;
}

function isConcreteGender(value: unknown): value is "male" | "female" {
  return value === "male" || value === "female";
}

function isState(value: unknown): value is BreedingRouteState {
  if (!isRecord(value)) return false;
  return (
    exactKeys(value, [
      "species_id",
      "gender",
      "required_passive_ids",
      "required_iv_constraints",
      "generation_depth",
    ]) &&
    typeof value.species_id === "string" &&
    SPECIES_ID.test(value.species_id) &&
    isConcreteGender(value.gender) &&
    Array.isArray(value.required_passive_ids) &&
    value.required_passive_ids.length === 0 &&
    Array.isArray(value.required_iv_constraints) &&
    value.required_iv_constraints.length === 0 &&
    isNonNegativeInteger(value.generation_depth)
  );
}

function isStep(value: unknown, index: number): value is BreedingRouteStep {
  if (!isRecord(value)) return false;
  return (
    exactKeys(value, [
      "order",
      "generation",
      "parent_a",
      "parent_b",
      "child",
      "result_kind",
      "source_record_hash",
    ]) &&
    value.order === index + 1 &&
    isNonNegativeInteger(value.generation) &&
    value.generation > 0 &&
    isState(value.parent_a) &&
    isState(value.parent_b) &&
    value.parent_a.gender !== value.parent_b.gender &&
    isState(value.child) &&
    value.child.generation_depth === value.generation &&
    [
      "same_species",
      "ordinary_power",
      "fixed_special",
      "gender_directed",
    ].includes(String(value.result_kind)) &&
    typeof value.source_record_hash === "string" &&
    SHA256.test(value.source_record_hash)
  );
}

function isCandidate(value: unknown): value is CaptureCandidate {
  if (!isRecord(value)) return false;
  return (
    exactKeys(value, ["candidate_id", "species_id", "gender"]) &&
    typeof value.candidate_id === "string" &&
    INSTANCE_ID.test(value.candidate_id) &&
    typeof value.species_id === "string" &&
    SPECIES_ID.test(value.species_id) &&
    isConcreteGender(value.gender)
  );
}

function isRequirement(value: unknown): value is CaptureRequirement {
  return isCandidate(value);
}

function isCost(value: unknown): value is CaptureRouteCost {
  if (!isRecord(value)) return false;
  return (
    exactKeys(value, [
      "new_capture_count",
      "generations",
      "breeding_steps",
      "probability_dependent_cost_available",
      "expected_attempts",
    ]) &&
    isNonNegativeInteger(value.new_capture_count) &&
    isNonNegativeInteger(value.generations) &&
    isNonNegativeInteger(value.breeding_steps) &&
    value.probability_dependent_cost_available === false &&
    value.expected_attempts === null
  );
}

function isBoundary(value: unknown): value is CaptureAcquisitionBoundary {
  if (!isRecord(value)) return false;
  return (
    exactKeys(value, [
      "candidates_are_user_supplied",
      "catchability_verified",
      "message",
    ]) &&
    value.candidates_are_user_supplied === true &&
    value.catchability_verified === false &&
    value.message === CAPTURE_ACQUISITION_MESSAGE
  );
}

function isIssue(value: unknown): value is BreedingValidationIssue {
  if (!isRecord(value)) return false;
  return (
    exactKeys(value, ["code", "field", "message"]) &&
    typeof value.code === "string" &&
    value.code.length > 0 &&
    typeof value.field === "string" &&
    value.field.length > 0 &&
    typeof value.message === "string" &&
    value.message.length > 0
  );
}

function validBase(value: Record<string, unknown>): boolean {
  return (
    exactKeys(value, RESPONSE_KEYS) &&
    value.dataset_id === CAPTURE_ROUTE_DATASET_ID &&
    isBoundary(value.acquisition_boundary) &&
    Array.isArray(value.steps) &&
    value.steps.length <= 598 &&
    value.steps.every((step, index) => isStep(step, index)) &&
    Array.isArray(value.capture_requirements) &&
    value.capture_requirements.length <= 16 &&
    value.capture_requirements.every(isRequirement) &&
    new Set(
      (value.capture_requirements as CaptureRequirement[]).map(
        (item) => item.candidate_id,
      ),
    ).size === value.capture_requirements.length &&
    Array.isArray(value.reachable_states) &&
    value.reachable_states.length <= 598 &&
    value.reachable_states.every(isState) &&
    Array.isArray(value.unknown_instance_ids) &&
    value.unknown_instance_ids.length <= 299 &&
    value.unknown_instance_ids.every(
      (item) => typeof item === "string" && INSTANCE_ID.test(item),
    ) &&
    new Set(value.unknown_instance_ids).size ===
      value.unknown_instance_ids.length &&
    Array.isArray(value.errors) &&
    value.errors.length <= 64 &&
    value.errors.every(isIssue)
  );
}

function fixedIdentities(value: Record<string, unknown>): boolean {
  return (
    value.content_sha256 === CAPTURE_ROUTE_CONTENT_SHA256 &&
    value.gender_data_content_sha256 ===
      CAPTURE_ROUTE_GENDER_CONTENT_SHA256
  );
}

function isSuccess(value: Record<string, unknown>): boolean {
  return (
    fixedIdentities(value) &&
    isState(value.target) &&
    isCost(value.cost) &&
    Array.isArray(value.capture_requirements) &&
    Array.isArray(value.steps) &&
    value.cost.new_capture_count === value.capture_requirements.length &&
    value.cost.generations === value.target.generation_depth &&
    value.cost.breeding_steps === value.steps.length &&
    isEmptyArray(value.reachable_states) &&
    isEmptyArray(value.unknown_instance_ids) &&
    value.error_category === null &&
    isEmptyArray(value.errors) &&
    value.message === null
  );
}

export function decodeCaptureRouteResponse(value: unknown): DecodeResult {
  if (!isRecord(value) || !validBase(value)) return { ok: false };
  switch (value.status) {
    case "success":
      return isSuccess(value)
        ? { ok: true, value: value as unknown as CaptureRouteResponse }
        : { ok: false };
    case "gender_required":
      if (
        fixedIdentities(value) &&
        value.target === null &&
        isEmptyArray(value.steps) &&
        isEmptyArray(value.capture_requirements) &&
        value.cost === null &&
        isEmptyArray(value.reachable_states) &&
        Array.isArray(value.unknown_instance_ids) &&
        value.unknown_instance_ids.length > 0 &&
        value.error_category === null &&
        isEmptyArray(value.errors) &&
        typeof value.message === "string" &&
        value.message.length > 0
      ) {
        return { ok: true, value: value as unknown as CaptureRouteResponse };
      }
      return { ok: false };
    case "unreachable":
      if (
        fixedIdentities(value) &&
        isState(value.target) &&
        isEmptyArray(value.steps) &&
        isEmptyArray(value.capture_requirements) &&
        value.cost === null &&
        isEmptyArray(value.unknown_instance_ids) &&
        value.error_category === null &&
        isEmptyArray(value.errors) &&
        typeof value.message === "string" &&
        value.message.length > 0
      ) {
        return { ok: true, value: value as unknown as CaptureRouteResponse };
      }
      return { ok: false };
    case "search_limit_exceeded":
      if (
        fixedIdentities(value) &&
        value.target === null &&
        isEmptyArray(value.steps) &&
        isEmptyArray(value.capture_requirements) &&
        value.cost === null &&
        isEmptyArray(value.reachable_states) &&
        isEmptyArray(value.unknown_instance_ids) &&
        value.error_category === null &&
        isEmptyArray(value.errors) &&
        typeof value.message === "string" &&
        value.message.length > 0
      ) {
        return { ok: true, value: value as unknown as CaptureRouteResponse };
      }
      return { ok: false };
    case "invalid":
      if (
        ((value.content_sha256 === null &&
          value.gender_data_content_sha256 === null) ||
          fixedIdentities(value)) &&
        value.target === null &&
        isEmptyArray(value.steps) &&
        isEmptyArray(value.capture_requirements) &&
        value.cost === null &&
        isEmptyArray(value.reachable_states) &&
        isEmptyArray(value.unknown_instance_ids) &&
        typeof value.error_category === "string" &&
        value.error_category.length > 0 &&
        Array.isArray(value.errors) &&
        value.errors.length > 0 &&
        typeof value.message === "string" &&
        value.message.length > 0
      ) {
        return {
          ok: true,
          value: value as unknown as CaptureInvalidResponse,
        };
      }
      return { ok: false };
    default:
      return { ok: false };
  }
}

function candidateEquals(
  requirement: CaptureRequirement,
  candidate: CaptureCandidate,
): boolean {
  return (
    requirement.candidate_id === candidate.candidate_id &&
    requirement.species_id === candidate.species_id &&
    requirement.gender === candidate.gender
  );
}

function stateKey(speciesId: string, gender: string): string {
  return `${speciesId}\u0000${gender}`;
}

function successUsesExactlyReportedRequirements(
  response: CaptureSuccessResponse,
  request: Readonly<CaptureRouteRequest>,
): boolean {
  const ownedStates = new Set(
    request.inventory
      .filter((item) => item.gender !== "unknown")
      .map((item) => stateKey(item.species_id, item.gender)),
  );
  const requirementsByState = new Map(
    response.capture_requirements.map((item) => [
      stateKey(item.species_id, item.gender),
      item.candidate_id,
    ]),
  );
  if (
    requirementsByState.size !== response.capture_requirements.length ||
    [...requirementsByState.keys()].some((key) => ownedStates.has(key))
  ) {
    return false;
  }

  const produced = new Map<string, number>();
  const usedRequirements = new Set<string>();
  function requireState(state: BreedingRouteState): boolean {
    const key = stateKey(state.species_id, state.gender);
    const producedGeneration = produced.get(key);
    if (producedGeneration !== undefined) {
      return state.generation_depth === producedGeneration;
    }
    if (ownedStates.has(key)) return state.generation_depth === 0;
    const candidateId = requirementsByState.get(key);
    if (candidateId === undefined || state.generation_depth !== 0) {
      return false;
    }
    usedRequirements.add(candidateId);
    return true;
  }

  for (const step of response.steps) {
    if (!requireState(step.parent_a) || !requireState(step.parent_b)) {
      return false;
    }
    const childKey = stateKey(step.child.species_id, step.child.gender);
    if (produced.has(childKey)) return false;
    produced.set(childKey, step.generation);
  }

  const targetKey = stateKey(
    response.target.species_id,
    response.target.gender,
  );
  if (response.steps.length === 0) {
    if (ownedStates.has(targetKey)) {
      return response.capture_requirements.length === 0;
    }
    const directCandidate = requirementsByState.get(targetKey);
    if (directCandidate === undefined) return false;
    usedRequirements.add(directCandidate);
  } else if (produced.get(targetKey) !== response.target.generation_depth) {
    return false;
  }
  return (
    usedRequirements.size === response.capture_requirements.length &&
    response.capture_requirements.every((item) =>
      usedRequirements.has(item.candidate_id),
    )
  );
}

export function captureResponseMatchesRequest(
  response: CaptureRouteResponse,
  request: Readonly<CaptureRouteRequest>,
): boolean {
  if (response.dataset_id !== request.dataset_id) return false;
  if (
    response.status === "success" ||
    response.status === "unreachable"
  ) {
    if (
      response.target.species_id !== request.target.species_id ||
      response.target.gender !== request.target.gender
    ) {
      return false;
    }
  }
  if (response.status === "success") {
    const candidates = new Map(
      request.capture_candidates.map((item) => [item.candidate_id, item]),
    );
    if (
      !response.capture_requirements.every((requirement) => {
        const submitted = candidates.get(requirement.candidate_id);
        return submitted !== undefined && candidateEquals(requirement, submitted);
      })
    ) {
      return false;
    }
    if (!successUsesExactlyReportedRequirements(response, request)) {
      return false;
    }
    const finalStep = response.steps.at(-1);
    if (
      finalStep !== undefined &&
      (finalStep.child.species_id !== request.target.species_id ||
        finalStep.child.gender !== request.target.gender)
    ) {
      return false;
    }
  }
  if (response.status === "gender_required") {
    const unknownIds = new Set(
      request.inventory
        .filter((item) => item.gender === "unknown")
        .map((item) => item.instance_id),
    );
    return response.unknown_instance_ids.every((id) => unknownIds.has(id));
  }
  return true;
}
