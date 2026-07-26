# PalNavi AI Frontend

This package is the standalone Vue 3 and TypeScript interface for local PalNavi services. It is
intentionally synthetic-first: **Synthetic knowledge only** is enabled and visibly labeled by
default, and the repository does not contain reviewed real Palworld knowledge prose. A separate
Breeding workspace consumes the fixed, reviewed production breeding endpoint without mixing
structured game data into the synthetic knowledge corpus.

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
frontend and `/api/v1` routes behind the same origin. Requests explicitly omit browser credentials.

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

## Current workspaces

The default Knowledge workspace supports:

- deterministic `POST /api/v1/knowledge/search`;
- retrieval-first `POST /api/v1/knowledge/explain`;
- query, optional language, optional exact-version, bounded-limit, and synthetic-only controls;
- explicit loading, empty, unsupported, backend-error, invalid-response, and network states;
- request replacement with abort plus a latest-response-wins guard;
- immutable display and announcement of the scope submitted with each request;
- canonical citation details and optional sanitized token usage;
- retrying the last request without clearing form input.

Knowledge search does not require model configuration. Explanation may require an optional provider
configured locally in the backend; the browser never asks for or stores a provider key or endpoint.

The separate Breeding workspace supports:

- fixed-dataset `POST /api/v1/breeding/gender-aware-routes`;
- a concrete target species ID and gender;
- zero through 299 explicit inventory rows with stable instance IDs, species IDs, and known or
  unknown genders;
- local rejection of incomplete rows, invalid IDs, duplicate instance IDs, and overflow before
  transport activity;
- distinct success, `gender_required`, `unreachable`, product-invalid, FastAPI-validation,
  invalid-response, and network states;
- deterministic ordered route steps, generation and breeding-step costs, source-record hashes,
  and accepted dataset identities;
- immutable submitted-request snapshots, latest-request-wins cancellation, retry, and disposal
  abort behavior.

Species IDs are stable internal identifiers in this alpha. There is no bundled species catalogue,
display-name lookup, or user-editable dataset identity.

## Safety boundary

Backend answers, result text, titles, IDs, locators, and error messages are untrusted text. The UI
does not parse Markdown or HTML, does not use `v-html`, and does not turn source locators into links.
All locators, breeding identifiers, source hashes, and backend messages remain inert text.
Response bodies are byte-bounded and decoded as strict UTF-8; malformed encoding, unexpected
HTTP/status combinations, extra or contradictory fields, unaccepted dataset identities, and
results that violate submitted request scope fail closed.

The frontend does not access a game installation, game process, save, mod loader, or multiplayer
session. It contains no game artwork, external fonts, analytics, trackers, or CDN runtime assets.
It never persists inventory in local storage, session storage, IndexedDB, cookies, or URLs.
Production structured breeding data is available only through the fixed same-origin read-only
endpoint; verified knowledge prose remains unavailable.
