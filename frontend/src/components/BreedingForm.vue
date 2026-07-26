<script setup lang="ts">
import { computed, nextTick, reactive, ref } from "vue";

import {
  BREEDING_DATASET_ID,
  type BreedingRequest,
} from "../api/breedingContract";
import {
  createInitialBreedingForm,
  MAX_INVENTORY_ROWS,
  type BreedingFieldErrors,
  type BreedingRowErrors,
  validateAndBuildBreedingRequest,
} from "../form/breedingRequest";

const emit = defineEmits<{ submit: [request: BreedingRequest] }>();

const form = reactive(createInitialBreedingForm());
const errors = ref<BreedingFieldErrors>({ rows: {} });
const formElement = ref<HTMLFormElement | null>(null);
const targetInput = ref<HTMLInputElement | null>(null);
let nextRowKey = 1;

const errorEntries = computed(() => {
  const entries: string[] = [];
  if (errors.value.targetSpeciesId) {
    entries.push(`Target: ${errors.value.targetSpeciesId}`);
  }
  if (errors.value.inventoryLimit) {
    entries.push(errors.value.inventoryLimit);
  }
  for (const [index, rowErrors] of Object.entries(errors.value.rows)) {
    if (rowErrors.instanceId) {
      entries.push(`Inventory row ${Number(index) + 1}: ${rowErrors.instanceId}`);
    }
    if (rowErrors.speciesId) {
      entries.push(`Inventory row ${Number(index) + 1}: ${rowErrors.speciesId}`);
    }
  }
  return entries;
});

function addRow(): void {
  if (form.inventory.length >= MAX_INVENTORY_ROWS) {
    errors.value = {
      ...errors.value,
      inventoryLimit: `Use no more than ${MAX_INVENTORY_ROWS} inventory rows.`,
    };
    return;
  }
  form.inventory.push({
    key: nextRowKey++,
    instanceId: "",
    speciesId: "",
    gender: "unknown",
  });
  errors.value = { rows: {} };
}

function removeRow(index: number): void {
  form.inventory.splice(index, 1);
  errors.value = { rows: {} };
}

function clearTargetError(): void {
  if (errors.value.targetSpeciesId === undefined) {
    return;
  }
  const next = { ...errors.value };
  delete next.targetSpeciesId;
  errors.value = next;
}

function clearRowError(
  index: number,
  field: keyof BreedingRowErrors,
): void {
  const rowErrors = errors.value.rows[index];
  if (rowErrors?.[field] === undefined) {
    return;
  }
  const nextRow = { ...rowErrors };
  delete nextRow[field];
  const rows = { ...errors.value.rows };
  if (Object.keys(nextRow).length === 0) {
    delete rows[index];
  } else {
    rows[index] = nextRow;
  }
  errors.value = { ...errors.value, rows };
}

function rowDescribedBy(
  index: number,
  field: keyof BreedingRowErrors,
  helpId: string,
): string {
  return errors.value.rows[index]?.[field]
    ? `${helpId} inventory-${index}-${field}-error`
    : helpId;
}

async function submit(): Promise<void> {
  const result = validateAndBuildBreedingRequest(form);
  if (!result.ok) {
    errors.value = result.errors;
    await nextTick();
    if (result.errors.targetSpeciesId) {
      targetInput.value?.focus();
      return;
    }
    const firstRowIndex = Object.keys(result.errors.rows)
      .map(Number)
      .sort((left, right) => left - right)[0];
    if (firstRowIndex !== undefined) {
      const rowErrors = result.errors.rows[firstRowIndex];
      const field = rowErrors?.instanceId ? "instanceId" : "speciesId";
      formElement.value
        ?.querySelector<HTMLElement>(
          `[data-row-index="${firstRowIndex}"][data-field="${field}"]`,
        )
        ?.focus();
    }
    return;
  }
  errors.value = { rows: {} };
  emit("submit", result.request);
}
</script>

