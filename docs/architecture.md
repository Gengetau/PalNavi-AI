# Foundation Architecture

The current prototype keeps exact route calculation separate from transport and from any
future language-model orchestration.

```text
HTTP schemas and FastAPI routes
             |
             v
input mapping / fixture loading
             |
             v
typed breeding domain + deterministic planner
```

`palnavi.domain.breeding` contains immutable types and the route planner. It imports no
FastAPI, Pydantic, persistence, model SDK, or game-integration library. The planner accepts
explicit relationships and an owned-species set, computes reachability, and searches for an
executable route. It minimizes maximum dependency generation first, then step count, then a
canonical relationship signature for stable tie-breaking. A species is never added to one
search state twice, and a finite closure check makes cyclic and unreachable data explicit.

`palnavi.application.fixtures` is a thin local-data adapter for the fictional development
fixture. It is replaceable by a versioned repository in a later loop.

`palnavi.api` owns HTTP schemas and maps them to domain models. Endpoint functions do not
implement graph search. FastAPI generates the OpenAPI schema and interactive documentation.

## Current assumptions and boundaries

- Inventory is species-level; individual sex, traits, quantities, and availability are future work.
- A route generation is one plus the maximum generation of its parents. Owned species are generation zero.
- The objective is minimum generation depth; step count and a stable signature break ties.
- `new_capture_count` is present in cost output but remains zero because capture planning is not authorized yet.
- Relationship data is supplied explicitly or loaded from the clearly marked synthetic fixture.
- There is no database, RAG, model provider, frontend, game adapter, save access, or mutation.
