# Loop 016 Codex Report: PalNavi AI v1 Release Candidate

## Command binding

- Program: `palnavi-ai-v1`
- Loop: `loop-016-v1-release-candidate`
- Target version: `1.0.0-rc.1`
- Attempt: `1`
- Command nonce:
  `palnavi-ai-v1-loop-016-v1-release-candidate-command-001`
- Exact business base:
  `ec2e11ab3a836868c9989410e041bd857acf65ad`
- Exact base tree:
  `be5c3e9f510dd7d0bcf1fb7eb636074ab0f7fded`
- Work branch: `codex/loop-016-v1-release-candidate`
- Candidate Head and Tree: bound by the v2 business receipt after publication

## Candidate outcome

The source tree now carries one public release identity,
`1.0.0-rc.1`. Python distribution metadata uses the PEP 440 equivalent
`1.0.0rc1`; the runtime package, FastAPI OpenAPI document, frontend package,
frontend lockfile root, README, release manifest, and human acceptance package
use the public version.

`release/v1.0.0-rc.1.json` is the strict machine-readable product boundary. It
binds the accepted production dataset ID and SHA-256 content identity, record
and outcome counts, game-version scope, 17 presentation locales, eight-route
API surface, supported and unsupported capabilities, local source
distribution mode, verification commands, and the human-decision requirement.

`scripts/verify_v1_release_candidate.py` locates the repository from its own
path, reads only repository artifacts, enumerates the in-process OpenAPI
surface, and produces deterministic JSON. It performs no network request,
shell execution, write, credential lookup, or dynamic code evaluation. It
fails closed on missing files or drift in identity, manifest, data, locale, or
API facts.

`docs/v1-acceptance.md` provides Windows-first and portable setup, synthetic
knowledge preparation, two-process loopback startup, four representative
product scenarios, supported and unsupported tables, residual risks, rollback,
and an explicit human accept-or-reject checklist. It does not claim a final
release, installer, signed binary, game integration, or remote deployment.

## Validation results

Release verification:

```text
python scripts/verify_v1_release_candidate.py
status: verified
product version: 1.0.0-rc.1
Python package version: 1.0.0rc1
dataset: palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47
API routes: 8
network required: false

python -m pytest backend/tests/test_release_candidate.py -q
6 passed in 0.48s
```

The focused suite covers the exact candidate plus isolated version, dataset,
release-manifest, API-surface, and missing-document failures.

Backend:

```text
python -m pytest
406 passed in 48.76s

python -m ruff format --check .
73 files already formatted

python -m ruff check .
All checks passed

python -m mypy src
Success: no issues found in 49 source files
```

Frontend after a clean lockfile install:

```text
npm ci
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

Repository and release boundaries:

```text
git diff --check
passed

allowed paths
11 of 11 exact; no missing or extra path

dependency graph
byte-equivalent after removing only top-level and root-package version fields

rollback boundary
every non-allowed Git object unchanged from the exact base

sanitized scans
passed for secrets, credentials, network primitives, persistence, dynamic
execution, raw HTML, VPS-only instructions, and premature final-release claims
```

Named command checks:

- `release-identity-consistency`: passed
- `supported-data-manifest`: passed
- `release-verifier-positive`: passed
- `release-verifier-negative`: passed
- `api-surface-identity`: passed
- `human-acceptance-package`: passed
- `local-run-and-rollback-runbook`: passed
- `no-premature-final-release-claim`: passed
- `backend-tests`: passed
- `frontend-offline-tests`: passed
- `frontend-type-check`: passed
- `frontend-build`: passed
- `npm-audit`: passed
- `ruff-format`: passed
- `ruff-lint`: passed
- `strict-mypy`: passed
- `dependency-graph-parity`: passed
- `diff-check`: passed
- `allowed-paths`: passed
- `rollback-boundary`: passed
- `sanitized-scans`: passed

## Rollback and unchanged boundaries

The release loop is limited to eleven paths. Every planner, application
service, repository, API route and schema, frontend source and test, dataset,
pipeline, knowledge artifact, configuration file, workflow, provider,
transport, and dependency declaration remains an exact rollback target from
base commit `ec2e11ab3a836868c9989410e041bd857acf65ad`.

Only the root frontend package version values may change in the lockfile; the
dependency graph must remain byte-equivalent after ignoring those two values.

## Release and deployment

- Candidate form: source checkout.
- Final release: not created.
- Tag: not created.
- Installer or signed binary: not created.
- Remote deployment: not applicable.
- Local health evidence: covered by the API suite, offline verifier, and human
  acceptance scenario.

## Residual risks

- The production dataset is explicitly scoped to its reviewed game versions.
- Explicit-capture search returns `search_limit_exceeded` at deterministic
  safety bounds rather than an approximation.
- Catchability and other acquisition facts remain user assertions.
- Production knowledge prose, probability costs, passives, IVs, time, cake,
  save access, game adapters, and automation remain unsupported.
- A source checkout still requires reviewed local Python and Node toolchains;
  packaging and remote hosting remain future work.
