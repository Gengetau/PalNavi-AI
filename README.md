# PalNavi AI

PalNavi AI is a local-first, version-aware Palworld assistant. Its long-term focus is
explainable planning that combines verified game data with a player's own context.

This repository currently contains a **foundation prototype**. It proves that breeding
routes can be calculated by a deterministic, typed domain service and exposed through a
small local API. It does not contain an AI model integration, RAG, game-process access,
save parsing, or real Palworld breeding data.

## What is implemented

- framework-independent species, relationship, inventory, request, step, cost, and result models;
- deterministic direct and multi-generation route planning;
- stable tie-breaking, cycle safety, invalid-input results, and unreachable results;
- a FastAPI health endpoint and breeding-route endpoint;
- fictional synthetic data and automated domain/API tests.

Exact breeding outcomes must always come from versioned structured data and deterministic
tools. A future language-model layer may interpret requests or explain a returned route,
but it must not invent relationships, probabilities, or costs.

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
python -m ruff check .
python -m mypy src
```

Start the API:

```powershell
python -m uvicorn palnavi.api.main:app --reload
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs`. Health is available
at `GET /health`; route planning is available at `POST /api/v1/breeding/routes`.

## Synthetic data warning

`samples/synthetic-breeding-data.json` is deliberately fictional test data. Identifiers
such as `pal_a` and `pal_b` are neutral placeholders and must never be presented as facts
about Palworld. Production data will require a separately reviewed, versioned provenance
contract and import process.

See [docs/architecture.md](docs/architecture.md) and
[docs/data-contracts.md](docs/data-contracts.md) for the current boundaries and schemas.
