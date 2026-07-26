import {
  BREEDING_CONTENT_SHA256,
  BREEDING_DATASET_ID,
  BREEDING_GENDER_CONTENT_SHA256,
  type BreedingInvalidResponse,
  type BreedingRequest,
  type BreedingResponse,
  type BreedingResultKind,
  type BreedingRouteCost,
  type BreedingRouteState,
  type BreedingRouteStep,
  type BreedingValidationIssue,
  type ConcreteGender,
} from "./breedingContract";

export type BreedingDecodeResult =
  | { ok: true; value: BreedingResponse }
  | { ok: false; issue: string };

type UnknownRecord = Record<string, unknown>;

const RESPONSE_KEYS = [
  "status",
  "dataset_id",
  "content_sha256",
  "gender_data_content_sha256",
  "target",
  "steps",
  "cost",
  "reachable_states",
  "unknown_instance_ids",
  "error_category",
  "errors",
  "message",
] as const;
const STATE_KEYS = [
  "species_id",
  "gender",
  "required_passive_ids",
  "required_iv_constraints",
  "generation_depth",
] as const;
const STEP_KEYS = [
  "order",
  "generation",
  "parent_a",
  "parent_b",
  "child",
  "result_kind",
  "source_record_hash",
] as const;
const COST_KEYS = [
  "generations",
  "breeding_steps",
  "probability_dependent_cost_available",
  "expected_attempts",
] as const;
const ISSUE_KEYS = ["code", "field", "message"] as const;
const RESULT_KINDS: readonly BreedingResultKind[] = [
  "same_species",
  "ordinary_power",
  "fixed_special",
  "gender_directed",
];
const SPECIES_PATTERN = /^[a-z][a-z0-9_]{0,63}$/;
const INSTANCE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SHA256_PATTERN = /^[a-f0-9]{64}$/;

const pass = (value: BreedingResponse): BreedingDecodeResult => ({
  ok: true,
  value,
});
const fail = (issue: string): BreedingDecodeResult => ({ ok: false, issue });
const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isConcreteGender = (value: unknown): value is ConcreteGender =>
  value === "male" || value === "female";
const safeIntegerBetween = (
  value: unknown,
  minimum: number,
  maximum: number,
): value is number =>
  typeof value === "number" &&
  Number.isSafeInteger(value) &&
  value >= minimum &&
  value <= maximum;

function hasExactKeys(
  value: UnknownRecord,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === expected.length &&
    keys.every((key) => expected.includes(key))
  );
}

function boundedString(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    [...value].length <= maximum
  );
}

function decodeState(value: unknown): BreedingRouteState | null {
  if (!isRecord(value) || !hasExactKeys(value, STATE_KEYS)) {
    return null;
  }
  if (
    typeof value.species_id !== "string" ||
    SPECIES_PATTERN.exec(value.species_id)?.[0] !== value.species_id ||
    !isConcreteGender(value.gender) ||
    !Array.isArray(value.required_passive_ids) ||
    value.required_passive_ids.length !== 0 ||
    !Array.isArray(value.required_iv_constraints) ||
    value.required_iv_constraints.length !== 0 ||
    !safeIntegerBetween(value.generation_depth, 0, 299)
  ) {
    return null;
  }
  return {
    species_id: value.species_id,
    gender: value.gender,
    required_passive_ids: [],
    required_iv_constraints: [],
    generation_depth: value.generation_depth,
  };
}

function decodeStates(
  value: unknown,
  maximum: number,
): BreedingRouteState[] | null {
  if (!Array.isArray(value) || value.length > maximum) {
    return null;
  }
  const states: BreedingRouteState[] = [];
  const identities = new Set<string>();
  for (const candidate of value) {
    const state = decodeState(candidate);
    if (state === null) {
      return null;
    }
    const identity = `${state.species_id}:${state.gender}:${state.generation_depth}`;
    if (identities.has(identity)) {
      return null;
    }
    identities.add(identity);
    states.push(state);
  }
  return states;
}

function decodeStep(value: unknown): BreedingRouteStep | null {
  if (!isRecord(value) || !hasExactKeys(value, STEP_KEYS)) {
    return null;
  }
  const parentA = decodeState(value.parent_a);
  const parentB = decodeState(value.parent_b);
  const child = decodeState(value.child);
  if (
    !safeIntegerBetween(value.order, 1, 299) ||
    !safeIntegerBetween(value.generation, 1, 299) ||
    parentA === null ||
    parentB === null ||
    child === null ||
    parentA.gender === parentB.gender ||
    child.generation_depth !== value.generation ||
    value.generation !==
      Math.max(parentA.generation_depth, parentB.generation_depth) + 1 ||
    parentA.generation_depth >= value.generation ||
    parentB.generation_depth >= value.generation ||
    typeof value.result_kind !== "string" ||
    !RESULT_KINDS.includes(value.result_kind as BreedingResultKind) ||
    typeof value.source_record_hash !== "string" ||
    !SHA256_PATTERN.test(value.source_record_hash)
  ) {
    return null;
  }
  return {
    order: value.order,
    generation: value.generation,
    parent_a: parentA,
    parent_b: parentB,
    child,
    result_kind: value.result_kind as BreedingResultKind,
    source_record_hash: value.source_record_hash,
  };
}

