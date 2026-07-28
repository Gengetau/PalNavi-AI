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
- lazy fixed-dataset `GET /api/v1/palworld/species-catalog` loading with all 17 exact source
  locales and one shared target/inventory suggestion list;
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

The separate Capture-ranked workspace supports:

- fixed-dataset `POST /api/v1/breeding/capture-ranked-routes`;
- zero through sixteen explicit, concrete capture candidates with collision and duplicate-state
  validation;
- exact minimum-distinct-capture ranking before generations, breeding steps, and stable
  source-bound tie breaks;
- a visible statement that candidates are user supplied and catchability is not verified;
- distinct direct-target, `gender_required`, `unreachable`, `search_limit_exceeded`, invalid,
  transport-failure, and network states;
- the same lazy localized suggestions and manual stable-ID fallback without changing the accepted
  Breeding request controller.

Localized names are presentation-only. Selecting a suggestion or entering one unambiguous exact
localized name normalizes the field to its stable species ID, and only that stable ID enters the
immutable breeding request. Catalog failure leaves an explicit manual-ID fallback and never
submits a route request. There is no bundled roster, fuzzy alias table, translated fallback, or
user-editable dataset identity.

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
It also never persists capture candidates, results, locale choice, catalog data, or species entry
text.
Production structured breeding data is available only through the fixed same-origin read-only
endpoint; verified knowledge prose remains unavailable.
