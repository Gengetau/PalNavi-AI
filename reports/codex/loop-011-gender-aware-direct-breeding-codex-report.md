# Loop 011 Business Execution Report

## Identity

- Loop: `loop-011-gender-aware-direct-breeding`
- Target version: `1.0.0-alpha.11`
- Command nonce:
  `palnavi-ai-v1-loop-011-gender-aware-direct-breeding-command-001`
- Business repository: `Gengetau/PalNavi-AI`
- Exact base: `b9d0617bc28b0013645bc7ccaf9e210ad597f1e9`
- Work branch: `codex/loop-011-gender-aware-direct-breeding`

## Delivered behavior

The implementation adds a read-only production direct-breeding boundary without changing the
existing multi-generation planner:

- typed `GenderConstraint`, `InventoryGender`, source-bound `BreedingRule`, request, result, and
  possibility models;
- separate unordered wildcard and fully qualified directed indexes;
- preservation of both Katress/Wixen results with species and gender kept on the same parent;
- a fail-closed repository for the exact accepted 299-species and 44,851-outcome dataset;
- validation of the accepted gender-data manifest and all files it binds without parsing or
  activating stored-only probability and native-field records;
- an application service and `POST /api/v1/breeding/direct` adapter;
- concrete and explicit species-only request shapes;
- stable `success`, `gender_required`, `invalid`, and `not_found` responses;
- shared backend/frontend golden response fixtures;
- runtime and API documentation.

## Exact data checks

The repository requires:

- main manifest SHA-256
  `23fb56cb7715a7c2d57872983bc4396e6d1cc47527d84cf27ff107dc9858fb45`;
- main content SHA-256
  `b7fbe9b7395d2aef6758ff162da8fb738cf1fcd3ec5c7d50133c3d5edafdd30b`;
- gender-data manifest SHA-256
  `362dbcfafe3b6e5cd2f92493bba3ce8953d29541fd8312fdc227b17704114325`;
- gender-data content SHA-256
  `11173754c8dcf123df6be22823210d80f9b866732cbff80f112c70ba8208cfdf`.

Before returning an immutable snapshot it validates all manifest-bound byte lengths and hashes,
30 ordered outcome shards, 299 unique and canonically ordered species, 44,851 unique source
record hashes, all species references, result-kind counts, the native acquisition lock, and the
exact two directed rows.

Tamper tests cover the main manifest, a bound shard, a source-record hash, a species reference, a
directed child, a gender-data output, and the acquisition lock. Every mutation returns one
sanitized `DatasetInvalid` result.

## Query parity

The exhaustive domain test performs four queries for each of the 44,849 non-directed rows:

1. source parent order as a species-only query;
2. reversed parent order as a species-only query;
3. source parent order with concrete male/female parents;
4. reversed parent order with concrete female/male parents.

Every query preserves the source child, result kind, and source-record hash. The two directed
rows are tested in all four species/gender input orientations. Species-only Katress/Wixen returns
both possible children in stable request-relative order. Known same-gender parents are invalid,
and `unknown` never satisfies a concrete rule.

## API validation

Concrete requests require explicit `male`, `female`, or `unknown` values on both parents.
Omitted, explicit `null`, and unrecognized values fail FastAPI validation. Species-only lookup
requires explicit `query_mode: "species_only"` and omission of both gender properties; any
gender property in that mode is invalid.

Repository errors expose only stable categories and messages. Raw paths and exception text do
not cross the API boundary.

## Verification

Completed checks:

- backend: 349 tests passed;
- exhaustive non-directed parity: 44,849 rows passed in both parent orders and both query modes;
- directed preservation: two source rows and four concrete orientations passed;
- Ruff formatting check: passed;
- Ruff lint: passed;
- strict mypy: passed for all 44 source modules;
- frontend offline unit tests: 136 passed;
- frontend TypeScript check: passed;
- frontend production build: passed;
- npm audit at high severity: zero vulnerabilities;
- main dataset offline validator: passed;
- gender-data offline validator: passed;
- `git diff --check`: passed;
- forbidden-path rollback boundary: passed;
- changed-content credential, private-key, caller-path, and temporary-path scan: passed.

## Preserved rollback boundary

The implementation does not modify:

- `datasets/**`;
- `samples/**`;
- `backend/src/palnavi/domain/breeding/planner.py`;
- the existing route request, route response, or synthetic repository;
- `frontend/src/**`;
- workflow, configuration, release, or deployment files.

Reverting the new direct endpoint and its dependencies leaves the prior synthetic route runtime
intact. No probability-dependent cost, mutable inventory, multi-generation gender planning,
frontend planning workflow, unsupported mechanics, or save-file access was added.
