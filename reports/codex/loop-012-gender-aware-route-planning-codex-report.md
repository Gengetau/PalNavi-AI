# Loop 012 Codex Report: Gender-Aware Route Planning

## Result

Implemented a separate production-backed endpoint at
`POST /api/v1/breeding/gender-aware-routes`. It searches immutable,
gender-capable route states over the accepted 299-species, 44,851-rule
Palworld snapshot.

The accepted business base was
`b293a6baf52c7699fe092038f2911c7d9ca5ffcb`. Work was limited to the Loop 012
allowlist. No dataset artifact, frontend source, workflow, configuration,
release, deployment, or legacy planner file changed.

## Domain and search behavior

- Added concrete inventory candidates with stable instance ID, species ID, and
  `male | female | unknown` gender.
- Added route states containing species, concrete gender requirement, immutable
  empty passive and IV constraint dimensions, and generation depth.
- Added production route steps containing both gender-bound parents, child
  state, generation, result kind, and source-record SHA-256.
- Added a deterministic route search ordered by maximum generation, breeding
  step count, and stable source-bound signature.
- Kept directed rules out of unordered canonicalization. The two
  Katress/Wixen rules remain separate.
- Treated produced states as repeatable planning capabilities, matching the
  existing species-availability model without claiming inventory counts or
  consumption.
- Returned `gender_required` before graph matching when any inventory gender is
  explicitly `unknown`.
- Returned structured `success`, `gender_required`, `unreachable`, and
  `invalid` results.

## Probability and data boundary

The production repository now locates the accepted 299-record gender document
by its manifest-bound SHA-256 and validates:

- exact document and record shapes;
- exact 299-species coverage and canonical order;
- numeric values excluding booleans;
- finite values in `(0, 1]`;
- exact male/female sum to one;
- positive male and female feasibility for every accepted species.

The planner uses these values only as a non-zero feasibility gate for future
offspring genders. Responses explicitly return
`probability_dependent_cost_available: false` and
`expected_attempts: null`. No 50:50 assumption or probability-weighted route
cost was added.

## Production regression

The accepted production graph deterministically finds this two-generation
route:

```text
dumud male + katress_ignis female
  -> katress male
katress male + wixen female
  -> wixen_noct female
```

The first step is the exact ordinary-power rule with source record
`4b732cb09f3c3e97426c5e2685a4f15cf3db0114055ab6c3bfd546d22a0ddd8a`.
The second is the exact directed rule with source record
`9da3059bdaa87c8a40b9446c72004720b18f41ad8370dabf23688eb0ce944452`.

An exhaustive route-graph test expands every one of the 44,849 non-directed
rules into both opposite-gender parent orientations and both feasible child
genders, preserving child identity and source hash. Existing direct-query
tests continue to validate all 44,849 rules in both parent orders and both
query modes.

## API and compatibility

- Added strict Pydantic request and response contracts plus frontend golden
  fixtures.
- Target gender must be concrete `male | female`.
- Inventory gender must be explicitly present as
  `male | female | unknown`; omitted, null, and unrecognized values fail
  request validation.
- Duplicate or malformed instance IDs fail closed.
- Every repository-backed response binds the accepted main and gender-data
  content identities.
- The legacy `POST /api/v1/breeding/routes` endpoint, its
  `BreedingRoutePlanner`, application service, fixtures, and response contract
  are unchanged byte for byte.

## Validation evidence

- Backend: 365 tests passed.
- Exhaustive production graph: all 44,849 non-directed rules and both directed
  rows covered.
- Ruff format and lint: passed.
- Strict mypy: 46 source modules passed.
- Frontend: 136 tests passed with network blocked.
- Frontend TypeScript: passed.
- Frontend production build: passed.
- npm audit at high threshold: 0 vulnerabilities.
- Loop 008 dataset offline validation: passed.
- Loop 010 gender-data offline validation: passed.
- `git diff --check`: passed.
- Allowed-path, legacy rollback, dataset immutability, sanitized-message, and
  secret-pattern scans: passed.

The initial frontend clean install attempted the environment-default
`/root/.npm` cache and failed before tests. It was rerun successfully with
`NPM_CONFIG_CACHE=/workspace/tools/cache/npm`; the incomplete generated
`node_modules` tree was removed after the successful install. No lockfile or
source file changed during that recovery.

## Remaining non-goals

This loop does not implement expected attempts, probability-weighted route
cost, inventory persistence or consumption, passive or IV inheritance,
mutation, cakes, incubation, partner skills, ranch outputs, frontend planning,
save-file reading, release, or deployment.