<template>
  <form
    ref="formElement"
    class="breeding-form"
    aria-labelledby="breeding-form-title"
    novalidate
    @submit.prevent="submit"
  >
    <div class="panel-heading">
      <p class="eyebrow">VERIFIED ROUTE CONSOLE</p>
      <h2 id="breeding-form-title">Plan from owned Pals</h2>
      <p>
        Enter stable internal IDs manually. This alpha does not read or modify a
        save file.
      </p>
    </div>

    <div class="dataset-scope">
      <strong>Fixed production dataset</strong>
      <code>{{ BREEDING_DATASET_ID }}</code>
    </div>

    <div
      v-if="errorEntries.length"
      class="error-summary"
      role="alert"
      aria-label="Breeding form errors"
    >
      <strong>Check the highlighted fields.</strong>
      <ul>
        <li v-for="(message, index) in errorEntries" :key="index">
          {{ message }}
        </li>
      </ul>
    </div>

    <fieldset>
      <legend>Target</legend>
      <div class="field">
        <label for="breeding-target-species">Target species ID</label>
        <input
          id="breeding-target-species"
          ref="targetInput"
          v-model="form.targetSpeciesId"
          name="target-species-id"
          type="text"
          maxlength="64"
          placeholder="wixen_noct"
          :aria-describedby="
            errors.targetSpeciesId
              ? 'target-species-help target-species-error'
              : 'target-species-help'
          "
          :aria-invalid="Boolean(errors.targetSpeciesId)"
          @input="clearTargetError"
        />
        <p id="target-species-help" class="field-help">
          Lowercase stable ID; display names are not accepted in this alpha.
        </p>
        <p
          v-if="errors.targetSpeciesId"
          id="target-species-error"
          class="field-error"
        >
          {{ errors.targetSpeciesId }}
        </p>
      </div>

      <div class="field">
        <label for="breeding-target-gender">Target gender</label>
        <select
          id="breeding-target-gender"
          v-model="form.targetGender"
          name="target-gender"
        >
          <option value="female">Female</option>
          <option value="male">Male</option>
        </select>
      </div>
    </fieldset>

    <fieldset>
      <legend>Owned inventory · {{ form.inventory.length }} / 299</legend>
      <p class="field-help">
        Every added row is submitted. Blank or incomplete rows are never
        silently omitted.
      </p>

      <div
        v-for="(row, index) in form.inventory"
        :key="row.key"
        class="inventory-row"
      >
        <div class="inventory-row-heading">
          <h3>Inventory row {{ index + 1 }}</h3>
          <button
            type="button"
            class="button button-compact"
            :aria-label="`Remove inventory row ${index + 1}`"
            @click="removeRow(index)"
          >
            Remove
          </button>
        </div>

        <div class="field">
          <label :for="`inventory-${row.key}-instance`">Instance ID</label>
          <input
            :id="`inventory-${row.key}-instance`"
            v-model="row.instanceId"
            :name="`inventory-${index}-instance-id`"
            type="text"
            maxlength="128"
            placeholder="dumud-1"
            :data-row-index="index"
            data-field="instanceId"
            :aria-describedby="
              rowDescribedBy(
                index,
                'instanceId',
                `inventory-${row.key}-instance-help`,
              )
            "
            :aria-invalid="Boolean(errors.rows[index]?.instanceId)"
            @input="clearRowError(index, 'instanceId')"
          />
          <p
            :id="`inventory-${row.key}-instance-help`"
            class="field-help"
          >
            Stable and unique within this request.
          </p>
          <p
            v-if="errors.rows[index]?.instanceId"
            :id="`inventory-${index}-instanceId-error`"
            class="field-error"
          >
            {{ errors.rows[index]?.instanceId }}
          </p>
        </div>

        <div class="inventory-row-fields">
          <div class="field">
            <label :for="`inventory-${row.key}-species`">Species ID</label>
            <input
              :id="`inventory-${row.key}-species`"
              v-model="row.speciesId"
              :name="`inventory-${index}-species-id`"
              type="text"
              maxlength="64"
              placeholder="dumud"
              :data-row-index="index"
              data-field="speciesId"
              :aria-describedby="
                rowDescribedBy(
                  index,
                  'speciesId',
                  `inventory-${row.key}-species-help`,
                )
              "
              :aria-invalid="Boolean(errors.rows[index]?.speciesId)"
              @input="clearRowError(index, 'speciesId')"
            />
            <p
              :id="`inventory-${row.key}-species-help`"
              class="field-help"
            >
              Stable lowercase internal ID.
            </p>
            <p
              v-if="errors.rows[index]?.speciesId"
              :id="`inventory-${index}-speciesId-error`"
              class="field-error"
            >
              {{ errors.rows[index]?.speciesId }}
            </p>
          </div>

          <div class="field">
            <label :for="`inventory-${row.key}-gender`">Gender</label>
            <select
              :id="`inventory-${row.key}-gender`"
              v-model="row.gender"
              :name="`inventory-${index}-gender`"
            >
              <option value="unknown">Unknown</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </div>
        </div>
      </div>

      <button
        type="button"
        class="button"
        :disabled="form.inventory.length >= MAX_INVENTORY_ROWS"
        @click="addRow"
      >
        Add owned Pal
      </button>
    </fieldset>

    <div class="objective-note">
      <span>Objective</span>
      <strong>Minimum generations</strong>
    </div>

    <button type="submit" class="button button-primary">
      Plan verified route
    </button>
  </form>
</template>
