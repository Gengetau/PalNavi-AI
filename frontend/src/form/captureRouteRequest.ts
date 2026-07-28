import {
  CAPTURE_ROUTE_DATASET_ID,
  type CaptureRouteRequest,
  type ConcreteGender,
} from "../api/captureRouteContract";
import type { InventoryGender } from "../api/breedingContract";

export interface CaptureOwnedRowModel {
  key: number;
  instanceId: string;
  speciesId: string;
  gender: InventoryGender;
}

export interface CaptureCandidateRowModel {
  key: number;
  candidateId: string;
  speciesId: string;
  gender: ConcreteGender;
}

export interface CaptureRouteFormModel {
  targetSpeciesId: string;
  targetGender: ConcreteGender;
  inventory: CaptureOwnedRowModel[];
  candidates: CaptureCandidateRowModel[];
}

export interface CaptureRowErrors {
  id?: string;
  speciesId?: string;
}

export interface CaptureRouteFieldErrors {
  targetSpeciesId?: string;
  inventoryLimit?: string;
  candidateLimit?: string;
  inventory: Record<number, CaptureRowErrors>;
  candidates: Record<number, CaptureRowErrors>;
}

export type CaptureRouteRequestValidation =
  | { ok: true; request: CaptureRouteRequest }
  | { ok: false; errors: CaptureRouteFieldErrors };

export const MAX_CAPTURE_INVENTORY_ROWS = 299;
export const MAX_CAPTURE_CANDIDATES = 16;
const SPECIES_ID = /^[a-z][a-z0-9_]{0,63}$/;
const INSTANCE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SPECIES_MESSAGE =
  "Enter a stable species ID using lowercase letters, numbers, and underscores.";
const ID_MESSAGE =
  "Enter a stable ID using letters, numbers, dots, underscores, colons, or hyphens.";

export function createInitialCaptureRouteForm(): CaptureRouteFormModel {
  return {
    targetSpeciesId: "",
    targetGender: "female",
    inventory: [],
    candidates: [],
  };
}

export function validateAndBuildCaptureRouteRequest(
  model: Readonly<CaptureRouteFormModel>,
): CaptureRouteRequestValidation {
  const errors: CaptureRouteFieldErrors = {
    inventory: {},
    candidates: {},
  };
  const targetSpeciesId = model.targetSpeciesId.trim();
  if (SPECIES_ID.exec(targetSpeciesId)?.[0] !== targetSpeciesId) {
    errors.targetSpeciesId = SPECIES_MESSAGE;
  }
  if (model.inventory.length > MAX_CAPTURE_INVENTORY_ROWS) {
    errors.inventoryLimit = `Use no more than ${MAX_CAPTURE_INVENTORY_ROWS} inventory rows.`;
  }
  if (model.candidates.length > MAX_CAPTURE_CANDIDATES) {
    errors.candidateLimit = `Use no more than ${MAX_CAPTURE_CANDIDATES} capture candidates.`;
  }

  const allIds = new Map<string, string>();
  const inventory: CaptureRouteRequest["inventory"] = [];
  for (const [index, row] of model.inventory.entries()) {
    const instanceId = row.instanceId.trim();
    const speciesId = row.speciesId.trim();
    const rowErrors: CaptureRowErrors = {};
    if (INSTANCE_ID.exec(instanceId)?.[0] !== instanceId) {
      rowErrors.id = ID_MESSAGE;
    } else if (allIds.has(instanceId)) {
      rowErrors.id = `ID duplicates ${allIds.get(instanceId)}.`;
    } else {
      allIds.set(instanceId, `inventory row ${index + 1}`);
    }
    if (SPECIES_ID.exec(speciesId)?.[0] !== speciesId) {
      rowErrors.speciesId = SPECIES_MESSAGE;
    }
    if (Object.keys(rowErrors).length > 0) {
      errors.inventory[index] = rowErrors;
    }
    inventory.push({
      instance_id: instanceId,
      species_id: speciesId,
      gender: row.gender,
    });
  }

  const candidateStates = new Map<string, number>();
  const captureCandidates: CaptureRouteRequest["capture_candidates"] = [];
  for (const [index, row] of model.candidates.entries()) {
    const candidateId = row.candidateId.trim();
    const speciesId = row.speciesId.trim();
    const rowErrors: CaptureRowErrors = {};
    if (INSTANCE_ID.exec(candidateId)?.[0] !== candidateId) {
      rowErrors.id = ID_MESSAGE;
    } else if (allIds.has(candidateId)) {
      rowErrors.id = `ID duplicates ${allIds.get(candidateId)}.`;
    } else {
      allIds.set(candidateId, `capture candidate ${index + 1}`);
    }
    if (SPECIES_ID.exec(speciesId)?.[0] !== speciesId) {
      rowErrors.speciesId = SPECIES_MESSAGE;
    } else {
      const state = `${speciesId}\u0000${row.gender}`;
      const firstIndex = candidateStates.get(state);
      if (firstIndex !== undefined) {
        rowErrors.speciesId =
          `Species and gender duplicate capture candidate ${firstIndex + 1}.`;
      } else {
        candidateStates.set(state, index);
      }
    }
    if (Object.keys(rowErrors).length > 0) {
      errors.candidates[index] = rowErrors;
    }
    captureCandidates.push({
      candidate_id: candidateId,
      species_id: speciesId,
      gender: row.gender,
    });
  }

  if (
    errors.targetSpeciesId !== undefined ||
    errors.inventoryLimit !== undefined ||
    errors.candidateLimit !== undefined ||
    Object.keys(errors.inventory).length > 0 ||
    Object.keys(errors.candidates).length > 0
  ) {
    return { ok: false, errors };
  }
  return {
    ok: true,
    request: {
      dataset_id: CAPTURE_ROUTE_DATASET_ID,
      target: {
        species_id: targetSpeciesId,
        gender: model.targetGender,
      },
      inventory,
      capture_candidates: captureCandidates,
      objective: "minimum_new_captures",
    },
  };
}
