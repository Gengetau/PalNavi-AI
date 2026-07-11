# Foundation Architecture

The current prototype keeps exact route calculation separate from transport and model
generation. The model gateway is an independent application port; it is not wired into route
planning or the public API.

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
                 validated runtime configuration
                            |
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
OpenAI Responses    Anthropic Messages   OpenAI-compatible Chat Completions
                                          |       |       |       |
                                      DeepSeek  Zhipu  Bailian  custom
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

`palnavi.api` owns HTTP schemas and maps them to application/domain models. FastAPI dependency
providers create repository and service instances without a global mutable repository.
Endpoint functions do not parse JSON datasets or implement graph search. Dataset not found is
HTTP 404. HTTP 422 has two validation layers: repository or explicit-relationship validation
uses the structured PalNavi `RouteResponse`, while malformed request bodies rejected before
route execution use FastAPI's `detail` response. OpenAPI declares both shapes as a union with
registered component references. FastAPI generates the interactive documentation.

## Current assumptions and boundaries

- Inventory is species-level; individual sex, traits, quantities, and availability are future work.
- A route generation is one plus the maximum generation of its parents. Owned species are generation zero.
- The objective is minimum generation depth; step count and a stable signature break ties.
- `new_capture_count` is present in cost output but remains zero because capture planning is not authorized yet.
- Relationship data is supplied explicitly or loaded through the validated repository boundary.
- Dataset identity is metadata, not a filesystem path; paths are never exposed by the API.
- Schema version and game-version scope are separate mandatory manifest concepts.
- The only local dataset is classified synthetic, claims no game version, and has synthetic provenance.
- There is no database, RAG, model orchestration, public model endpoint, frontend, game adapter,
  save access, or mutation. Model adapters are transport foundations only.
