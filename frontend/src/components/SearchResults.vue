<script setup lang="ts">
import type { KnowledgeRequest, KnowledgeSearchItem } from "../api/contract";
import { safeLanguageTag } from "../presentation/language";
import CitationDetails from "./CitationDetails.vue";

defineProps<{
  request: KnowledgeRequest;
  results: KnowledgeSearchItem[];
  message: string | null;
}>();

function section(parts: string[]): string {
  return parts.length > 0 ? parts.join(" / ") : "Root";
}

function version(item: KnowledgeSearchItem): string {
  return item.game_version_scope.value === null
    ? item.game_version_scope.kind
    : `${item.game_version_scope.kind}: ${item.game_version_scope.value}`;
}
</script>

<template>
  <section class="result-content" aria-labelledby="search-results-title">
    <div class="result-heading">
      <p class="eyebrow">DETERMINISTIC RETRIEVAL</p>
      <h2 id="search-results-title">
        {{ results.length }} result{{ results.length === 1 ? "" : "s" }}
      </h2>
      <p class="query-snapshot">For “{{ request.query }}”</p>
    </div>
    <p v-if="message" class="service-note">{{ message }}</p>
    <p v-if="results.length === 0" class="empty-state">
      No knowledge results matched this query.
    </p>
    <ol v-else class="result-list">
      <li
        v-for="(item, index) in results"
        :key="`${item.document_id}:${item.chunk_id}:${index}`"
      >
        <article class="knowledge-card">
          <div class="card-topline">
            <span class="result-index">RESULT {{ index + 1 }}</span>
            <span class="score">score {{ item.score.toFixed(3) }}</span>
          </div>
          <h3>{{ item.title || "Untitled knowledge item" }}</h3>
          <p class="section-path">{{ section(item.section_path) }}</p>
          <p class="knowledge-text" :lang="safeLanguageTag(item.language)">
            {{ item.text }}
          </p>
          <dl class="metadata-row">
            <div>
              <dt>Language</dt>
              <dd>{{ item.language }}</dd>
            </div>
            <div>
              <dt>Classification</dt>
              <dd>{{ item.classification }}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>{{ version(item) }}</dd>
            </div>
          </dl>
          <details>
            <summary>Citation details</summary>
            <CitationDetails :citation="item.citation" :marker="null" />
          </details>
        </article>
      </li>
    </ol>
  </section>
</template>
