<script setup lang="ts">
import type { BreedingRouteState } from "../api/breedingContract";
import type { BreedingViewState } from "../composables/useBreedingRequest";

defineProps<{ state: BreedingViewState }>();
defineEmits<{ retry: [] }>();

const stateLabel = (state: BreedingRouteState): string =>
  `${state.species_id} · ${state.gender} · generation ${state.generation_depth}`;
</script>

<template>
  <section
    class="result-panel breeding-result-panel"
    aria-label="Breeding route response"
    :aria-busy="state.kind === 'loading'"
  >
    <p v-if="state.kind !== 'idle'" class="submitted-scope">
      Submitted target: {{ state.request.target.species_id }} ·
      {{ state.request.target.gender }} · {{ state.request.inventory.length }}
      inventory rows
    </p>

    <div v-if="state.kind === 'idle'" class="state-card idle-state">
      <p class="eyebrow">PLANNER READY</p>
      <h2>Ready for a concrete inventory</h2>
      <p>
        Add only Pals you own, identify their genders explicitly, and submit a
        read-only route request.
      </p>
    </div>

    <div v-else-if="state.kind === 'loading'" class="state-card loading-state">
      <p class="eyebrow">REQUEST {{ state.requestId }}</p>
      <h2>Planning a verified route…</h2>
      <p>A newer submission safely replaces this request.</p>
    </div>

    <div v-else-if="state.kind === 'success'" class="route-result">
      <header class="result-heading">
        <p class="eyebrow">VERIFIED ROUTE · SUCCESS</p>
        <h2>
          {{ state.response.target.species_id }} ·
          {{ state.response.target.gender }}
        </h2>
        <p>
          {{ state.response.cost.generations }} generations ·
          {{ state.response.cost.breeding_steps }} breeding steps
        </p>
      </header>

      <div class="availability-warning" role="note">
        <strong>Probability-dependent cost is unavailable.</strong>
        <span>
          Expected attempts, cakes, incubation, inventory consumption,
          passives, IV inheritance, and save integration are not calculated.
        </span>
      </div>

      <div
        v-if="state.response.steps.length === 0"
        class="empty-state zero-step-state"
      >
        <h3>Target already owned</h3>
        <p>No breeding step is needed for this request.</p>
      </div>

      <ol v-else class="route-steps">
        <li
          v-for="step in state.response.steps"
          :key="step.order"
          class="route-step"
        >
          <p class="eyebrow">
            STEP {{ step.order }} · GENERATION {{ step.generation }}
          </p>
          <div class="breeding-equation">
            <span>
              <strong>{{ step.parent_a.species_id }}</strong>
              <small>{{ step.parent_a.gender }}</small>
            </span>
            <b aria-hidden="true">+</b>
            <span>
              <strong>{{ step.parent_b.species_id }}</strong>
              <small>{{ step.parent_b.gender }}</small>
            </span>
            <b aria-hidden="true">→</b>
            <span>
              <strong>{{ step.child.species_id }}</strong>
              <small>{{ step.child.gender }}</small>
            </span>
          </div>
          <p class="result-kind">Result kind: {{ step.result_kind }}</p>
        </li>
      </ol>

      <details class="provenance-disclosure">
        <summary>Verified dataset provenance</summary>
        <dl class="citation-details">
          <dt>Dataset</dt>
          <dd><code>{{ state.response.dataset_id }}</code></dd>
          <dt>Main content SHA-256</dt>
          <dd><code>{{ state.response.content_sha256 }}</code></dd>
          <dt>Gender data SHA-256</dt>
          <dd>
            <code>{{ state.response.gender_data_content_sha256 }}</code>
          </dd>
        </dl>
        <ol v-if="state.response.steps.length" class="source-hash-list">
          <li v-for="step in state.response.steps" :key="step.order">
            Step {{ step.order }} source record:
            <code>{{ step.source_record_hash }}</code>
          </li>
        </ol>
      </details>
    </div>

    <div
      v-else-if="state.kind === 'gender-required'"
      class="state-card attention-state"
    >
      <p class="eyebrow">GENDER REQUIRED</p>
      <h2>Inventory genders are incomplete</h2>
      <p>{{ state.response.message }}</p>
      <p>Identify these exact inventory instances:</p>
      <ul class="identifier-list">
        <li v-for="id in state.response.unknown_instance_ids" :key="id">
          <code>{{ id }}</code>
        </li>
      </ul>
      <button type="button" class="button" @click="$emit('retry')">
        Retry last request
      </button>
    </div>

    <div
      v-else-if="state.kind === 'unreachable'"
      class="state-card attention-state"
    >
      <p class="eyebrow">NO ROUTE FOUND</p>
      <h2>Target is unreachable from this inventory</h2>
      <p>{{ state.response.message }}</p>
      <details v-if="state.response.reachable_states.length">
        <summary>Validated reachable states</summary>
        <ul class="identifier-list">
          <li
            v-for="item in state.response.reachable_states"
            :key="stateLabel(item)"
          >
            <code>{{ stateLabel(item) }}</code>
          </li>
        </ul>
      </details>
      <button type="button" class="button" @click="$emit('retry')">
        Retry last request
      </button>
    </div>

    <div
      v-else-if="state.kind === 'backend-invalid'"
      class="state-card error-state"
      role="alert"
    >
      <p class="eyebrow">BACKEND INVALID · HTTP {{ state.httpStatus }}</p>
      <h2>Route request or production data was rejected</h2>
      <p>{{ state.response.message }}</p>
      <p class="error-category">
        Category: {{ state.response.error_category }}
      </p>
      <ul>
        <li v-for="(issue, index) in state.response.errors" :key="index">
          {{ issue.field }}: {{ issue.message }} ({{ issue.code }})
        </li>
      </ul>
      <button type="button" class="button" @click="$emit('retry')">
        Retry last request
      </button>
    </div>

    <div
      v-else-if="state.kind === 'http-invalid'"
      class="state-card error-state"
      role="alert"
    >
      <p class="eyebrow">INVALID RESPONSE · HTTP {{ state.httpStatus }}</p>
      <h2>Breeding response could not be used</h2>
      <p>{{ state.message }}</p>
      <p class="error-category">Reason: {{ state.reason }}</p>
      <button type="button" class="button" @click="$emit('retry')">
        Retry last request
      </button>
    </div>

    <div
      v-else-if="state.kind === 'network-error'"
      class="state-card error-state"
      role="alert"
    >
      <p class="eyebrow">NETWORK FAILURE</p>
      <h2>Breeding service could not be reached</h2>
      <p>{{ state.message }}</p>
      <button type="button" class="button" @click="$emit('retry')">
        Retry last request
      </button>
    </div>
  </section>
</template>
