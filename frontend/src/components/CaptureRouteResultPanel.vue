<script setup lang="ts">
import type { CaptureRouteViewState } from "../composables/useCaptureRouteRequest";

defineProps<{ state: CaptureRouteViewState }>();
defineEmits<{ retry: [] }>();
</script>

<template>
  <section
    class="result-panel capture-result-panel"
    aria-labelledby="capture-result-title"
    :aria-busy="state.kind === 'loading'"
  >
    <div class="panel-heading">
      <p class="eyebrow">EXACT ROUTE OUTPUT</p>
      <h2 id="capture-result-title">Capture-ranked result</h2>
    </div>

    <div v-if="state.kind === 'idle'" class="empty-state">
      <strong>Ready to compare explicit candidates</strong>
      <p>No planning request is issued until you submit the form.</p>
    </div>

    <div v-else-if="state.kind === 'loading'" class="loading-state" role="status">
      <strong>Searching exact capture-set labels…</strong>
      <p>The latest immutable request replaces any earlier in-flight request.</p>
    </div>

    <template v-else-if="state.kind === 'success'">
      <div class="result-summary verified-summary">
        <div>
          <span>New captures</span>
          <strong>{{ state.response.cost.new_capture_count }}</strong>
        </div>
        <div>
          <span>Generations</span>
          <strong>{{ state.response.cost.generations }}</strong>
        </div>
        <div>
          <span>Breeding steps</span>
          <strong>{{ state.response.cost.breeding_steps }}</strong>
        </div>
      </div>
      <div class="capture-boundary">
        <strong>Acquisition boundary</strong>
        <p>{{ state.response.acquisition_boundary.message }}</p>
      </div>
      <section aria-labelledby="capture-requirements-title">
        <h3 id="capture-requirements-title">Exact capture requirements</h3>
        <p v-if="state.response.capture_requirements.length === 0">
          No new capture candidate is required.
        </p>
        <ol v-else class="route-list">
          <li
            v-for="item in state.response.capture_requirements"
            :key="item.candidate_id"
          >
            <strong>{{ item.candidate_id }}</strong>
            <code>{{ item.species_id }}</code>
            <span>{{ item.gender }}</span>
          </li>
        </ol>
      </section>
      <p
        v-if="
          state.response.steps.length === 0 &&
          state.response.capture_requirements.length === 1
        "
        class="direct-capture-note"
      >
        Direct target acquisition: one allowed target candidate, zero breeding
        steps.
      </p>
      <section aria-labelledby="capture-steps-title">
        <h3 id="capture-steps-title">Deterministic breeding steps</h3>
        <p v-if="state.response.steps.length === 0">
          No breeding step is required.
        </p>
        <ol v-else class="route-list">
          <li v-for="step in state.response.steps" :key="step.order">
            <span>Generation {{ step.generation }}</span>
            <strong>
              {{ step.parent_a.species_id }} ({{ step.parent_a.gender }}) ×
              {{ step.parent_b.species_id }} ({{ step.parent_b.gender }})
            </strong>
            <span>→ {{ step.child.species_id }} ({{ step.child.gender }})</span>
            <code>{{ step.source_record_hash }}</code>
          </li>
        </ol>
      </section>
    </template>

    <div
      v-else-if="state.kind === 'gender-required'"
      class="error-state"
      role="status"
    >
      <strong>Concrete owned genders required</strong>
      <p>{{ state.response.message }}</p>
      <ul>
        <li v-for="id in state.response.unknown_instance_ids" :key="id">
          {{ id }}
        </li>
      </ul>
    </div>

    <div
      v-else-if="state.kind === 'unreachable'"
      class="empty-state"
      role="status"
    >
      <strong>No exact route from this submitted set</strong>
      <p>{{ state.response.message }}</p>
    </div>

    <div
      v-else-if="state.kind === 'search-limit-exceeded'"
      class="error-state"
      role="alert"
    >
      <strong>Exact search stopped safely</strong>
      <p>{{ state.response.message }}</p>
      <p>No approximate route was returned.</p>
    </div>

    <div v-else class="error-state" role="alert">
      <strong>Capture-ranked route unavailable</strong>
      <p v-if="state.kind === 'backend-invalid'">
        {{ state.response.message }}
      </p>
      <p v-else>{{ state.message }}</p>
      <button type="button" class="button" @click="$emit('retry')">
        Retry exact request
      </button>
    </div>
  </section>
</template>
