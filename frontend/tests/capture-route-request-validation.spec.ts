import { describe, expect, it } from "vitest";

import {
  createInitialCaptureRouteForm,
  validateAndBuildCaptureRouteRequest,
} from "../src/form/captureRouteRequest";

describe("capture route form validation", () => {
  it("builds a stable-ID-only exact request", () => {
    const form = createInitialCaptureRouteForm();
    form.targetSpeciesId = " anubis ";
    form.inventory.push({
      key: 1,
      instanceId: " lamball-m ",
      speciesId: " lamball ",
      gender: "male",
    });
    form.candidates.push({
      key: 2,
      candidateId: " anubis-f ",
      speciesId: " anubis ",
      gender: "female",
    });

    expect(validateAndBuildCaptureRouteRequest(form)).toEqual({
      ok: true,
      request: {
        dataset_id: "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47",
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
      },
    });
  });

  it("rejects ID collisions and duplicate candidate states", () => {
    const form = createInitialCaptureRouteForm();
    form.targetSpeciesId = "anubis";
    form.inventory.push({
      key: 1,
      instanceId: "shared-id",
      speciesId: "lamball",
      gender: "male",
    });
    form.candidates.push(
      {
        key: 2,
        candidateId: "shared-id",
        speciesId: "anubis",
        gender: "female",
      },
      {
        key: 3,
        candidateId: "other-id",
        speciesId: "anubis",
        gender: "female",
      },
    );

    const result = validateAndBuildCaptureRouteRequest(form);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.candidates[0]?.id).toContain("inventory row");
      expect(result.errors.candidates[1]?.speciesId).toContain(
        "duplicate capture candidate",
      );
    }
  });

  it("never silently omits blank rows", () => {
    const form = createInitialCaptureRouteForm();
    form.targetSpeciesId = "anubis";
    form.candidates.push({
      key: 1,
      candidateId: "",
      speciesId: "",
      gender: "female",
    });
    const result = validateAndBuildCaptureRouteRequest(form);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.candidates[0]).toMatchObject({
        id: expect.any(String),
        speciesId: expect.any(String),
      });
    }
  });
});
