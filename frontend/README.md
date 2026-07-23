# PalNavi AI Frontend

This package is the standalone Vue 3 and TypeScript interface for the local PalNavi knowledge
services. It is intentionally synthetic-first: **Synthetic knowledge only** is enabled and visibly
labeled by default, and the current repository does not contain reviewed real Palworld knowledge.

## Requirements

- Node.js `^22.18.0` or `>=24.12.0`
- npm 11 (the lockfile was produced with npm 11.9.0)
- the PalNavi FastAPI service when testing browser-to-backend integration

Install the exact lockfile dependencies:

```bash
npm ci
```

Run the frontend:

```bash
npm run dev
```

Vite proxies the relative `/api` path to `http://127.0.0.1:8000` during development. Start the
FastAPI application separately from `backend/`:

```bash
python -m uvicorn palnavi.api.main:app --reload
```

The browser client has no configurable remote API base. Production deployments must serve the
frontend and `/api/v1` routes behind the same origin.

## Checks

```bash
npm run test:unit
npm run test:unit:no-network
npm run type-check
npm run build
```

`npm run check` runs all three gates. Unit and component tests inject deterministic fake clients or
transports, replace global `fetch` with a rejecting guard, and make no live HTTP request. The
explicit no-network variant additionally blocks TCP, TLS, HTTP, DNS, UDP, and subprocess APIs
before Vitest starts.

## Current workflow

The one-page workspace supports:

- deterministic `POST /api/v1/knowledge/search`;
- retrieval-first `POST /api/v1/knowledge/explain`;
- query, optional language, optional exact-version, bounded-limit, and synthetic-only controls;
- explicit loading, empty, unsupported, backend-error, invalid-response, and network states;
- request replacement with abort plus a latest-response-wins guard;
- canonical citation details and optional sanitized token usage;
- retrying the last request without clearing form input.

Knowledge search does not require model configuration. Explanation may require an optional provider
configured locally in the backend; the browser never asks for or stores a provider key or endpoint.

## Safety boundary

Backend answers, result text, titles, IDs, locators, and error messages are untrusted text. The UI
does not parse Markdown or HTML, does not use `v-html`, and does not turn source locators into links.
All locators remain inert code text.

The frontend does not access a game installation, game process, save, mod loader, or multiplayer
session. It contains no game artwork, external fonts, analytics, trackers, or CDN runtime assets.
Real Palworld data remains unavailable until a separate provenance review and versioned import are
accepted.
