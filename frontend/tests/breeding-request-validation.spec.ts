import { describe, expect, it } from "vitest";

import {
  createInitialBreedingForm,
  type BreedingFormModel,
  validateAndBuildBreedingRequest,
} from "../src/form/breedingRequest";
import goldenContracts from "./golden/knowledge-contracts.json";

function valid(
  overrides: Partial<BreedingFormModel> = {},
): BreedingFormModel {
  return {
    targetSpeciesId: "wixen_noct",
    targetGender: "female",
    inventory: [
      {
        key: 1,
        instanceId: "dumud-1",
        speciesId: "dumud",
        gender: "male",
      },
    ],
    ...overrides,
  };
}

describe("breeding request validation", () => {
  it("starts with a fixed target gender and zero inventory rows", () => {
    expect(createInitialBreedingForm()).toEqual({
      targetSpeciesId: "",
      targetGender: "female",
      inventory: [],
    });
  });

  it("builds the exact fixed production request and trims boundaries", () => {
    expect(
      validateAndBuildBreedingRequest(
        valid({
          targetSpeciesId: "  wixen_noct ",
          inventory: [
            {
              key: 1,
              instanceId: " dumud-1 ",
              speciesId: " dumud ",
              gender: "male",
            },
          ],
        }),
      ),
    ).toEqual({
      ok: true,
      request: {
        dataset_id:
          "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47",
        target: { species_id: "wixen_noct", gender: "female" },
        inventory: [
          {
            instance_id: "dumud-1",
            species_id: "dumud",
            gender: "male",
          },
        ],
        objective: "minimum_generations",
      },
    });
  });

  it("serializes the accepted backend-owned golden request", () => {
    const result = validateAndBuildBreedingRequest(
      valid({
        inventory: goldenContracts.gender_route_request.inventory.map(
          (item, index) => ({
            key: index + 1,
            instanceId: item.instance_id,
            speciesId: item.species_id,
            gender: item.gender as "male" | "female" | "unknown",
          }),
        ),
      }),
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.request).toEqual(
        goldenContracts.gender_route_request,
      );
    }
  });

  it("allows an explicit zero-row inventory", () => {
    const result = validateAndBuildBreedingRequest(valid({ inventory: [] }));
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.request.inventory).toEqual([]);
    }
  });

  it.each([
    "",
    "Wixen",
    "1wixen",
    "wixen-noct",
    "wixen noct",
    `a${"b".repeat(64)}`,
  ])("rejects invalid target species ID %j", (targetSpeciesId) => {
    const result = validateAndBuildBreedingRequest(valid({ targetSpeciesId }));
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.targetSpeciesId).toBeDefined();
    }
  });

  it.each(["", "-first", "space id", "bad/id", "x".repeat(129)])(
    "rejects invalid instance ID %j",
    (instanceId) => {
      const model = valid();
      model.inventory[0]!.instanceId = instanceId;
      const result = validateAndBuildBreedingRequest(model);
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.errors.rows[0]?.instanceId).toBeDefined();
      }
    },
  );

  it("rejects every blank field in an added row instead of omitting it", () => {
    const result = validateAndBuildBreedingRequest(
      valid({
        inventory: [
          {
            key: 1,
            instanceId: "",
            speciesId: "",
            gender: "unknown",
          },
        ],
      }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.rows[0]).toEqual({
        instanceId: expect.any(String),
        speciesId: expect.any(String),
      });
    }
  });

  it("rejects duplicate instance IDs locally", () => {
    const result = validateAndBuildBreedingRequest(
      valid({
        inventory: [
          {
            key: 1,
            instanceId: "duplicate",
            speciesId: "dumud",
            gender: "male",
          },
          {
            key: 2,
            instanceId: "duplicate",
            speciesId: "wixen",
            gender: "female",
          },
        ],
      }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.rows[1]?.instanceId).toContain("row 1");
    }
  });

  it("rejects inventory overflow", () => {
    const inventory = Array.from({ length: 300 }, (_, index) => ({
      key: index,
      instanceId: `pal-${index}`,
      speciesId: "dumud",
      gender: "male" as const,
    }));
    const result = validateAndBuildBreedingRequest(valid({ inventory }));
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.inventoryLimit).toContain("299");
    }
  });
});
