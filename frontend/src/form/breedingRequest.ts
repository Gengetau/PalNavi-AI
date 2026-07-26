import {
  BREEDING_DATASET_ID,
  type BreedingRequest,
  type ConcreteGender,
  type InventoryGender,
} from "../api/breedingContract";

export interface BreedingInventoryRowModel {
  key: number;
  instanceId: string;
  speciesId: string;
  gender: InventoryGender;
}

export interface BreedingFormModel {
  targetSpeciesId: string;
  targetGender: ConcreteGender;
  inventory: BreedingInventoryRowModel[];
}

export interface BreedingRowErrors {
  instanceId?: string;
  speciesId?: string;
}

export interface BreedingFieldErrors {
  targetSpeciesId?: string;
  inventoryLimit?: string;
  rows: Record<number, BreedingRowErrors>;
}

export type BreedingRequestValidation =
  | { ok: true; request: BreedingRequest }
  | { ok: false; errors: BreedingFieldErrors };

export const MAX_INVENTORY_ROWS = 299;
export const SPECIES_ID_PATTERN = /^[a-z][a-z0-9_]{0,63}$/;
export const INSTANCE_ID_PATTERN =
  /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export function createInitialBreedingForm(): BreedingFormModel {
  return {
    targetSpeciesId: "",
    targetGender: "female",
    inventory: [],
  };
}

export function validateAndBuildBreedingRequest(
  model: Readonly<BreedingFormModel>,
): BreedingRequestValidation {
  const errors: BreedingFieldErrors = { rows: {} };
  const targetSpeciesId = model.targetSpeciesId.trim();
  if (SPECIES_ID_PATTERN.exec(targetSpeciesId)?.[0] !== targetSpeciesId) {
    errors.targetSpeciesId =
      "Enter a stable species ID using lowercase letters, numbers, and underscores.";
  }
  if (model.inventory.length > MAX_INVENTORY_ROWS) {
    errors.inventoryLimit = `Use no more than ${MAX_INVENTORY_ROWS} inventory rows.`;
  }

  const inventory: BreedingRequest["inventory"] = [];
  const firstRowByInstance = new Map<string, number>();
  for (const [index, row] of model.inventory.entries()) {
    const instanceId = row.instanceId.trim();
    const speciesId = row.speciesId.trim();
    const rowErrors: BreedingRowErrors = {};
    if (INSTANCE_ID_PATTERN.exec(instanceId)?.[0] !== instanceId) {
      rowErrors.instanceId =
        "Enter a stable instance ID using letters, numbers, dots, underscores, colons, or hyphens.";
    } else {
      const firstIndex = firstRowByInstance.get(instanceId);
      if (firstIndex !== undefined) {
        rowErrors.instanceId = `Instance ID duplicates inventory row ${firstIndex + 1}.`;
      } else {
        firstRowByInstance.set(instanceId, index);
      }
    }
    if (SPECIES_ID_PATTERN.exec(speciesId)?.[0] !== speciesId) {
      rowErrors.speciesId =
        "Enter a stable species ID using lowercase letters, numbers, and underscores.";
    }
    if (Object.keys(rowErrors).length > 0) {
      errors.rows[index] = rowErrors;
    }
    inventory.push({
      instance_id: instanceId,
      species_id: speciesId,
      gender: row.gender,
    });
  }

  if (
    errors.targetSpeciesId !== undefined ||
    errors.inventoryLimit !== undefined ||
    Object.keys(errors.rows).length > 0
  ) {
    return { ok: false, errors };
  }
  return {
    ok: true,
    request: {
      dataset_id: BREEDING_DATASET_ID,
      target: {
        species_id: targetSpeciesId,
        gender: model.targetGender,
      },
      inventory,
      objective: "minimum_generations",
    },
  };
}
