# Loop 015 Codex Report: Explicit Minimum-New-Capture Route Ranking

## Command binding

- Program: `palnavi-ai-v1`
- Loop: `loop-015-explicit-capture-route-ranking`
- Target version: `1.0.0-alpha.15`
- Attempt: `1`
- Command nonce:
  `palnavi-ai-v1-loop-015-explicit-capture-route-ranking-command-001`
- Exact business base:
  `2e967bf21254ca06faf166aaf5ab719dfe55b135`
- Exact base tree:
  `854e4c60156f95471d1105f151c5830f4edf1bec`
- Work branch: `codex/loop-015-explicit-capture-route-ranking`
- Candidate Head and Tree: bound by the v2 business receipt after publication

## Implemented outcome

The backend adds the separate fixed-production endpoint:

```text
POST /api/v1/breeding/capture-ranked-routes
```

The request retains the accepted concrete target and owned-inventory shapes
and adds zero through sixteen explicit capture candidates. Candidate IDs and
species/gender states must be unique, candidate IDs cannot collide with owned
instance IDs, and candidate gender is always concrete. Unknown owned gender
retains the machine-readable `gender_required` outcome.

The planner searches state identities of stable species ID plus concrete
gender. Owned states begin with an empty capture set; user-supplied candidates
begin with their singleton candidate ID. It retains capture-set Pareto labels
and combines parent labels by exact set union. A label is dominated only by a
subset capture set whose generation, step count, and full stable signature are
all no worse. Equal-cardinality sets with different candidate members,
shallower/longer versus deeper/shorter route trade-offs, and
shallower/larger-signature versus deeper/smaller-signature trade-offs therefore
remain available for later combination.

Target results are ranked by distinct capture count, maximum generation depth,
breeding-step count, ordered candidate-ID tuple, and the full source-bound
route signature. The selected plan is reconstructed from the target
dependency graph, unused candidates are removed, and generation depths are
recalculated before response construction. Fixed per-state and total label
bounds return `search_limit_exceeded`; no approximate result is returned.
Because every combination is strictly no better than either parent under this
priority, the first current target label popped from the priority heap is the
exact global minimum and safely terminates a successful search.

The accepted owned-only planner is reused unchanged for zero-candidate
requests and for the zero-capture precheck. If a zero-capture route succeeds,
it outranks every hypothetical acquisition. Otherwise an explicitly allowed
target candidate returns one capture, zero generations, and zero breeding
steps.

Every success returns only submitted candidates actually used, with exact ID,
species, and gender values. `new_capture_count` equals the requirement length.
Probability-dependent cost remains explicitly unavailable and expected
attempts remain null.

## Truthful acquisition boundary

Every product response states:

```text
Capture candidates are user-supplied hypothetical individuals; PalNavi does
not verify catchability or encounter availability.
```

No catchability, encounter location, availability, rarity, capture
difficulty, sphere, time, probability, or recommendation score is inferred or
displayed. The new backend path does not contact a model, external service,
save file, game process, or browser storage.

## Frontend workflow

The Vue application adds an independent Capture-ranked workspace. It:

- shows the acquisition boundary before submission;
- accepts the concrete target, up to 299 owned rows, and up to 16 candidates;
- rejects incomplete rows, invalid IDs, duplicate candidate states, and
  owned/candidate ID collisions locally;
- lazily reuses the accepted 17-locale catalog for presentation only;
- normalizes unambiguous localized names such as Japanese `アヌビス` to stable
  ID `anubis`;
- preserves manual stable-ID entry if catalog loading fails;
- labels direct-target capture as a one-capture, zero-step outcome;
- distinguishes success, `gender_required`, `unreachable`,
  `search_limit_exceeded`, product invalid, request validation, transport
  invalid, and network failures;
- preserves immutable snapshots, latest-request-wins cancellation, retry, and
  disposal;
- renders all backend text inertly and collapses to a single-column layout at
  320 CSS pixels.

Candidates, inventory, locale, catalog data, and results remain component
memory only. Nothing is persisted to local storage, session storage,
IndexedDB, cookies, or a URL.

## Exactness and production evidence

Focused regressions prove:

- zero candidates reproduce the accepted owned-only Wixen Noct route;
- an allowed target candidate produces one capture and zero steps when no
  zero-capture route exists;
