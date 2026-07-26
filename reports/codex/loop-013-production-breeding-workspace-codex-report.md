# Loop 013 Codex Report: Production Breeding Workspace

## Command binding

- Program: `palnavi-ai-v1`
- Loop: `loop-013-production-breeding-workspace`
- Target version: `1.0.0-alpha.13`
- Attempt: `2`
- Command nonce:
  `palnavi-ai-v1-loop-013-production-breeding-workspace-command-002`
- Exact business base: `988908d46fe8f3b32a37f0c6e7ce033d73745f73`
- Work branch: `codex/loop-013-production-breeding-workspace`

## Implemented outcome

The frontend now retains the synthetic Knowledge workspace as its default and
adds a visually and semantically separate verified-data Breeding workspace.
The breeding form submits only:

- the fixed accepted production dataset identity;
- one stable target species ID and a concrete male or female target gender;
- zero through 299 complete inventory rows with stable instance IDs, stable
  species IDs, and male, female, or unknown inventory gender;
- the fixed `minimum_generations` objective.

Local validation rejects invalid target, species, and instance identifiers,
incomplete rows, duplicate instance IDs, and inventory overflow before client
transport is invoked.

The dedicated breeding client uses the accepted shared same-origin transport.
It adds no API-base override and preserves credential omission, redirect
rejection, no-store behavior, response-byte limits, fatal UTF-8 decoding,
content-type validation, and abort support.

The breeding response decoder fails closed on:

- extra or missing object keys;
- incorrect dataset or content identities;
- invalid identifiers, genders, result kinds, SHA-256 values, or bounded
  arrays;
- nonempty passive or IV constraints;
- unordered, non-contiguous, duplicated, or generation-inconsistent steps;
- generated parents without a prior producing step;
- mismatched target, generation, breeding-step cost, or submitted inventory;
- probability-dependent cost claims or non-null expected attempts;
- inconsistent product status and HTTP status combinations;
- a `gender_required` result that does not name exactly the submitted unknown
  inventory instances.

The request controller deep-copies each submitted request, aborts replaced work,
ignores stale completion, retries the last immutable snapshot, and aborts on
disposal.

Unreachable responses are bound to the immutable submitted request before
presentation. Their unique generation-zero reachable species-and-gender keys
must exactly equal the unique concrete inventory species-and-gender keys, so a
stale or misrouted same-target response cannot add an unowned seed state or
omit an owned seed state.

The result panel presents success, zero-step already-owned success,
`gender_required`, `unreachable`, product-invalid, FastAPI-validation,
HTTP-contract, malformed-response, and network outcomes distinctly. Ordered
steps retain both gender-bound parents, child, generation, result kind, and
source-record hash. Dataset digests are placed in a secondary provenance
disclosure. Probability-dependent cost and unsupported mechanics remain
explicitly unavailable. Backend strings and identifiers use ordinary Vue text
interpolation only.

No player inventory persistence, URL serialization, telemetry, external
request, raw HTML rendering, dynamic evaluation, or credential path was added.

## Regression evidence

Frontend:

```text
npm ci
added 115 packages

npm run test:unit:no-network
12 test files passed
206 tests passed

npm run type-check
passed

npm run build
passed
```

The frontend suite includes the accepted two-generation production fixture,
zero-step success, every product outcome, FastAPI validation, malformed JSON,
wrong content type, oversized response, invalid UTF-8 marker, HTTP/status
conflicts, response-shape tampering, invalid and duplicate identifiers,
inventory overflow, request-bound unreachable generation-zero state closure,
latest-request-wins cancellation, retry, disposal, inert hostile text, and the
unchanged knowledge-workspace suite. The existing golden contract JSON remains
byte-identical.

Backend:

```text
python -m pytest
365 passed

python -m ruff format --check .
67 files already formatted

python -m ruff check .
All checks passed

python -m mypy src
Success: no issues found in 46 source files
```

Repository boundary:

```text
git diff --check
passed

allowed tracked and untracked paths
passed

backend, dataset, sample, configuration, production dependency, shared
transport, knowledge module, and golden-fixture rollback comparison to exact
base
passed

persistence, external URL, dynamic execution, raw HTML, console logging, and
credential scans over new runtime source and diff
passed
```

The dependency-manifest delta is limited to the exact direct development pin
and its mechanically generated lockfile graph. No production dependency or
other direct dependency changed.

## Attempt 2 audit remediation

Attempt 1 reported six high-severity findings in the pre-existing
development-only `@vue/test-utils -> js-beautify -> glob/minimatch ->
brace-expansion` chain. Attempt 2 applies the control-authorized exact pin:

```text
@vue/test-utils: 2.4.11 -> 2.2.7
```

The lockfile delta was generated from the updated direct pin and removes only
the obsolete test-utility dependency subtree. A clean lockfile installation
followed by the exact required audit now passes:

```text
npm ci
added 115 packages

npm audit --audit-level=high
found 0 vulnerabilities
```

The complete 206-test frontend suite, strict type check, production build, and
all backend gates pass after the clean install. No audit exception is claimed.

## Rollback

The change is frontend-only. Reverting the Loop 013 business commit removes the
Breeding workspace and leaves the accepted Loop 012 endpoint, backend tree,
production datasets, configuration, production dependency graph, shared
transport, synthetic Knowledge workspace modules, and golden contracts
unchanged. It also restores the prior development-test utility version and its
lockfile subtree.
