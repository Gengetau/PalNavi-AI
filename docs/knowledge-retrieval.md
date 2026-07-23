# Versioned Knowledge Retrieval

PalNavi's local knowledge layer ingests project-authored synthetic documents, validates their
metadata and declared identity, stores active chunks transactionally in SQLite, and returns
citation-complete lexical search results. It is the retrieval half of a future RAG flow. It does
not call a model, construct prompts, or generate an answer.

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

The response contains only retrieval results and citations. FastAPI request validation and
application-level whitespace validation are both represented in OpenAPI. Repository failures
return HTTP 503 with a structured safe error.

## Synthetic corpus warning

`samples/knowledge/synthetic-v1/` is entirely fictional, project-authored test content. Its
manifest and every document explicitly state that it is not Palworld knowledge. Terms such as
"crystal moss", "cobalt arch", and "paper lantern" are invented retrieval tokens. The corpus
must not be presented as game guidance or combined with production facts.

## Future model use

A later, separately reviewed explanation service may pass retrieved chunks and their citations
to the provider-neutral model gateway. That service must preserve citations, distinguish
synthetic from production scope, return unsupported when evidence is absent, and keep
deterministic structured services authoritative for exact breeding and game facts. This loop
adds no such connection.
