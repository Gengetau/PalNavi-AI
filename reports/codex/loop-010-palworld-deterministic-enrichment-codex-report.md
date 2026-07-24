# Loop 010 Codex Report: Palworld Deterministic Enrichment

## Scope

Implemented control command
`palnavi-ai-v1-loop-010-deterministic-enrichment-command-001` on exact business
baseline `d258c9f156c9ec602ea3df97d40cdde462a91b82`.

The change creates a deterministic, provenance-bound enrichment for all 299
calculation records. It does not change backend runtime source, API, planner,
frontend source, configuration, samples, workflows, the completed Loop 008
dataset, releases, or deployment.

## Native acquisition and extraction

The operator reacquired only
`Pal/Content/Paks/Pal-LinuxServer.pak` from Steam App `2394010`, Linux depot
`2394012`, manifest `2167164727892555341`. The live and local evidence matched:

- Build `24181105`;
- manifest binary SHA-256
  `3bab93b8c70d612ca5bd1a827be3d7f2d1bf92a2c1829507eca60c81a8f605ca`;
- manifest text SHA-256
  `fbcadb5fc783a410adf72ce2d4f4145b50c1abfe12059d3457e82054d70e89e9`;
- PAK size `4,797,040,962`;
- Steam SHA-1 `b81698aff4e50356b9c2672ecadc59a2dd840ea3`;
- PAK SHA-256
  `cad80fe15c38d74a795779fbab31f04bc2c15c37fb8a2188e4d89f3800fb0e68`.

Atlas commit `0385b3fd8bd757240d4a2c79615145122669abd5` passed the
accepted no-mappings probe with 753 Pal rows. The versioned patch SHA-256 is
`462761bdb29e8992f21af050d563d2f8a32bb02ce4b4724499518c699b7e3feb`.
It adds a bounded `enrich` command and exports only:

- `ElementType1`, `ElementType2`, `MaleProbability`, and
  `PassiveSkill1` through `PassiveSkill4` from
  `DT_PalMonsterParameter`;
- `PalID`, `WazaID`, and `Level` from `DT_WazaMasterLevel`.

The raw snapshot SHA-256 is
`5a9aa34bf870fa6270fedacc7dbc3a991d83ef7907ab1a301766fd8fd52f1da9`.
It contains 753 Pal rows and 5,772 active-skill rows. Every row has its
selected field names, selected values, source-row ID, source-row SHA-256, and
the complete selected-field table SHA-256.

## Join, normalization, and comparison

All 299 `source_internal_name` values matched exactly once without aliases.

| Source rows | Joined | Excluded | Total |
| --- | ---: | ---: | ---: |
| Pal parameter rows | 299 | 454 | 753 |
| Active-skill rows | 2,356 | 3,416 | 5,772 |

Every excluded row retains an explicit deterministic exclusion reason. The
four target records with no native learnset retain empty lists.

The enrichment contains exactly seven reviewed field groups:

- canonical Paldeck membership;
- roster class;
- one or two elements;
- male probability;
- female probability;
- active-skill learnset;
- direct guaranteed passive IDs.

Roster counts are exactly 287 canonical Paldeck records, 11 Terraria
collaboration entities, and one internal duplicate form. Female probability is
the decimal complement of the native integer male percentage.

The machine PalCalc/native diff compares gender probability and direct fixed
passives for every record. It contains 598 comparisons, 598 matches, and zero
differences. Guaranteed passives are explicitly described as fixed assignments,
not a complete inheritance pool.

## Produced artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `enrichment/ATLAS-LICENSE.txt` | 1,067 | `b88ccccdda36c466e1f74db2c5d97edac73edffa382ec7c92fbc8651daca6694` |
| `enrichment/manifest.json` | 4,451 | `b39b8e97e1b6db3c84949e9861fa4c7d6af4a900d322a84fa670c12938e54d51` |
| `enrichment/native-pal-fields.json` | 3,509,325 | `9e79caaa37715df5b19cc0faebc877e72a4bc696bdd6d11e4f26d240bc8e21b1` |
| `enrichment/pal-enrichment.json` | 381,451 | `4e27eaf7bd4624afa47f7f57c6b24febf759081b0ea44b2f032986080083872b` |
| `enrichment/palcalc-native-diff.json` | 149,488 | `77efe94b8776259b48780d8f7b75f222ea2b9308172e50258cde773df634515d` |
| `enrichment/roster-classification.json` | 5,049 | `4a9de3ea0560f7053366c2bcfa053f059c7b2aaaffc46bb355e0774ab841d61c` |

The generator source SHA-256 is
`553fc84fe52a1792e2e12f0b4132d6b5cfdb854b56eea2e885cfb9f146f1b101`.

## Determinism and failure behavior

Generation ran independently in two clean dataset directories. Both output
trees were byte-identical to each other and to the checked-in tree.

The offline validator verifies:

- the accepted native acquisition lock and Atlas patch;
- every generated-file identity;
- both native table identities and all row accounting;
- all 299 field allowlists, roster assignments, elements, probabilities,
  learnsets, and fixed passives;
- all 598 PalCalc/native comparisons;
- sanitized outputs;
- absence of enrichment references from backend runtime source.

Tests separately tamper with the manifest and every generated output. Every
case fails closed with a sanitized error.

## Validation evidence

- Exact manifest-only and single-PAK reacquisition: passed.
- PAK byte count, Steam SHA-1, and local SHA-256: passed.
- Atlas no-mappings production probe: passed.
- Bounded native extraction: 753 Pal rows and 5,772 active-skill rows.
- Clean-directory deterministic generation: passed twice.
- Offline enrichment validator: passed.
- Backend: 310 tests passed.
- Ruff format and lint: passed.
- Strict mypy: passed for 41 source files.
- Frontend no-network tests: 136 passed.
- Frontend type check: passed.
- Frontend production build: passed.
- `npm audit --audit-level=high`: zero vulnerabilities.
- `git diff --check`: passed.

## Remaining boundary

The enrichment is `stored_not_activated`. It does not provide UI
displayability, partner skills, ranch outputs, inheritable or random passive
pools, IV, inheritance, mutation, cake, incubation, or route probability
costs.

Gender-aware inventory, request, route, API, planner, and runtime activation
remain a separately controlled implementation loop.
