<script setup lang="ts">
import type { Citation } from "../api/contract";

defineProps<{
  citation: Citation;
  marker: string | null;
}>();

const section = (parts: string[]): string =>
  parts.length > 0 ? parts.join(" / ") : "Root";
</script>

<template>
  <dl class="citation-details">
    <template v-if="marker">
      <dt>Marker</dt>
      <dd><span class="marker">{{ marker }}</span></dd>
    </template>
    <dt>Title</dt>
    <dd>{{ citation.title || "Untitled source" }}</dd>
    <dt>Document ID</dt>
    <dd><code>{{ citation.document_id }}</code></dd>
    <dt>Chunk ID</dt>
    <dd><code>{{ citation.chunk_id }}</code></dd>
    <dt>Section</dt>
    <dd>{{ section(citation.section_path) }}</dd>
    <dt>Source ID</dt>
    <dd><code>{{ citation.source_id }}</code></dd>
    <dt>Source locator</dt>
    <dd><code class="source-locator">{{ citation.source_locator }}</code></dd>
    <dt>Retrieved</dt>
    <dd>{{ citation.retrieved_at }}</dd>
    <dt>License / usage</dt>
    <dd>{{ citation.license_or_usage_note }}</dd>
  </dl>
</template>
