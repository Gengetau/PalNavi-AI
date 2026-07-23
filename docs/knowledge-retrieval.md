# Versioned Knowledge Retrieval

PalNavi's local knowledge layer ingests project-authored synthetic documents, validates their
metadata and declared identity, stores active chunks transactionally in SQLite, and returns
citation-complete lexical search results. Retrieval itself is deterministic and never calls a
model. The `POST /api/v1/knowledge/explain` application layer runs retrieval first and may then ask
the provider-neutral gateway to summarize only a bounded evidence set. The bundled knowledge corpus
remains fictional and synthetic.

## Contracts and boundaries

`palnavi.domain.knowledge` defines immutable application-facing types for:

- stable document and chunk identifiers;
- normalized language identifiers;
- synthetic or production classification and explicit version scope;
- provenance, retrieval/import timestamps, usage notes, and validation status;
- SHA-256 content identity;
- ordered chunks and section paths;
- bounded queries, scores, results, and citations;
- write-on-import/read-only-search repository outcomes.

SQLite rows, raw dictionaries, Pydantic models, filesystem paths, and model-provider objects do
not cross this boundary. Repository failures contain controlled categories and messages without
database paths or underlying exception text.

The explanation layer adds immutable request and outcome contracts for grounded success,
unsupported/no evidence, controlled retrieval or model failure, and invalid model output. Success
carries exact canonical citations and optional sanitized token usage already defined by gateway
contracts. No Pydantic model, HTTP client, provider payload, prompt, raw dictionary, path, API key,
or database row crosses the application boundary.

## Canonical ingestion and chunking

The importer applies these rules in order:

1. Normalize CRLF and CR to LF.
2. Normalize Unicode to NFC.
3. Remove trailing whitespace and outer blank lines.
4. Validate identifiers, title, language, timestamps, version scope, provenance, usage note,
   source locator, schema version, importer version, and declared digest.
5. Calculate canonical SHA-256 over normalized content plus identity-relevant metadata.
6. Parse Markdown ATX headings into stable section paths.
7. Split section bodies at paragraph boundaries and then word or character boundaries so each
   chunk stays within the configured size.
8. Assign zero-based order and a chunk ID derived from document ID, digest prefix, and order.

The same normalized source, metadata, and chunk size therefore produce the same digest, chunk
IDs, section paths, order, and text. A manifest digest mismatch is rejected before storage.
Absolute filesystem locators, `file:` locators, malformed URLs, URL credentials, queries, and
fragments are rejected without copying the supplied locator into an error.

## SQLite lifecycle

The default source-checkout database is `.local/knowledge.sqlite3`; `.local/` is ignored by Git.
An explicit database path can be supplied to the repository or import command. The adapter uses
only these feature-owned tables:

- `knowledge_schema_meta`;
- `knowledge_documents`;
- `knowledge_chunks`.

Migration to schema version 1 is idempotent. A database with a newer unknown schema becomes a
safe unavailable repository rather than exposing its path. Import behavior is:

- new document: `created`;
- identical document and digest: `unchanged`, with no rewrite;
- changed document with the same stable ID: old document and chunks are deleted and replaced in
  one transaction;
- failed replacement: the transaction rolls back, leaving the old active document intact.

No model credential or provider configuration is stored in the knowledge schema.

From `backend`, import the bundled corpus into the default local database:

```powershell
python -m palnavi.infrastructure.knowledge_cli
```

Optional `--database` and `--corpus` paths select an explicit local database or corpus. Command
errors print validation codes or a controlled repository message, not local paths or stack traces.

## Retrieval semantics

Retrieval tokenizes NFKC/case-folded text using standard-library Unicode word matching. Scores
sum chunk matches, title matches with weight 2, and section-path matches with weight 1.5. This
strategy was chosen instead of FTS5 so tests and ordering remain identical across Python/SQLite
builds. It adds no external service or dependency.

Only active, validated chunks are candidates. Optional filters behave as follows:

- `language` requires an exact normalized language match;
- `exact_game_version` returns only explicit scopes with that exact value;
- `synthetic_only` returns only synthetic-classified documents;
- incompatible scopes are excluded rather than silently mixed;
- `limit` is bounded from 1 through 20.

Zero-score chunks are omitted. Results sort by descending score, then document ID and chunk ID.
No match returns a successful empty result and never invents content.

Every result includes score, document/chunk IDs, title, section path, text, language,
classification, version scope, and a citation containing the stable source ID and locator,
retrieval time, and usage note.

## Grounded explanation flow

`KnowledgeExplanationService` enforces this order:

1. Run deterministic retrieval with the validated query, including language, exact-version,
   synthetic-only, and bounded-limit filters unchanged.
2. Return a controlled retrieval error on repository failure, with no model call.
3. Select usable evidence deterministically from retrieval order and assign `[K1]`, `[K2]`, and
   so on.
4. Build separate system and user messages with escaped, explicitly delimited untrusted evidence.
5. Make at most one non-streaming generation request with temperature `0` and a `512` output-token
   limit.
6. Validate the answer as untrusted text and fail closed on any grounding violation.
7. Attach only retrieval-owned canonical citations for markers actually referenced.

Evidence selection accepts at most five items, keeps each item to at most 2,000 characters, keeps
the combined evidence to at most 6,000 characters, and skips items shorter than 16 characters
after trimming. If no item remains, the outcome is `unsupported`; provider configuration is not
loaded, no HTTP client is created, and the model gateway is not called.

