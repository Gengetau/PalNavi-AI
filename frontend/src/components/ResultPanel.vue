<script setup lang="ts">
import type { ViewState } from "../composables/useKnowledgeRequest";
import ExplanationResult from "./ExplanationResult.vue";
import SearchResults from "./SearchResults.vue";

defineProps<{ state: ViewState }>();
defineEmits<{ retry: [] }>();
</script>

<template>
  <section
    class="result-panel"
    aria-label="Knowledge response"
    :aria-busy="state.kind === 'loading'"
  >
    <div v-if="state.kind === 'idle'" class="state-card idle-state">
      <p class="eyebrow">SYSTEM READY</p>
      <h2>Ready to navigate</h2>
      <p>Enter a question, keep synthetic-only enabled, and choose an action.</p>
    </div>

    <div v-else-if="state.kind === 'loading'" class="state-card loading-state">
      <p class="eyebrow">REQUEST {{ state.requestId }}</p>
      <h2>
        {{
          state.operation === "search"
            ? "Searching synthetic knowledge…"
            : "Building a grounded explanation…"
        }}
      </h2>
      <p>A newer action will safely replace this request.</p>
    </div>

    <SearchResults
      v-else-if="state.kind === 'search-success'"
      :request="state.request"
      :results="state.results"
      :message="state.message"
    />

    <ExplanationResult
      v-else-if="state.kind === 'explain-success'"
      :request="state.request"
      :answer="state.answer"
      :citations="state.citations"
      :usage="state.usage"
    />

    <div
      v-else-if="state.kind === 'unsupported'"
      class="state-card unsupported-state"
    >
      <p class="eyebrow">NO USABLE EVIDENCE</p>
      <h2>Grounded explanation unavailable</h2>
      <p>{{ state.message }}</p>
      <button type="button" class="button" @click="$emit('retry')">
        Retry last request
      </button>
    </div>

    <div
      v-else-if="state.kind === 'backend-error'"
      class="state-card error-state"
      role="alert"
    >
      <p class="eyebrow">BACKEND ERROR · HTTP {{ state.httpStatus }}</p>
      <h2>Knowledge service reported a problem</h2>
      <p>{{ state.message }}</p>
      <p v-if="state.errorCategory" class="error-category">
        Category: {{ state.errorCategory }}
      </p>
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
      <h2>Service response could not be used</h2>
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
      <h2>Knowledge service could not be reached</h2>
      <p>{{ state.message }}</p>
      <button type="button" class="button" @click="$emit('retry')">
        Retry last request
      </button>
    </div>
  </section>
</template>