function sameState(
  left: BreedingRouteState,
  right: BreedingRouteState,
): boolean {
  return (
    left.species_id === right.species_id &&
    left.gender === right.gender &&
    left.generation_depth === right.generation_depth
  );
}

function decodeSteps(value: unknown): BreedingRouteStep[] | null {
  if (!Array.isArray(value) || value.length > 299) {
    return null;
  }
  const steps: BreedingRouteStep[] = [];
  const produced = new Map<string, BreedingRouteState>();
  let previousGeneration = 0;
  for (const [index, candidate] of value.entries()) {
    const step = decodeStep(candidate);
    if (
      step === null ||
      step.order !== index + 1 ||
      step.generation < previousGeneration
    ) {
      return null;
    }
    for (const parent of [step.parent_a, step.parent_b]) {
      if (parent.generation_depth === 0) {
        continue;
      }
      const producer = produced.get(
        `${parent.species_id}:${parent.gender}:${parent.generation_depth}`,
      );
      if (producer === undefined || !sameState(parent, producer)) {
        return null;
      }
    }
    const childIdentity = `${step.child.species_id}:${step.child.gender}:${step.child.generation_depth}`;
    if (produced.has(childIdentity)) {
      return null;
    }
    produced.set(childIdentity, step.child);
    steps.push(step);
    previousGeneration = step.generation;
  }
  return steps;
}

function decodeCost(value: unknown): BreedingRouteCost | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, COST_KEYS) ||
    !safeIntegerBetween(value.generations, 0, 299) ||
    !safeIntegerBetween(value.breeding_steps, 0, 299) ||
    value.probability_dependent_cost_available !== false ||
    value.expected_attempts !== null
  ) {
    return null;
  }
  return {
    generations: value.generations,
    breeding_steps: value.breeding_steps,
    probability_dependent_cost_available: false,
    expected_attempts: null,
  };
}

function decodeIssues(value: unknown): BreedingValidationIssue[] | null {
  if (!Array.isArray(value) || value.length > 64) {
    return null;
  }
  const issues: BreedingValidationIssue[] = [];
  for (const candidate of value) {
    if (
      !isRecord(candidate) ||
      !hasExactKeys(candidate, ISSUE_KEYS) ||
      !boundedString(candidate.code, 128) ||
      !boundedString(candidate.field, 256) ||
      !boundedString(candidate.message, 1_000)
    ) {
      return null;
    }
    issues.push({
      code: candidate.code,
      field: candidate.field,
      message: candidate.message,
    });
  }
  return issues;
}

function exactIdentities(value: UnknownRecord): boolean {
  return (
    value.dataset_id === BREEDING_DATASET_ID &&
    value.content_sha256 === BREEDING_CONTENT_SHA256 &&
    value.gender_data_content_sha256 === BREEDING_GENDER_CONTENT_SHA256
  );
}

function nullOrExactIdentities(value: UnknownRecord): boolean {
  const main = value.content_sha256;
  const gender = value.gender_data_content_sha256;
  return (
    value.dataset_id === BREEDING_DATASET_ID &&
    ((main === null && gender === null) ||
      (main === BREEDING_CONTENT_SHA256 &&
        gender === BREEDING_GENDER_CONTENT_SHA256))
  );
}

function decodeInstanceIds(value: unknown): string[] | null {
  if (!Array.isArray(value) || value.length > 299) {
    return null;
  }
  const result: string[] = [];
  const seen = new Set<string>();
  for (const candidate of value) {
    if (
      typeof candidate !== "string" ||
      INSTANCE_PATTERN.exec(candidate)?.[0] !== candidate ||
      seen.has(candidate)
    ) {
      return null;
    }
    seen.add(candidate);
    result.push(candidate);
  }
  return result;
}

function validNullableMessage(value: unknown): value is string | null {
  return value === null || boundedString(value, 4_096);
}

