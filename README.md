# PalNavi AI

PalNavi AI is a local-first, version-aware Palworld assistant. Its long-term focus is
explainable planning that combines verified game data with a player's own context.

This repository currently contains a **foundation prototype**. It proves that breeding
routes can be calculated from a validated, versioned dataset by a deterministic typed
domain service and exposed through a small local API. It also provides deterministic local
knowledge retrieval and an optional retrieval-first, citation-grounded explanation endpoint
through provider-neutral, non-streaming model adapters. The explanation path remains disconnected
from route planning. It does not contain broad model orchestration, game-process access, save
parsing, or real Palworld breeding or knowledge data.

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
versioned knowledge data is imported. The current explanation endpoint supports only fictional
synthetic evidence.

Model provider setup, security boundaries, and the explicit live smoke command are documented
in [docs/model-providers.md](docs/model-providers.md). Knowledge ingestion, local database setup,
and filtering behavior are documented in
[docs/knowledge-retrieval.md](docs/knowledge-retrieval.md). See
[docs/architecture.md](docs/architecture.md) and
[docs/data-contracts.md](docs/data-contracts.md) for the current boundaries and schemas.
Dataset authors should also follow
[docs/dataset-maintenance.md](docs/dataset-maintenance.md).
