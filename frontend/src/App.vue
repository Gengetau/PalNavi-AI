<script setup lang="ts">
import { computed, onBeforeUnmount } from "vue";

import { createKnowledgeClient } from "./api/knowledgeClient";
import type {
  KnowledgeClient,
  KnowledgeRequest,
  Operation,
} from "./api/contract";
import KnowledgeForm from "./components/KnowledgeForm.vue";
import ResultPanel from "./components/ResultPanel.vue";
import { useKnowledgeRequest } from "./composables/useKnowledgeRequest";

const props = defineProps<{ client?: KnowledgeClient }>();
const controller = useKnowledgeRequest(props.client ?? createKnowledgeClient());

const announcedScope = (syntheticOnly: boolean): string =>
  syntheticOnly
    ? "Submitted scope: synthetic knowledge only."
    : "Submitted scope: synthetic-only filter off.";

const announcement = computed(() => {
  const state = controller.state.value;
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
  void controller.run(intent.operation, intent.request);
}

function retry(): void {
  const state = controller.state.value;
  if (state.kind !== "idle" && state.kind !== "loading") {
    void controller.run(state.operation, state.request);
  }
}

onBeforeUnmount(controller.dispose);
</script>

<template>
  <a class="skip-link" href="#main-content">Skip to knowledge workspace</a>
  <header class="site-header">
    <div>
      <p class="eyebrow">PALNAVI / AI LOOP 006</p>
      <h1>Synthetic Knowledge Navigator</h1>
    </div>
    <div class="safety-badge">
      <span>OFFLINE-FIRST UI</span>
      <strong>No verified game facts loaded</strong>
    </div>
  </header>

  <main id="main-content" class="workspace">
    <aside class="form-panel">
      <KnowledgeForm @submit="run" />
    </aside>
    <ResultPanel :state="controller.state.value" @retry="retry" />
  </main>

  <div class="sr-only" role="status" aria-live="polite" aria-atomic="true">
    {{ announcement }}
  </div>
</template>
