# PalNavi AI

PalNavi AI is a local-first, version-aware Palworld assistant. Its long-term focus is
explainable planning that combines verified game data with a player's own context.

This repository currently contains a **foundation prototype**. It proves that breeding
routes can be calculated from a validated, versioned dataset by a deterministic typed
domain service and exposed through a small local API. It also provides deterministic local
knowledge retrieval and an optional retrieval-first, citation-grounded explanation endpoint
through provider-neutral, non-streaming model adapters. The explanation path remains disconnected
from route planning. A reviewed Palworld v1 static breeding dataset is now stored in the
repository but is not activated because the current species-only planner cannot safely represent
its gender-directed pair. The application does not contain broad model orchestration, game-process
access, save parsing, or production-searchable Palworld knowledge prose.

## What is implemented

- framework-independent species, relationship, inventory, request, step, cost, and result models;
- deterministic direct and multi-generation route planning;
- stable tie-breaking, cycle safety, invalid-input results, and unreachable results;
- immutable dataset metadata with classification, game-version scope, provenance, validation
  status, and a verified SHA-256 content identity;
- a read-only repository protocol and validated local JSON implementation;
- a FastAPI health endpoint and breeding-route endpoint;
- asynchronous model contracts and offline-tested OpenAI, Anthropic, DeepSeek, Zhipu,
  Bailian, and custom OpenAI-compatible adapters;
- deterministic Markdown ingestion, citation-ready SQLite knowledge storage, lexical retrieval,
  and a read-only knowledge search endpoint;
- a retrieval-first `POST /api/v1/knowledge/explain` endpoint with bounded evidence, canonical
  retrieval-owned citations, and fail-closed validation of untrusted model text;
- a standalone Vue 3 and TypeScript knowledge workspace that defaults visibly to synthetic-only,
  preserves typed search and explanation outcomes, and renders backend content as inert text;
- a deterministic registry of exact official source URLs plus a credential-free, metadata-only
  fingerprint boundary with a mandatory synthetic mock fallback;
- an exact-source, MIT-attributed Palworld v1 dataset with 299 calculation records and 44,851
  normalized outcomes, stored but not yet enabled for runtime planning;
- a deterministic native Linux-server acquisition lock that binds exact Steam Build, depot
  manifest, PAK, acquisition tool, extractor dependency graph, and a successful no-mappings
  probe without committing proprietary game bytes;
- versioned fictional synthetic data and automated domain/import/repository/API tests.

Exact breeding outcomes must always come from versioned structured data and deterministic
tools. Explanation model output is untrusted, may summarize only retrieved evidence, and never
becomes the source of truth for deterministic mechanics. It must not invent relationships,
probabilities, or costs.

## Local development

Python 3.12 or newer is required. From the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On shells where `py` is unavailable, use `python3.12` or another Python 3.12+ executable.

Run all checks:

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy src
```

The standalone frontend requires Node.js `^22.18.0` or `>=24.12.0`. From the repository root:

```powershell
cd frontend
npm ci
npm run test:unit
npm run type-check
npm run build
```

For local browser development, start the FastAPI service on `127.0.0.1:8000`, then run
`npm run dev` in `frontend/`. Vite proxies the same-origin `/api` path during development. See
[frontend/README.md](frontend/README.md) for the complete workflow and safety boundary.

Start the API:

```powershell
python -m uvicorn palnavi.api.main:app --reload
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs`. Health is available
at `GET /health`; route planning is available at `POST /api/v1/breeding/routes`; citation-ready
retrieval is available at `POST /api/v1/knowledge/search`; and grounded explanations are available
at `POST /api/v1/knowledge/explain`.

## Synthetic data warning

`samples/datasets/synthetic-v1/` is deliberately fictional test data. Identifiers such as
`pal_a` and `pal_b` are neutral placeholders and must never be presented as facts about
Palworld. Its manifest explicitly claims no real game version and uses only project-authored
synthetic provenance.

The dataset schema version describes this application's contract; it is not a Palworld
version. The stable dataset identifier is independent from its directory, provenance is
independent from validation status, and the SHA-256 digest identifies the canonical metadata,
provenance, and relationship content rather than trusting a filename. A future production dataset must use explicit game
version applicability and separately reviewed, permission-compatible provenance.

Real Palworld knowledge answers remain unavailable until permission-compatible, reviewed,
versioned knowledge documents are imported. Structured breeding data is present separately but
is not an explanation corpus or the current planner default. The explanation endpoint supports
only fictional synthetic evidence. The frontend keeps **Synthetic knowledge only** enabled and
visibly labeled by default and does not claim that its fixtures represent verified game facts.

Model provider setup, security boundaries, and the explicit live smoke command are documented
in [docs/model-providers.md](docs/model-providers.md). Knowledge ingestion, local database setup,
and filtering behavior are documented in
[docs/knowledge-retrieval.md](docs/knowledge-retrieval.md). See
[docs/architecture.md](docs/architecture.md) and
[docs/data-contracts.md](docs/data-contracts.md) for the current boundaries and schemas.
Dataset authors should also follow
[docs/dataset-maintenance.md](docs/dataset-maintenance.md).
The reviewed Palworld source locks, normalized data schema, known gaps, and activation boundary
are documented in [docs/palworld-data.md](docs/palworld-data.md).
The exact native server acquisition procedure, offline validator, probe result, and
client-claim limits are documented in
[docs/palworld-native-acquisition.md](docs/palworld-native-acquisition.md).
Official-source registry governance, content-free snapshots, the mock-default CLI, and the
single-attempt live boundary are documented in
[docs/official-sources.md](docs/official-sources.md). Registering or fingerprinting an official
source does not approve its page body for knowledge ingestion or factual answers.
