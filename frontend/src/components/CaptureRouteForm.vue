<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from "vue";

import {
  CAPTURE_ACQUISITION_MESSAGE,
  CAPTURE_ROUTE_DATASET_ID,
  type CaptureRouteRequest,
} from "../api/captureRouteContract";
import {
  SPECIES_CATALOG_LOCALE_TAGS,
  type SpeciesCatalogClient,
  type SpeciesCatalogLocale,
  type SpeciesCatalogRecord,
} from "../api/breedingCatalogContract";
import { useSpeciesCatalog } from "../composables/useSpeciesCatalog";
import {
  createInitialCaptureRouteForm,
  MAX_CAPTURE_CANDIDATES,
  MAX_CAPTURE_INVENTORY_ROWS,
  type CaptureRouteFieldErrors,
  validateAndBuildCaptureRouteRequest,
} from "../form/captureRouteRequest";

const props = defineProps<{ catalogClient: SpeciesCatalogClient }>();
const emit = defineEmits<{ submit: [request: CaptureRouteRequest] }>();
const form = reactive(createInitialCaptureRouteForm());
const errors = ref<CaptureRouteFieldErrors>({
  inventory: {},
  candidates: {},
});
const formElement = ref<HTMLFormElement | null>(null);
const targetInput = ref<HTMLInputElement | null>(null);
const locale = ref<SpeciesCatalogLocale>("en");
const catalog = useSpeciesCatalog(props.catalogClient);
let nextKey = 1;

const records = computed<readonly SpeciesCatalogRecord[]>(() =>
  catalog.state.value.kind === "success"
    ? catalog.state.value.response.records
    : [],
);
const catalogUnavailable = computed(
  () =>
    !["idle", "loading", "success"].includes(catalog.state.value.kind),
);
const errorEntries = computed(() => {
  const values: string[] = [];
  if (errors.value.targetSpeciesId) {
    values.push(`Target: ${errors.value.targetSpeciesId}`);
  }
  if (errors.value.inventoryLimit) values.push(errors.value.inventoryLimit);
  if (errors.value.candidateLimit) values.push(errors.value.candidateLimit);
  for (const [index, row] of Object.entries(errors.value.inventory)) {
    if (row.id) values.push(`Inventory row ${Number(index) + 1}: ${row.id}`);
    if (row.speciesId) {
      values.push(`Inventory row ${Number(index) + 1}: ${row.speciesId}`);
    }
  }
  for (const [index, row] of Object.entries(errors.value.candidates)) {
    if (row.id) values.push(`Candidate ${Number(index) + 1}: ${row.id}`);
    if (row.speciesId) {
      values.push(`Candidate ${Number(index) + 1}: ${row.speciesId}`);
    }
  }
  return values;
});

function displayName(record: SpeciesCatalogRecord): string {
  return record.localized_names[locale.value];
}

function normalizeSpecies(value: string): string {
  const trimmed = value.trim();
  const direct = records.value.find((record) => record.species_id === trimmed);
  if (direct) return direct.species_id;
  const named = records.value.filter(
    (record) => displayName(record) === trimmed,
  );
  if (named.length === 1) return named[0]!.species_id;
  const labeled = records.value.find(
    (record) => `${displayName(record)} · ${record.species_id}` === trimmed,
  );
  return labeled?.species_id ?? value;
}

function clearErrors(): void {
  errors.value = { inventory: {}, candidates: {} };
}

function addInventory(): void {
  if (form.inventory.length >= MAX_CAPTURE_INVENTORY_ROWS) return;
  form.inventory.push({
    key: nextKey++,
    instanceId: "",
    speciesId: "",
    gender: "unknown",
  });
  clearErrors();
}

function addCandidate(): void {
  if (form.candidates.length >= MAX_CAPTURE_CANDIDATES) return;
  form.candidates.push({
    key: nextKey++,
    candidateId: "",
    speciesId: "",
    gender: "female",
  });
  clearErrors();
}

