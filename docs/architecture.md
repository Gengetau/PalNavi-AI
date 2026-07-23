# Foundation Architecture

The current prototype keeps exact route calculation separate from transport and model
generation. The model gateway remains independent of route planning and is used only by the
retrieval-first knowledge explanation endpoint.

The standalone Vue client is another transport-facing boundary. It uses only the public search and
explanation schemas and never imports Python, repository, provider, or game-integration types.

```text
HTTP schemas and FastAPI dependency provider
             |
             v
breeding planning application service
        |                     |
        v                     v
read-only repository     shared relationship validation
        |
        v
local JSON parse -> manifest validation -> immutable dataset snapshot
        |                     |
        +----------+----------+
                   v
typed breeding domain + deterministic planner
```

The separate model boundary is:

```text
provider-neutral ModelRequest / ModelResponse / ModelGateway
                            |
                            v
            lazily loaded validated runtime configuration
                            |
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
OpenAI Responses    Anthropic Messages   OpenAI-compatible Chat Completions
                                          |       |       |       |
                                      DeepSeek  Zhipu  Bailian  custom
```

The knowledge retrieval boundary is also independent:

```text
synthetic Markdown + manifest
            |
            v
validation -> NFC/line normalization -> deterministic heading/length chunks
            |
            v
transactional SQLite documents + chunks
            |
            v
deterministic lexical retrieval -> ordered citation-complete results
            |
      +-----+----------------------+
      |                            |
      v                            v
POST /api/v1/knowledge/search   bounded deterministic evidence selection
                                   |
                           +-------+--------+
                           |                |
                           v                v
                 zero usable evidence   up to one model call
                           |                |
                           v                v
                      unsupported      fail-closed marker validation
                      (no provider)          |
                                             v
                             POST /api/v1/knowledge/explain
```

```text
Vue form -> normalized typed request -> request controller -> typed API client
                                                       |
                                                       v
                                         same-origin /api/v1 routes
                                                       |
                                                       v
                                      strict runtime response decoder
                                                       |
                                                       v
                                      inert result and citation rendering
```

`palnavi.domain.breeding` contains immutable types and the route planner. It imports no
FastAPI, Pydantic, persistence, model SDK, or game-integration library. The planner accepts
explicit relationships and an owned-species set, computes reachability, and searches for an
executable route. It minimizes maximum dependency generation first, then step count, then a
canonical relationship signature for stable tie-breaking. A species is never added to one
search state twice, and a finite closure check makes cyclic and unreachable data explicit.

`palnavi.domain.data` owns immutable dataset metadata, structured provenance, validation
issues, repository outcomes, the read-only repository protocol, shared relationship
validation, and canonical content hashing. These contracts use only Python standard-library
types and domain breeding relationships.

`palnavi.application.breeding_planning` depends on the repository protocol and a planner
protocol. It will not call the planner after a dataset lookup or relationship validation
failure. Fixture-backed and explicit-relationship requests converge on the same relationship
validation rule before planning.

`palnavi.application.model_gateway` defines provider-neutral asynchronous text-generation
contracts, provider and message-role identifiers, usage data, and normalized failure
categories. These contracts do not import an HTTP client or provider SDK.

`palnavi.infrastructure` contains the JSON importer and local read-only repository. It owns
filesystem and JSON details, validates the manifest before constructing a snapshot, and
verifies the declared SHA-256 against canonicalized metadata, provenance, and relationships. Repository results
are immutable and report found, not-found, or structured invalid outcomes.

`palnavi.infrastructure.model` loads validated environment or explicit configuration and maps
the six supported provider identifiers onto three HTTP protocols. Credentials are excluded
from configuration representations, response bodies are never copied into gateway errors,
and custom endpoints reject embedded credentials, queries, fragments, and non-loopback HTTP.
The explanation dependency loads provider configuration only after usable evidence exists. If it
constructs an HTTP gateway, it owns and closes that client during cancellation-shielded request
cleanup. Search and breeding dependencies never load model configuration.

`palnavi.domain.knowledge` owns immutable document, chunk, query, repository, result, and
citation contracts. `palnavi.infrastructure.knowledge_ingestion` owns canonical normalization,
identity verification, and deterministic Markdown chunking. The SQLite adapter owns only its
feature tables, replaces updated document chunks transactionally, and performs deterministic
standard-library lexical scoring so behavior does not depend on optional SQLite FTS5 builds.

`palnavi.application.knowledge_explanation` runs deterministic retrieval before any model
setup or generation. It selects at most five usable chunks in returned order, labels them with
assigned markers, HTML-escapes structural text, numeric-entity-encodes source square brackets,
requests one bounded non-streaming generation, and validates conservative plain-text output before
attaching retrieval-owned citations. Zero usable evidence returns unsupported without loading
configuration or creating an HTTP client.
Model text is untrusted and never changes knowledge records or deterministic mechanics.

`palnavi.api` owns HTTP schemas and maps them to application/domain models. FastAPI dependency
providers create repository and service instances without a global mutable repository.
The async explanation dependency permits fake repositories and gateways in tests and owns any
HTTP client it constructs. Endpoint functions do not parse JSON datasets, implement graph search,
or query SQLite rows directly. Dataset not found is
HTTP 404. HTTP 422 has two validation layers: repository or explicit-relationship validation
uses the structured PalNavi `RouteResponse`, while malformed request bodies rejected before
route execution use FastAPI's `detail` response. OpenAPI declares both shapes as a union with
registered component references. FastAPI generates the interactive documentation.

`frontend/src/api` mirrors only the accepted public knowledge schema in TypeScript. Its replaceable
transport is the sole `fetch` boundary, endpoints are fixed origin-relative paths, and small manual
decoders reconstruct trusted objects without spreading unknown fields. HTTP, response-shape,
backend, network, unsupported, and abort outcomes remain distinct.

`frontend/src/composables/useKnowledgeRequest.ts` owns one active `AbortController` and a monotonic
request ID. A replacement request aborts the previous signal, and the ID guard prevents a transport
that ignores cancellation from writing stale state. Components render backend strings only through
Vue text interpolation. Source locators remain inert text, and no Markdown or raw HTML path exists.

## Current assumptions and boundaries

- Inventory is species-level; individual sex, traits, quantities, and availability are future work.
- A route generation is one plus the maximum generation of its parents. Owned species are generation zero.
- The objective is minimum generation depth; step count and a stable signature break ties.
- `new_capture_count` is present in cost output but remains zero because capture planning is not authorized yet.
- Relationship data is supplied explicitly or loaded through the validated repository boundary.
- Dataset identity is metadata, not a filesystem path; paths are never exposed by the API.
- Schema version and game-version scope are separate mandatory manifest concepts.
- The only local dataset is classified synthetic, claims no game version, and has synthetic provenance.
- SQLite is used only for the local versioned knowledge feature; no external search service or
  vector database is present.
- `/api/v1/knowledge/search` returns retrieved chunks and citations without generation or model
  configuration.
- `/api/v1/knowledge/explain` is the only model-backed route; it retrieves first and can return
  success, unsupported, or a controlled error.
- Explanation does not retry, fan out, stream, call tools, or run an agent loop.
- Model output is never the source of truth for deterministic breeding or other exact mechanics.
- The standalone frontend covers search and explanation with deterministic mock-tested behavior.
- The frontend defaults visibly to synthetic-only and collects no provider credential or endpoint.
- There is no game adapter, save access, or mutation.
- Real Palworld explanations remain unavailable until reviewed, versioned knowledge data is imported.