Questions and source text are HTML-escaped before prompt assembly, and their square brackets are
encoded as numeric entities. Raw ASCII `[K#]` tokens therefore occur only in assigned marker
attributes rather than inside source or question text. Every source stays inside its own
`<untrusted_evidence>` delimiter with its assigned marker, so text that asks the model to ignore
earlier instructions remains quoted data and cannot change the system-message position or citation
mapping. Prompts contain no provider settings, credentials, local paths, internal exceptions, or
unrelated player context.

A successful answer contains at least one allowed `[K#]` marker, and every nonblank logical line
contains at least one assigned marker. Unknown or unassigned `[K#]` markers, malformed markers,
bare or punctuation-separated `K1`-style markers, non-`K` bracket markers, nested markers,
citation links, HTML or angle-bracket markup, encoded entities, URI strings, schemeless hostnames,
absolute POSIX, Windows, or UNC paths, common credential-token forms, provider request IDs,
explicit metadata presentation, and uncited lines all fail closed as
`invalid_grounded_output`. Metadata presentation includes singular or plural source, document,
chunk, title, locator, URL, and URI labels followed by label punctuation or copulas such as
`is`, `was`, `named`, or `called`; ordinary prose using those nouns without presenting metadata
remains valid. Duplicate adjacent markers are normalized deterministically. The application never
treats model-authored titles, IDs, locators, or URLs as citation metadata: it copies canonical
citation metadata only from the matching retrieval result, returns only cited results, and omits
the raw model text on failure.

## Local API

`POST /api/v1/knowledge/search` accepts:

```json
{
  "query": "crystal moss",
  "language": "en",
  "exact_game_version": "synthetic-1.0",
  "synthetic_only": true,
  "limit": 5
}
```

The search response contains only retrieval results and citations. FastAPI request validation and
application-level whitespace validation are both represented in OpenAPI. Repository failures
return HTTP 503 with a structured safe error.

`POST /api/v1/knowledge/explain` accepts the same query and filter shape. This fictional,
synthetic-only example does not imply real game knowledge:

```json
{
  "query": "fictional crystal moss observation",
  "language": "en",
  "exact_game_version": "synthetic-1.0",
  "synthetic_only": true,
  "limit": 5
}
```

An illustrative grounded response is:

```json
{
  "status": "success",
  "answer": "The fictional note places crystal moss beside a cobalt arch. [K1]",
  "citations": [
    {
      "marker": "[K1]",
      "citation": {
        "document_id": "synthetic-observatory-note",
        "chunk_id": "synthetic-observatory-note-0001",
        "title": "Synthetic Observatory Note",
        "section_path": ["Fictional observations"],
        "source_id": "synthetic-observatory-note",
        "source_locator": "https://example.invalid/palnavi/synthetic-observatory-note",
        "retrieved_at": "2026-07-23T12:00:00+00:00",
        "license_or_usage_note": "Project-authored synthetic fixture."
      }
    }
  ],
  "usage": {
    "input_tokens": 31,
    "output_tokens": 14,
    "total_tokens": 45
  }
}
```

Citation metadata in this example is attached by the application, not copied from the answer.
The endpoint exposes three outcome shapes:

- `success` (HTTP 200) returns grounded answer text, the referenced canonical citation list, and
  optional sanitized usage containing only input, output, and total token counts;
- `unsupported` (HTTP 200) returns a safe message when retrieval yields no usable evidence and
  performs zero model, configuration, and client calls;
- `error` returns a controlled category and safe message for request validation, retrieval,
  missing configuration, authentication rejection, rate limiting, invalid provider requests,
  timeout, provider unavailability, malformed provider responses, unknown providers, or invalid
  grounded output.

Error responses use HTTP 422, 502, 503, or 504 as appropriate. No outcome exposes a raw prompt,
raw provider response, invalid model text, stack trace, credential, provider payload, request ID,
local path, or database row.

Model provider configuration is optional and is resolved lazily only for this explanation route
after usable evidence has been selected. Deterministic search and breeding planning do not load
it and remain available with no model configuration. If the request dependency constructs an
HTTP gateway, it owns the client and closes it in cancellation-shielded cleanup.

## Offline verification

Explanation tests use synthetic fixtures and a deterministic fake gateway; protocol-adapter tests
use an in-memory HTTP transport. Focused guards reject TCP connections, UDP sends, forward and
reverse DNS resolution, and subprocess execution, so tests cannot contact a live provider or
invoke a filesystem-provider command.

## Synthetic corpus warning

`samples/knowledge/synthetic-v1/` is entirely fictional, project-authored test content. Its
manifest and every document explicitly state that it is not Palworld knowledge. Terms such as
"crystal moss", "cobalt arch", and "paper lantern" are invented retrieval tokens. The corpus
must not be presented as game guidance or combined with production facts.

## Authority and current availability

Real Palworld answers remain unavailable until permission-compatible, reviewed, versioned knowledge
data is imported. The bundled corpus supports only fictional synthetic demonstrations.
The explanation endpoint enforces citation mapping rather than semantic fact verification. Model
output may summarize retrieved evidence, but it never becomes the source of truth for deterministic
breeding or any other exact mechanic.

# Official source separation

The versioned official-source registry and its metadata-only snapshot manifests are not knowledge
documents. Acquisition discards every response body after fatal UTF-8 validation and hashing.
Neither a registered URL nor a successful fingerprint authorizes copying, indexing, chunking,
summarizing, or answering from that source. A later source-specific review must explicitly approve
usage scope and version applicability before any production knowledge import.
