<script setup lang="ts">
import { computed, nextTick, reactive, ref } from "vue";

import type { KnowledgeRequest, Operation } from "../api/contract";
import {
  INITIAL_FORM,
  type FieldErrors,
  type FormField,
  validateAndBuildRequest,
} from "../form/knowledgeRequest";

const emit = defineEmits<{
  submit: [intent: { operation: Operation; request: KnowledgeRequest }];
}>();

const form = reactive({ ...INITIAL_FORM });
const errors = ref<FieldErrors>({});
const queryInput = ref<HTMLTextAreaElement | null>(null);
const languageInput = ref<HTMLInputElement | null>(null);
const versionInput = ref<HTMLInputElement | null>(null);
const limitInput = ref<HTMLInputElement | null>(null);
const queryLength = computed(() => [...form.query.trim()].length);
const errorEntries = computed(() => Object.values(errors.value));
const errorIds: Record<FormField, string> = {
  query: "query-error",
  language: "language-error",
  exactGameVersion: "version-error",
  limit: "limit-error",
};

const focusField: Record<FormField, () => void> = {
  query: () => queryInput.value?.focus(),
  language: () => languageInput.value?.focus(),
  exactGameVersion: () => versionInput.value?.focus(),
  limit: () => limitInput.value?.focus(),
};

function clearError(field: FormField): void {
  if (!(field in errors.value)) {
    return;
  }
  const nextErrors = { ...errors.value };
  delete nextErrors[field];
  errors.value = nextErrors;
}

function describedBy(field: FormField, base: string): string {
  return errors.value[field] ? `${base} ${errorIds[field]}` : base;
}

async function submit(operation: Operation): Promise<void> {
  const result = validateAndBuildRequest(form);
  if (!result.ok) {
    errors.value = result.errors;
    const order: FormField[] = [
      "query",
      "language",
      "exactGameVersion",
      "limit",
    ];
    const first = order.find((field) => field in result.errors);
    await nextTick();
    if (first) {
      focusField[first]();
    }
    return;
  }
  errors.value = {};
  emit("submit", { operation, request: result.request });
}
</script>

<template>
  <form
    class="knowledge-form"
    aria-labelledby="knowledge-form-title"
    novalidate
    @submit.prevent="submit('search')"
  >
    <div class="panel-heading">
      <p class="eyebrow">QUERY CONSOLE</p>
      <h2 id="knowledge-form-title">Ask the local navigator</h2>
      <p>
        Search is deterministic. Explanations use only retrieved evidence and may
        require optional backend provider configuration.
      </p>
    </div>

    <div
      v-if="errorEntries.length"
      class="error-summary"
      role="alert"
      aria-label="Form errors"
    >
      <strong>Check the highlighted fields.</strong>
      <ul>
        <li v-for="message in errorEntries" :key="message">{{ message }}</li>
      </ul>
    </div>

    <div class="field">
      <label for="knowledge-query">Question</label>
      <textarea
        id="knowledge-query"
        ref="queryInput"
        v-model="form.query"
        name="query"
        rows="5"
        maxlength="1000"
        :aria-describedby="describedBy('query', 'query-help query-count')"
        :aria-invalid="Boolean(errors.query)"
        @input="clearError('query')"
      />
      <div class="field-meta">
        <span id="query-help">Surrounding whitespace is ignored.</span>
        <span id="query-count">{{ queryLength }} / 500</span>
      </div>
      <p v-if="errors.query" id="query-error" class="field-error">
        {{ errors.query }}
      </p>
    </div>

    <fieldset>
      <legend>Retrieval scope</legend>

      <div class="field">
        <label for="knowledge-language">Language <span>optional</span></label>
        <input
          id="knowledge-language"
          ref="languageInput"
          v-model="form.language"
          name="language"
          type="text"
          placeholder="en-US"
          maxlength="35"
          :aria-describedby="describedBy('language', 'language-help')"
          :aria-invalid="Boolean(errors.language)"
          @input="clearError('language')"
        />
        <p id="language-help" class="field-help">
          Use a backend-compatible tag such as en, en-US, or zh_Hant.
        </p>
        <p v-if="errors.language" id="language-error" class="field-error">
          {{ errors.language }}
        </p>
      </div>

      <div class="field">
        <label for="knowledge-version">Exact game version <span>optional</span></label>
        <input
          id="knowledge-version"
          ref="versionInput"
          v-model="form.exactGameVersion"
          name="exact-game-version"
          type="text"
          placeholder="synthetic-0.0.0"
          maxlength="128"
          :aria-describedby="
            describedBy('exactGameVersion', 'version-help')
          "
          :aria-invalid="Boolean(errors.exactGameVersion)"
          @input="clearError('exactGameVersion')"
        />
        <p id="version-help" class="field-help">
          Exact matching only; blank means no version filter.
        </p>
        <p
          v-if="errors.exactGameVersion"
          id="version-error"
          class="field-error"
        >
          {{ errors.exactGameVersion }}
        </p>
      </div>

      <div class="field field-small">
        <label for="knowledge-limit">Result limit</label>
        <input
          id="knowledge-limit"
          ref="limitInput"
          v-model="form.limit"
          name="limit"
          type="text"
          inputmode="numeric"
          pattern="[0-9]*"
          maxlength="2"
          :aria-describedby="describedBy('limit', 'limit-help')"
          :aria-invalid="Boolean(errors.limit)"
          @input="clearError('limit')"
        />
        <p id="limit-help" class="field-help">Choose 1 through 20 results.</p>
        <p v-if="errors.limit" id="limit-error" class="field-error">
          {{ errors.limit }}
        </p>
      </div>

      <label class="synthetic-toggle" for="synthetic-only">
        <input
          id="synthetic-only"
          v-model="form.syntheticOnly"
          name="synthetic-only"
          type="checkbox"
        />
        <span>
          <strong>Synthetic knowledge only</strong>
          <small>
            Current fixtures are fictional and are not verified Palworld facts.
          </small>
        </span>
        <b aria-live="polite">{{ form.syntheticOnly ? "ON" : "OFF" }}</b>
      </label>
    </fieldset>

    <div class="form-actions">
      <button type="submit" class="button button-primary">Search knowledge</button>
      <button type="button" class="button" @click="submit('explain')">
        Explain with citations
      </button>
    </div>
  </form>
</template>
