# Loop 014 Codex Report: Version-Bound Localized Species Catalog

## Command binding

- Program: `palnavi-ai-v1`
- Loop: `loop-014-versioned-species-catalog`
- Target version: `1.0.0-alpha.14`
- Attempt: `1`
- Command nonce:
  `palnavi-ai-v1-loop-014-versioned-species-catalog-command-001`
- Exact business base:
  `129cb660c557338a5d4c3774cee165fa62ba27a3`
- Exact base tree:
  `743d38e99079456fe6dab52f49be5a6fb385109f`
- Work branch: `codex/loop-014-versioned-species-catalog`
- Candidate Head and Tree: bound by the v2 business receipt after publication

## Implemented outcome

The backend now exposes:

```text
GET /api/v1/palworld/species-catalog?dataset_id=<stable-id>
```

The fixed catalog is loaded only from the accepted
`palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47` artifacts. Before returning
records, the repository validates the complete production breeding snapshot,
the exact manifest and generated-file identities, exact `pals.json` envelope
and record keys, 299 stable species IDs, 17 exact locale tags, bounded nonempty
names, Paldeck metadata, variant flags, source-record hashes, source internal
name uniqueness, source hash uniqueness, and equality with the accepted
breeding species set.

The success response is stable-ID sorted and exposes only:

- stable species ID;
- Paldeck number and optional suffix;
- variant flag;
- the exact 17-name localization map;
- source-record SHA-256.

It does not expose source internal names, breeding power, probability,
statistics, skills, ranch outputs, raw dataset fields, or filesystem paths.
Unknown datasets return deterministic `not_found`; invalid stored data returns
deterministic `invalid`; neither path substitutes another dataset or a partial
catalog.

The Vue Breeding workspace lazily loads the fixed catalog only when that
workspace is mounted. It defaults display locale to `en`, exposes all 17 exact
locale tags, and provides one native bounded datalist shared by target and
inventory fields. Options render exact localized name plus stable ID as inert
Vue text. Selecting an option or entering an unambiguous exact localized name
normalizes the field to the stable ID before the unchanged Loop 013 request is
built.

Catalog loading has its own abortable latest-request-wins controller. A
replacement aborts and supersedes older work; component disposal aborts active
work. Catalog failure presents an accessible warning, preserves manual
stable-ID entry, and never starts a breeding request. Locale, catalog, entry
text, and inventory remain memory-only and are not written to browser storage,
cookies, or URLs.

## Exact reconstruction evidence

The API regression reads the accepted `pals.json`, reconstructs all 299 public
records using only the allowed fields, sorts by stable species ID, and compares
the complete response byte values field-for-field. It also confirms the JSON
body is below the accepted 1 MiB response limit.

The Anubis record remains:

```text
stable ID: anubis
en: Anubis
ja: アヌビス
zh-Hans: 阿努比斯
zh-Hant: 阿努比斯
source SHA-256:
16fa84241baad9b7a23f3717a3f5dd03c9f1834daa2940e6a1ba8210ed920fb4
```

Focused fail-closed regressions cover malformed source shape, duplicate stable
ID, duplicate source internal name, missing locale, invalid source hash, and a
catalog/breeding species-set mismatch.

## Validation results

Backend:

```text
python -m pytest
376 passed

python -m ruff format --check .
69 files already formatted

python -m ruff check .
All checks passed

python -m mypy src
Success: no issues found in 47 source files
```

Frontend:

```text
npm ci --cache /workspace/tools/cache/npm
added 115 packages

npm run test:unit:no-network
14 test files passed
239 tests passed

npm run type-check
passed

npm run build
passed

npm audit --audit-level=high --cache /workspace/tools/cache/npm
found 0 vulnerabilities
```

The first clean-install attempt used npm's inaccessible default `/root/.npm`
cache and failed before tests. Re-running the same lockfile installation with
the workspace's writable rebuildable cache succeeded; no dependency manifest
or lockfile changed.

Named command checks:

- `exact-catalog-identities`: passed
- `complete-localization-map`: passed
- `catalog-breeding-species-parity`: passed
- `strict-catalog-response-validation`: passed
- `localized-stable-id-submission`: passed
- `catalog-request-cancellation`: passed
- `manual-id-fallback`: passed
- `breeding-workspace-regression`: passed
- `knowledge-workspace-regression`: passed
- `no-browser-persistence`: passed
- `offline-frontend-tests`: passed
- `backend-tests`: passed
- `frontend-tests`: passed
- `frontend-type-check`: passed
- `frontend-build`: passed
- `npm-audit`: passed
- `ruff-format`: passed
- `ruff-lint`: passed
- `strict-mypy`: passed
- `diff-check`: passed
- `allowed-paths`: passed
- `rollback-boundary`: passed
- `sanitized-scans`: passed

## Rollback and unchanged boundaries

The production datasets, data pipeline, samples, knowledge modules,
configuration, GitHub workflows, dependency manifests and lockfile, breeding
planners, breeding request and response contracts, shared transport, Loop 013
request controller and runtime response validator, and golden fixtures remain
byte-identical to the exact base.

Reverting the Loop 014 business commit removes the catalog endpoint, catalog
client/controller, localized suggestion UI, tests, and documentation while
restoring the exact accepted Loop 013 product tree.

## Release and deployment

- Release: not requested; not created.
- Tag: not requested; not created.
- GitHub Release: not requested; not created.
- Deployment: not requested; not run.
- Health check: not applicable before a deployment target exists.

## Not included

No dataset rewrite, translation, inferred name, fuzzy alias table, art,
external request, recommendation score, probability, cost, passive
inheritance, cake, incubation, save integration, persistence, telemetry,
credential, proxy, planner change, or game integration was added.

## Residual risks and follow-up

The suggestion UI intentionally relies on the browser's accessible native
`datalist`; visual styling and exact presentation vary by browser. The manual
stable-ID path remains available if catalog loading or native suggestion
presentation is unavailable. Fuzzy matching and alias resolution remain
explicitly out of scope.