export function decodeBreedingResponse(
  value: unknown,
): BreedingDecodeResult {
  if (!isRecord(value) || !hasExactKeys(value, RESPONSE_KEYS)) {
    return fail("breeding response keys are invalid");
  }
  const steps = decodeSteps(value.steps);
  const reachableStates = decodeStates(value.reachable_states, 598);
  const unknownInstanceIds = decodeInstanceIds(value.unknown_instance_ids);
  const errors = decodeIssues(value.errors);
  if (
    steps === null ||
    reachableStates === null ||
    unknownInstanceIds === null ||
    errors === null ||
    !validNullableMessage(value.message)
  ) {
    return fail("breeding response fields are invalid");
  }

  if (value.status === "success") {
    const target = decodeState(value.target);
    const cost = decodeCost(value.cost);
    if (
      !exactIdentities(value) ||
      target === null ||
      cost === null ||
      reachableStates.length !== 0 ||
      unknownInstanceIds.length !== 0 ||
      value.error_category !== null ||
      errors.length !== 0 ||
      value.message !== null ||
      cost.breeding_steps !== steps.length ||
      cost.generations !== target.generation_depth ||
      (steps.length === 0
        ? target.generation_depth !== 0
        : !sameState(steps[steps.length - 1]!.child, target))
    ) {
      return fail("breeding success is inconsistent");
    }
    return pass({
      status: "success",
      dataset_id: BREEDING_DATASET_ID,
      content_sha256: BREEDING_CONTENT_SHA256,
      gender_data_content_sha256: BREEDING_GENDER_CONTENT_SHA256,
      target,
      steps,
      cost,
      reachable_states: [],
      unknown_instance_ids: [],
      error_category: null,
      errors: [],
      message: null,
    });
  }

  if (value.status === "gender_required") {
    if (
      !exactIdentities(value) ||
      value.target !== null ||
      steps.length !== 0 ||
      value.cost !== null ||
      reachableStates.length !== 0 ||
      unknownInstanceIds.length === 0 ||
      value.error_category !== null ||
      errors.length !== 0 ||
      typeof value.message !== "string"
    ) {
      return fail("gender-required response is inconsistent");
    }
    return pass({
      status: "gender_required",
      dataset_id: BREEDING_DATASET_ID,
      content_sha256: BREEDING_CONTENT_SHA256,
      gender_data_content_sha256: BREEDING_GENDER_CONTENT_SHA256,
      target: null,
      steps: [],
      cost: null,
      reachable_states: [],
      unknown_instance_ids: unknownInstanceIds,
      error_category: null,
      errors: [],
      message: value.message,
    });
  }

  if (value.status === "unreachable") {
    const target = decodeState(value.target);
    if (
      !exactIdentities(value) ||
      target === null ||
      steps.length !== 0 ||
      value.cost !== null ||
      unknownInstanceIds.length !== 0 ||
      value.error_category !== null ||
      errors.length !== 0 ||
      typeof value.message !== "string"
    ) {
      return fail("unreachable response is inconsistent");
    }
    return pass({
      status: "unreachable",
      dataset_id: BREEDING_DATASET_ID,
      content_sha256: BREEDING_CONTENT_SHA256,
      gender_data_content_sha256: BREEDING_GENDER_CONTENT_SHA256,
      target,
      steps: [],
      cost: null,
      reachable_states: reachableStates,
      unknown_instance_ids: [],
      error_category: null,
      errors: [],
      message: value.message,
    });
  }

  if (value.status === "invalid") {
    if (
      !nullOrExactIdentities(value) ||
      value.target !== null ||
      steps.length !== 0 ||
      value.cost !== null ||
      reachableStates.length !== 0 ||
      unknownInstanceIds.length !== 0 ||
      !boundedString(value.error_category, 128) ||
      errors.length === 0 ||
      typeof value.message !== "string"
    ) {
      return fail("invalid product response is inconsistent");
    }
    const response: BreedingInvalidResponse = {
      status: "invalid",
      dataset_id: BREEDING_DATASET_ID,
      content_sha256:
        value.content_sha256 === BREEDING_CONTENT_SHA256
          ? BREEDING_CONTENT_SHA256
          : null,
      gender_data_content_sha256:
        value.gender_data_content_sha256 === BREEDING_GENDER_CONTENT_SHA256
          ? BREEDING_GENDER_CONTENT_SHA256
          : null,
      target: null,
      steps: [],
      cost: null,
      reachable_states: [],
      unknown_instance_ids: [],
      error_category: value.error_category,
      errors,
      message: value.message,
    };
    return pass(response);
  }
  return fail("breeding response status is invalid");
}

export function responseMatchesRequest(
  response: BreedingResponse,
  request: Readonly<BreedingRequest>,
): boolean {
  if (response.status === "gender_required") {
    const submittedUnknownIds = request.inventory
      .filter((item) => item.gender === "unknown")
      .map((item) => item.instance_id)
      .sort();
    return (
      submittedUnknownIds.length === response.unknown_instance_ids.length &&
      [...response.unknown_instance_ids]
        .sort()
        .every((id, index) => id === submittedUnknownIds[index])
    );
  }
  if (response.status === "invalid") {
    return true;
  }
  if (
    response.target.species_id !== request.target.species_id ||
    response.target.gender !== request.target.gender
  ) {
    return false;
  }
  if (response.status === "unreachable") {
    return true;
  }
  const owned = new Set(
    request.inventory
      .filter((item) => item.gender !== "unknown")
      .map((item) => `${item.species_id}:${item.gender}:0`),
  );
  if (
    response.steps.length === 0 &&
    !owned.has(
      `${response.target.species_id}:${response.target.gender}:0`,
    )
  ) {
    return false;
  }
  const produced = new Set<string>();
  for (const step of response.steps) {
    for (const parent of [step.parent_a, step.parent_b]) {
      const identity = `${parent.species_id}:${parent.gender}:${parent.generation_depth}`;
      if (
        (parent.generation_depth === 0 && !owned.has(identity)) ||
        (parent.generation_depth > 0 && !produced.has(identity))
      ) {
        return false;
      }
    }
    produced.add(
      `${step.child.species_id}:${step.child.gender}:${step.child.generation_depth}`,
    );
  }
  return true;
}
