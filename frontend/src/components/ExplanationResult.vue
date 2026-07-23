<script setup lang="ts">
import { computed } from "vue";

import type {
  ExplainCitation,
  KnowledgeRequest,
  TokenUsage,
} from "../api/contract";
import { safeLanguageTag } from "../presentation/language";
import CitationDetails from "./CitationDetails.vue";

const props = defineProps<{
  request: KnowledgeRequest;
  answer: string;
  citations: ExplainCitation[];
  usage: TokenUsage | null;
}>();

const hasUsage = computed(
  () =>
    props.usage !== null &&
    [
      props.usage.input_tokens,
      props.usage.output_tokens,
      props.usage.total_tokens,
    ].some((value) => value !== undefined && value !== null),
);
</script>

<template>
  <section class="result-content" aria-labelledby="explanation-title">
    <div class="result-heading">
      <p class="eyebrow">GROUNDED EXPLANATION</p>
      <h2 id="explanation-title">Citation-backed answer</h2>
      <p class="query-snapshot">For “{{ request.query }}”</p>
    </div>
    <p class="answer-text" :lang="safeLanguageTag(request.language)">
      {{ answer || "No answer text was returned." }}
    </p>
    <dl v-if="hasUsage && usage" class="usage-row" aria-label="Model usage">
      <div v-if="usage.input_tokens !== undefined && usage.input_tokens !== null">
        <dt>Input</dt>
        <dd>{{ usage.input_tokens }}</dd>
      </div>
      <div v-if="usage.output_tokens !== undefined && usage.output_tokens !== null">
        <dt>Output</dt>
        <dd>{{ usage.output_tokens }}</dd>
      </div>
      <div v-if="usage.total_tokens !== undefined && usage.total_tokens !== null">
        <dt>Total</dt>
        <dd>{{ usage.total_tokens }}</dd>
      </div>
    </dl>
    <h3>Canonical citations</h3>
    <ol class="citation-list">
      <li
        v-for="(item, index) in citations"
        :key="`${item.marker}:${item.citation.document_id}:${index}`"
        class="citation-card"
      >
        <h4>
          <span class="marker">{{ item.marker }}</span>
          {{ item.citation.title || "Untitled source" }}
        </h4>
        <CitationDetails :citation="item.citation" :marker="null" />
      </li>
    </ol>
  </section>
</template>
