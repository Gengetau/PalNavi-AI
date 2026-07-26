import { describe, expect, it } from "vitest";

import {
  decodeBreedingResponse,
  responseMatchesRequest,
} from "../src/api/breedingRuntimeValidation";
import {
  breedingGenderRequired,
  breedingInvalid,
  breedingRequest,
  breedingState,
  breedingSuccess,
  breedingUnreachable,
  breedingZeroStepSuccess,
} from "./breeding-fixtures";

const clone = <T>(value: T): T =>
  JSON.parse(JSON.stringify(value)) as T;

describe("breeding runtime validation", () => {
  it.each([
    breedingSuccess(),
    breedingZeroStepSuccess(),
    breedingGenderRequired(),
    breedingUnreachable(),
    breedingInvalid(),
  ])("accepts a complete canonical $status response", (response) => {
    expect(decodeBreedingResponse(response)).toEqual({
      ok: true,
      value: response,
    });
  });

  it("rejects unknown keys at response, state, step, cost, and issue boundaries", () => {
    const cases: unknown[] = [];

    const responseExtra = clone(breedingSuccess()) as unknown as Record<
      string,
      unknown
    >;
    responseExtra.extra = true;
    cases.push(responseExtra);

    const stateExtra = clone(breedingSuccess());
    (stateExtra.target as unknown as Record<string, unknown>).extra = true;
    cases.push(stateExtra);

    const stepExtra = clone(breedingSuccess());
    (
      stepExtra.steps[0] as unknown as Record<string, unknown>
    ).extra = true;
    cases.push(stepExtra);

    const costExtra = clone(breedingSuccess());
    (costExtra.cost as unknown as Record<string, unknown>).extra = true;
    cases.push(costExtra);

    const issueExtra = clone(breedingInvalid());
    (
      issueExtra.errors[0] as unknown as Record<string, unknown>
    ).extra = true;
    cases.push(issueExtra);

    for (const candidate of cases) {
      expect(decodeBreedingResponse(candidate).ok).toBe(false);
    }
  });

  it.each([
    ["dataset_id", "wrong-dataset"],
    ["content_sha256", "a".repeat(64)],
    ["gender_data_content_sha256", "b".repeat(64)],
  ] as const)("rejects mismatched accepted identity %s", (key, value) => {
    const response = clone(breedingSuccess()) as unknown as Record<
      string,
      unknown
    >;
    response[key] = value;
    expect(decodeBreedingResponse(response).ok).toBe(false);
  });

  it("rejects passive or IV claims and invalid identifiers", () => {
    const passive = clone(breedingSuccess());
    (
      passive.steps[0]!.child.required_passive_ids as unknown as string[]
    ).push("invented-passive");
    expect(decodeBreedingResponse(passive).ok).toBe(false);

    const iv = clone(breedingSuccess());
    (
      iv.steps[0]!.child.required_iv_constraints as unknown as string[]
    ).push("invented-iv");
    expect(decodeBreedingResponse(iv).ok).toBe(false);

    const species = clone(breedingSuccess());
    species.target.species_id = "Bad Species";
    expect(decodeBreedingResponse(species).ok).toBe(false);
  });

  it("rejects unordered, discontinuous, duplicated, or inconsistent steps", () => {
    const wrongOrder = clone(breedingSuccess());
    wrongOrder.steps[1]!.order = 3;
    expect(decodeBreedingResponse(wrongOrder).ok).toBe(false);

    const wrongGeneration = clone(breedingSuccess());
    wrongGeneration.steps[1]!.child.generation_depth = 1;
    expect(decodeBreedingResponse(wrongGeneration).ok).toBe(false);

    const sameGender = clone(breedingSuccess());
    sameGender.steps[0]!.parent_b.gender = "male";
    expect(decodeBreedingResponse(sameGender).ok).toBe(false);

    const missingProducer = clone(breedingSuccess());
    missingProducer.steps[1]!.parent_a.species_id = "other_pal";
    expect(decodeBreedingResponse(missingProducer).ok).toBe(false);

    const duplicateChild = clone(breedingSuccess());
    duplicateChild.steps[1]!.child = clone(
      duplicateChild.steps[0]!.child,
    );
    duplicateChild.steps[1]!.generation =
      duplicateChild.steps[0]!.generation;
    expect(decodeBreedingResponse(duplicateChild).ok).toBe(false);
  });

  it("rejects probability claims and mismatched cost or final target", () => {
    const probability = clone(breedingSuccess());
    (
      probability.cost as unknown as {
        probability_dependent_cost_available: boolean;
      }
    ).probability_dependent_cost_available = true;
    expect(decodeBreedingResponse(probability).ok).toBe(false);

    const expectedAttempts = clone(breedingSuccess());
    (
      expectedAttempts.cost as unknown as { expected_attempts: number | null }
    ).expected_attempts = 7;
    expect(decodeBreedingResponse(expectedAttempts).ok).toBe(false);

    const cost = clone(breedingSuccess());
    cost.cost.breeding_steps = 1;
    expect(decodeBreedingResponse(cost).ok).toBe(false);

    const target = clone(breedingSuccess());
    target.target.gender = "male";
    expect(decodeBreedingResponse(target).ok).toBe(false);
  });

  it("requires bounded unique IDs for gender_required", () => {
    const empty = clone(breedingGenderRequired());
    empty.unknown_instance_ids = [];
    expect(decodeBreedingResponse(empty).ok).toBe(false);

    const duplicate = clone(breedingGenderRequired());
    duplicate.unknown_instance_ids = [
      "katress-unknown",
      "katress-unknown",
    ];
    expect(decodeBreedingResponse(duplicate).ok).toBe(false);
  });

  it("requires exact unknown IDs and an owned target for zero-step success", () => {
    expect(
      responseMatchesRequest(
        breedingGenderRequired(),
        breedingRequest({
          inventory: [
            {
              instance_id: "different-unknown",
              species_id: "katress",
              gender: "unknown",
            },
          ],
        }),
      ),
    ).toBe(false);

    expect(
      responseMatchesRequest(
        breedingZeroStepSuccess(),
        breedingRequest({ inventory: [] }),
      ),
    ).toBe(false);
    expect(
      responseMatchesRequest(
        breedingZeroStepSuccess(),
        breedingRequest({
          inventory: [
            {
              instance_id: "owned-target",
              species_id: "wixen_noct",
              gender: "female",
            },
          ],
        }),
      ),
    ).toBe(true);
  });

  it("accepts the canonical request-bound unreachable boundary", () => {
    expect(
      responseMatchesRequest(breedingUnreachable(), breedingRequest()),
    ).toBe(true);
  });

  it("rejects an unreachable response with an unowned generation-zero state", () => {
    const response = breedingUnreachable();
    response.reachable_states.push(
      breedingState({ species_id: "lamball", gender: "male" }),
    );

    expect(responseMatchesRequest(response, breedingRequest())).toBe(false);
  });

  it("rejects an unreachable response missing an owned generation-zero state", () => {
    const response = breedingUnreachable();
    response.reachable_states.pop();

    expect(responseMatchesRequest(response, breedingRequest())).toBe(false);
  });

  it("binds target and generated parents to the submitted request", () => {
    const success = breedingSuccess();
    expect(responseMatchesRequest(success, breedingRequest())).toBe(true);

    const wrongTarget = clone(success);
    wrongTarget.target.species_id = "dumud";
    expect(responseMatchesRequest(wrongTarget, breedingRequest())).toBe(false);

    const unavailableParent = clone(success);
    unavailableParent.steps[0]!.parent_a.species_id = "not_owned";
    expect(
      responseMatchesRequest(unavailableParent, breedingRequest()),
    ).toBe(false);
  });
});