async function submit(): Promise<void> {
  form.targetSpeciesId = normalizeSpecies(form.targetSpeciesId);
  form.inventory.forEach((row) => {
    row.speciesId = normalizeSpecies(row.speciesId);
  });
  form.candidates.forEach((row) => {
    row.speciesId = normalizeSpecies(row.speciesId);
  });
  const result = validateAndBuildCaptureRouteRequest(form);
  if (!result.ok) {
    errors.value = result.errors;
    await nextTick();
    if (result.errors.targetSpeciesId) {
      targetInput.value?.focus();
      return;
    }
    formElement.value
      ?.querySelector<HTMLElement>("[aria-invalid='true']")
      ?.focus();
    return;
  }
  clearErrors();
  emit("submit", result.request);
}

onMounted(() => {
  void catalog.load();
});
onBeforeUnmount(() => {
  catalog.dispose();
});
</script>

<template>
  <form
    ref="formElement"
    class="breeding-form capture-route-form"
    aria-labelledby="capture-form-title"
    novalidate
    @submit.prevent="submit"
  >
    <div class="panel-heading">
      <p class="eyebrow">EXPLICIT ACQUISITION CONSOLE</p>
      <h2 id="capture-form-title">Minimize new captures</h2>
      <p>
        Add only concrete Pals you personally allow as hypothetical new
        acquisitions.
      </p>
    </div>

    <div class="dataset-scope">
      <strong>Fixed production dataset</strong>
      <code>{{ CAPTURE_ROUTE_DATASET_ID }}</code>
    </div>

    <div class="capture-boundary" role="note">
      <strong>Acquisition boundary</strong>
      <p>{{ CAPTURE_ACQUISITION_MESSAGE }}</p>
      <p>
        Allowing the target itself may produce a one-capture, zero-step result.
      </p>
    </div>

    <section class="catalog-controls" aria-labelledby="capture-catalog-title">
      <div>
        <h3 id="capture-catalog-title">Localized species suggestions</h3>
        <p v-if="catalog.state.value.kind === 'loading'" role="status">
          Loading verified species suggestions…
        </p>
        <p v-else-if="catalog.state.value.kind === 'success'" role="status">
          Suggestions loaded; submitted values remain stable IDs.
        </p>
        <div v-else-if="catalogUnavailable" class="catalog-warning" role="status">
          <p>Catalog unavailable. Manual stable-ID entry remains available.</p>
          <button type="button" class="button button-compact" @click="catalog.load">
            Retry catalog
          </button>
        </div>
      </div>
      <div class="field">
        <label for="capture-species-locale">Suggestion language</label>
        <select
          id="capture-species-locale"
          v-model="locale"
          :disabled="catalog.state.value.kind !== 'success'"
        >
          <option
            v-for="tag in SPECIES_CATALOG_LOCALE_TAGS"
            :key="tag"
            :value="tag"
          >
            {{ tag }}
          </option>
        </select>
      </div>
    </section>

    <datalist id="capture-species-suggestions">
      <option
        v-for="record in records"
        :key="record.species_id"
        :value="record.species_id"
        :label="`${displayName(record)} · ${record.species_id}`"
      />
    </datalist>

    <div v-if="errorEntries.length" class="error-summary" role="alert">
      <strong>Check the highlighted fields.</strong>
      <ul>
        <li v-for="message in errorEntries" :key="message">{{ message }}</li>
      </ul>
    </div>

    <fieldset>
      <legend>Target</legend>
      <div class="field">
        <label for="capture-target-species">Target species ID</label>
        <input
          id="capture-target-species"
          ref="targetInput"
          v-model="form.targetSpeciesId"
          name="capture-target-species"
          list="capture-species-suggestions"
          maxlength="64"
          :aria-invalid="Boolean(errors.targetSpeciesId)"
          @input="clearErrors"
        />
        <p v-if="errors.targetSpeciesId" class="field-error">
          {{ errors.targetSpeciesId }}
        </p>
      </div>
      <div class="field">
        <label for="capture-target-gender">Target gender</label>
        <select id="capture-target-gender" v-model="form.targetGender">
          <option value="female">Female</option>
          <option value="male">Male</option>
        </select>
      </div>
    </fieldset>

    <fieldset>
      <legend>Owned inventory · {{ form.inventory.length }} / 299</legend>
      <div
        v-for="(row, index) in form.inventory"
        :key="row.key"
        class="inventory-row"
      >
        <div class="inventory-row-heading">
          <h3>Owned row {{ index + 1 }}</h3>
          <button
            type="button"
            class="button button-compact"
            @click="form.inventory.splice(index, 1); clearErrors()"
          >
            Remove
          </button>
        </div>
        <div class="field">
          <label :for="`capture-owned-${row.key}-id`">Instance ID</label>
          <input
            :id="`capture-owned-${row.key}-id`"
            v-model="row.instanceId"
            :aria-invalid="Boolean(errors.inventory[index]?.id)"
            @input="clearErrors"
          />
          <p v-if="errors.inventory[index]?.id" class="field-error">
            {{ errors.inventory[index]?.id }}
          </p>
        </div>
        <div class="inventory-row-fields">
          <div class="field">
            <label :for="`capture-owned-${row.key}-species`">Species ID</label>
            <input
              :id="`capture-owned-${row.key}-species`"
              v-model="row.speciesId"
              list="capture-species-suggestions"
              :aria-invalid="Boolean(errors.inventory[index]?.speciesId)"
              @input="clearErrors"
            />
            <p v-if="errors.inventory[index]?.speciesId" class="field-error">
              {{ errors.inventory[index]?.speciesId }}
            </p>
          </div>
          <div class="field">
            <label :for="`capture-owned-${row.key}-gender`">Gender</label>
            <select :id="`capture-owned-${row.key}-gender`" v-model="row.gender">
              <option value="unknown">Unknown</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </div>
        </div>
      </div>
      <button type="button" class="button" @click="addInventory">
        Add owned Pal
      </button>
    </fieldset>

    <fieldset>
      <legend>Allowed capture candidates · {{ form.candidates.length }} / 16</legend>
      <p class="field-help">
        Each row asserts one concrete species-and-gender individual; it does not
        assert that the Pal is catchable.
      </p>
      <div
        v-for="(row, index) in form.candidates"
        :key="row.key"
        class="inventory-row capture-candidate-row"
      >
        <div class="inventory-row-heading">
          <h3>Candidate {{ index + 1 }}</h3>
          <button
            type="button"
            class="button button-compact"
            @click="form.candidates.splice(index, 1); clearErrors()"
          >
            Remove
          </button>
        </div>
        <div class="field">
          <label :for="`capture-candidate-${row.key}-id`">Candidate ID</label>
          <input
            :id="`capture-candidate-${row.key}-id`"
            v-model="row.candidateId"
            :aria-invalid="Boolean(errors.candidates[index]?.id)"
            @input="clearErrors"
          />
          <p v-if="errors.candidates[index]?.id" class="field-error">
            {{ errors.candidates[index]?.id }}
          </p>
        </div>
        <div class="inventory-row-fields">
          <div class="field">
            <label :for="`capture-candidate-${row.key}-species`">Species ID</label>
            <input
              :id="`capture-candidate-${row.key}-species`"
              v-model="row.speciesId"
              list="capture-species-suggestions"
              :aria-invalid="Boolean(errors.candidates[index]?.speciesId)"
              @input="clearErrors"
            />
            <p v-if="errors.candidates[index]?.speciesId" class="field-error">
              {{ errors.candidates[index]?.speciesId }}
            </p>
          </div>
          <div class="field">
            <label :for="`capture-candidate-${row.key}-gender`">Gender</label>
            <select
              :id="`capture-candidate-${row.key}-gender`"
              v-model="row.gender"
            >
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </div>
        </div>
      </div>
      <button type="button" class="button" @click="addCandidate">
        Add allowed capture
      </button>
    </fieldset>

    <div class="objective-note">
      <span>Objective</span>
      <strong>Minimum distinct new captures</strong>
    </div>
    <button type="submit" class="button button-primary">
      Plan capture-ranked route
    </button>
  </form>
</template>
