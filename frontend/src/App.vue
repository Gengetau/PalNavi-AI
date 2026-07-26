<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";

import { createBreedingClient } from "./api/breedingClient";
import type {
  BreedingClient,
  BreedingRequest,
} from "./api/breedingContract";
import { createKnowledgeClient } from "./api/knowledgeClient";
import type {
  KnowledgeClient,
  KnowledgeRequest,
  Operation,
} from "./api/contract";
import BreedingForm from "./components/BreedingForm.vue";
import BreedingResultPanel from "./components/BreedingResultPanel.vue";
import KnowledgeForm from "./components/KnowledgeForm.vue";
import ResultPanel from "./components/ResultPanel.vue";
import { useBreedingRequest } from "./composables/useBreedingRequest";
import { useKnowledgeRequest } from "./composables/useKnowledgeRequest";

const props = defineProps<{
  client?: KnowledgeClient;
  breedingClient?: BreedingClient;
}>();
const activeWorkspace = ref<"knowledge" | "breeding">("knowledge");
const knowledgeController = useKnowledgeRequest(
  props.client ?? createKnowledgeClient(),
);
const breedingController = useBreedingRequest(
  props.breedingClient ?? createBreedingClient(),
);

const announcedScope = (syntheticOnly: boolean): string =>
  syntheticOnly
    ? "Submitted scope: synthetic knowledge only."
    : "Submitted scope: synthetic-only filter off.";

const announcement = computed(() => {
  if (activeWorkspace.value === "breeding") {
    const state = breedingController.state.value;
    switch (state.kind) {
      case "idle":
        return "Breeding planner ready.";
      case "loading":
        return "Planning a verified breeding route.";
      case "success":
        return `Verified route loaded with ${state.response.steps.length} breeding steps.`;
      case "gender-required":
        return `Gender information is required for ${state.response.unknown_instance_ids.length} inventory instances.`;
      case "unreachable":
        return "The target is unreachable from the submitted inventory.";
      case "backend-invalid":
        return "The breeding service rejected the request or production data.";
      case "http-invalid":
        return "The breeding service response could not be used.";
      case "network-error":
        return "The breeding service could not be reached.";
    }
  }
  const state = knowledgeController.state.value;
  if (state.kind === "idle") {
    return "Knowledge navigator ready.";
  }
  const scope = announcedScope(state.request.synthetic_only);
  switch (state.kind) {
    case "loading":
      return `${state.operation === "search"
        ? state.request.synthetic_only
          ? "Searching synthetic knowledge."
          : "Searching available knowledge with the synthetic-only filter off."
        : "Building a grounded explanation."} ${scope}`;
    case "search-success":
      return `${state.results.length} knowledge results loaded. ${scope}`;
    case "explain-success":
      return `Grounded explanation loaded with ${state.citations.length} citations. ${scope}`;
    case "unsupported":
      return `Grounded explanation is unavailable for this query. ${scope}`;
    case "backend-error":
    case "http-invalid":
    case "network-error":
      return scope;
  }
});

function run(intent: {
  operation: Operation;
  request: KnowledgeRequest;
}): void {
  void knowledgeController.run(intent.operation, intent.request);
}

function retry(): void {
  const state = knowledgeController.state.value;
  if (state.kind !== "idle" && state.kind !== "loading") {
    void knowledgeController.run(state.operation, state.request);
  }
}

function runBreeding(request: BreedingRequest): void {
  void breedingController.run(request);
}

onBeforeUnmount(() => {
  knowledgeController.dispose();
  breedingController.dispose();
});
</script>

<template>
  <a class="skip-link" href="#main-content">Skip to active workspace</a>
  <header class="site-header">
    <div>
      <p class="eyebrow">
        {{
          activeWorkspace === "knowledge"
            ? "PALNAVI / SYNTHETIC KNOWLEDGE"
            : "PALNAVI / VERIFIED BREEDING"
        }}
      </p>
      <h1>
        {{
          activeWorkspace === "knowledge"
            ? "Synthetic Knowledge Navigator"
            : "Production Breeding Planner"
        }}
      </h1>
    </div>
    <div
      class="safety-badge"
      :class="{ 'verified-badge': activeWorkspace === 'breeding' }"
    >
      <span>
        {{
          activeWorkspace === "knowledge"
            ? "SYNTHETIC WORKSPACE"
            : "VERIFIED DATA WORKSPACE"
        }}
      </span>
      <strong>
        {{
          activeWorkspace === "knowledge"
            ? "No verified game facts loaded"
            : "Read-only planning · manual inventory"
        }}
      </strong>
    </div>
  </header>

  <nav class="workspace-switcher" aria-label="PalNavi workspace">
    <label :class="{ active: activeWorkspace === 'knowledge' }">
      <input
        v-model="activeWorkspace"
        type="radio"
        name="workspace"
        value="knowledge"
      />
      <span>Knowledge</span>
      <small>Synthetic corpus</small>
    </label>
    <label :class="{ active: activeWorkspace === 'breeding' }">
      <input
        v-model="activeWorkspace"
        type="radio"
        name="workspace"
        value="breeding"
      />
      <span>Breeding</span>
      <small>Verified production data</small>
    </label>
  </nav>

  <main
    v-if="activeWorkspace === 'knowledge'"
    id="main-content"
    class="workspace"
  >
    <aside class="form-panel">
      <KnowledgeForm @submit="run" />
    </aside>
    <ResultPanel :state="knowledgeController.state.value" @retry="retry" />
  </main>

  <main v-else id="main-content" class="workspace breeding-workspace">
    <aside class="form-panel">
      <BreedingForm @submit="runBreeding" />
    </aside>
    <BreedingResultPanel
      :state="breedingController.state.value"
      @retry="breedingController.retry"
    />
  </main>

  <div class="sr-only" role="status" aria-live="polite" aria-atomic="true">
    {{ announcement }}
  </div>
</template>