- one capture outranks a shorter two-capture route;
- equal-cardinality `{a}` and `{b}` labels remain distinct so later reuse of
  `{b}` reduces a two-capture union to one;
- two equal-three-step labels with the same capture set retain a
  generation-three route with the smaller full signature beside a
  generation-two route with the larger signature, so later generation
  equalization cannot worsen the exact stable optimum;
- source-bound step order is deterministic across repeated runs;
- the real Dumud male plus owned Katress Ignis female and Wixen female route
  uses exactly `capture-dumud`, produces Katress, and then preserves the
  directed Katress male plus Wixen female result;
- unknown owned gender, duplicate IDs, duplicate candidate states, ID
  collisions, unknown candidate gender, excess candidates, unknown keys, and
  label-bound overflow fail closed.

The first independent control review exposed a generation-equalization
counterexample in the original lexicographic dominance rule: a shallower
seven-step shared parent incorrectly pruned a deeper four-step parent,
worsening the final route from ten to thirteen steps. The componentwise
generation/step repair retained both labels and preserved the one-capture,
six-generation, ten-step optimum.

The second independent review exposed the remaining stable-signature case:
two same-capture-set, equal-three-step labels reached a shared state, with a
generation-two route carrying a larger signature and a generation-three route
carrying a smaller signature. A generation-three other parent equalized the
final cost, but the shallower intermediate label incorrectly pruned the exact
stable winner. Dominance now requires a no-worse full signature even when a
numeric dimension is strictly better. The new deep-only and expanded
regressions both return one capture, four generations, seven steps, and the
same smaller complete route signature.

Retaining that exact Pareto dimension initially expanded the production
search. Monotone target-label termination restores the performance boundary
without approximation: the real 44,851-rule one-candidate production route
completed in 3.35 seconds under a 60-second safety command.

## Validation results

Backend:

```text
python -m pytest
398 passed

python -m ruff format --check .
72 files already formatted

python -m ruff check .
All checks passed

python -m mypy src
Success: no issues found in 49 source files

timeout 60s python -m pytest \
  tests/test_capture_route_planning.py::test_one_explicit_candidate_unlocks_a_production_directed_route -q
1 passed in 3.35s
```

Frontend after a clean lockfile install:

```text
NPM_CONFIG_CACHE=/workspace/tools/cache/npm npm ci
added 115 packages

npm run test:unit:no-network
18 test files passed
272 tests passed

npm run type-check
passed

npm run build
passed

npm audit --audit-level=high
found 0 vulnerabilities
```

Repository:

```text
git diff --check
passed
```

Named command checks:

- `explicit-capture-candidate-boundary`: passed
- `minimum-new-capture-ranking`: passed
- `capture-set-pareto-search`: passed
- `direct-capture-result`: passed
- `stable-capture-tie-breaking`: passed
- `gender-directed-route-regressions`: passed
- `existing-production-route-byte-parity`: passed
- `localized-stable-id-capture-input`: passed
- `capture-request-race-cancellation`: passed
- `manual-capture-workflow`: passed
- `knowledge-workspace-regression`: passed
- `no-browser-persistence`: passed
- `no-unsupported-capture-claims`: passed
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

The accepted owned-only gender planner, application service, endpoint request
and response shapes, strict frontend client/runtime validator, Breeding
components and request controller, Loop 014 catalog client/controller,
production dataset repository, shared transport, synthetic planner, datasets,
data pipeline, samples, knowledge modules, configuration, workflows,
dependency manifests and lockfile, and golden fixture remain byte-identical to
the exact base.

Reverting the Loop 015 business commit removes the capture-ranked planner,
endpoint, workspace, tests, and documentation while restoring the exact
accepted Loop 014 product tree.

## Release and deployment

- Release: not requested; not created.
- Tag: not requested; not created.
- GitHub Release: not requested; not created.
- Deployment: not requested; not run.
- Health check: not applicable before a deployment target exists.

## Not included

No dataset change, catchability inference, map fact, rarity, difficulty,
capture probability, sphere cost, expected attempts, cake, incubation,
passive or IV inheritance, save integration, adapter, persistence, telemetry,
credential, proxy, external request, raw HTML, link generation, or model route
result was added.

## Residual risks and follow-up

Exact Pareto search is intentionally bounded. Adversarial candidate sets that
produce more labels than the fixed safety limits return
`search_limit_exceeded` instead of an approximation. Candidate availability
remains entirely user asserted until independently verified encounter data
exists.
