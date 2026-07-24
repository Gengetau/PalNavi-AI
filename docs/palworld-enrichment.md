# Palworld Deterministic Enrichment

This document describes the versioned enrichment stored beneath:

`datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/enrichment/`

The enrichment adds reviewed static fields alongside the immutable Loop 008
dataset. It does not modify the runtime repository, API, planner, frontend, or
the completed `pals.json` and breeding-outcome files.

## Exact source identities

| Source | Accepted identity |
| --- | --- |
| Steam App | `2394010` |
| Linux depot | `2394012` |
| Steam Build | `24181105` |
| Depot manifest | `2167164727892555341` |
| Selected PAK SHA-256 | `cad80fe15c38d74a795779fbab31f04bc2c15c37fb8a2188e4d89f3800fb0e68` |
| Atlas commit | `0385b3fd8bd757240d4a2c79615145122669abd5` |
| Atlas dependency record | `d2df63b2c44fbccd291bbfe99168d460e40dcf301e026b29c6a2e4e8648fb32b` |
| Atlas patch SHA-256 | `555a7ee1df68fbf120a2cac0582f562e4e4761cd35ccc08131bac89a1c93ce1e` |
| Raw native snapshot SHA-256 | `5a9aa34bf870fa6270fedacc7dbc3a991d83ef7907ab1a301766fd8fd52f1da9` |
| PalCalc commit | `8b7e2f779e47fddae16ddcb973e828ba20c02b80` |
| Roster rules SHA-256 | `4a9de3ea0560f7053366c2bcfa053f059c7b2aaaffc46bb355e0774ab841d61c` |

The versioned native acquisition lock remains the source of truth for the
Steam, PAK, tool, SDK, dependency, and no-mappings identities.

## Bounded native extraction

`tools/palworld_atlas_enrichment.patch` applies only to the accepted Atlas
commit. It adds an `enrich` command and does not alter the existing probe or
published data contracts.

The command reads only:

- `DT_PalMonsterParameter`: `ElementType1`, `ElementType2`,
  `MaleProbability`, and `PassiveSkill1` through `PassiveSkill4`;
- `DT_WazaMasterLevel`: `PalID`, `WazaID`, and `Level`.

It emits the exact package path, selected field names, every source-row ID,
every selected value, a SHA-256 for each selected row, and a SHA-256 for each
complete selected-field table. Output is stable JSON with no timestamp.

The reviewed extraction produced:

| Table | Raw rows | Selected-field SHA-256 |
| --- | ---: | --- |
| `DT_PalMonsterParameter` | 753 | `c967739d5da54e14362a7e09e71b6edc8d6d69ab9c2231f0a41c17c632454b96` |
| `DT_WazaMasterLevel` | 5,772 | `f4ec51af9d46b997e54fe597461c650012cc04dbbc588817c2818f81f172e341` |

The raw extraction is a disposable operator input. It is not committed because
the reviewed repository artifact is the bounded, normalized, fully accounted
source evidence.

## Join and row accounting

The normalizer joins by exact `source_internal_name`. All 299 calculation
records match one native Pal row without an alias. The output therefore records
an empty alias map rather than guessing alternate identities.

| Source row class | Joined | Excluded | Total |
| --- | ---: | ---: | ---: |
| Native Pal rows | 299 | 454 | 753 |
| Native active-skill rows | 2,356 | 3,416 | 5,772 |

Every excluded Pal row receives
`source_row_not_in_locked_299_calculation_roster`. Every excluded active-skill
row receives `pal_id_not_in_locked_299_calculation_roster`. Each record retains
its source row ID, selected values, field list, and source-row hash.

The four target records `GhostAnglerfish`, `GhostAnglerfish_Fire`,
`LazyCatfish`, and `LazyCatfish_Gold` have no native active-skill row. Their
learnsets are stored as empty lists rather than inferred from related forms.

## Normalization

Each entry in `records_by_pal_internal_id` contains exactly:

- `canonical_paldeck_member`;
- `roster_class`;
- `elements`;
- `male_probability`;
- `female_probability`;
- `active_skill_learnset`;
- `guaranteed_passive_skill_ids`.

Roster rules classify the 299 records as 287 canonical Paldeck members, 11
Terraria collaboration entities, and one internal duplicate form. Elements
retain the stable native element IDs. Male percentage is divided by 100;
female probability is calculated as `(100 - male_percent) / 100`.

Learnset entries retain the PalNavi Pal ID, stable native skill ID, and learned
level. Fixed passives contain only direct assignments from the four native
fields. They are not a complete inheritance pool.

## PalCalc/native diff

`palcalc-native-diff.json` compares both shared consumed fields for every
record:

- male probability percentage;
- direct guaranteed passive IDs.

The reviewed output contains 598 comparisons, 598 matches, and zero
differences. A difference cannot be silently preferred because every
comparison stores the PalCalc value, native value, and explicit status.

## Generation

First acquire and validate the exact PAK as described in
`docs/palworld-native-acquisition.md`. Check out Atlas and PalCalc at their
accepted commits, apply the versioned patch to a clean Atlas worktree, and
produce the raw native snapshot with the patched `enrich` command.

Then pass every local input explicitly:

```bash
python tools/build_palworld_enrichment.py \
  --dataset datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47 \
  --native-snapshot "$NATIVE_SNAPSHOT" \
  --pak "$PALWORLD_PAK" \
  --atlas-repo "$ATLAS_REPOSITORY" \
  --atlas-license "$ATLAS_REPOSITORY/LICENSE" \
  --palcalc-repo "$PALCALC_REPOSITORY" \
  --palcalc-db "$PALCALC_REPOSITORY/PalCalc.Model/db.json" \
  --palcalc-csv "$PALCALC_REPOSITORY/PalCalc.GenDB/out-csv/pals.csv" \
  --roster-classification "$ROSTER_CLASSIFICATION"
```

The generator verifies all Git Heads, source bytes, Git blobs, PAK bytes,
the exact three-file patch inventory, the applied source hashes, native row and
table hashes, joins, comparisons, counts, and output identities before
atomically replacing artifacts. The patch is applied to a disposable copy of
the pinned source files; `git apply --check` alone is not accepted as evidence.

Routine validation is offline:

```bash
python tools/build_palworld_enrichment.py \
  --validate-only \
  --dataset datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47
```

Generation must be repeated in two clean dataset directories. The two
`enrichment/` trees and the checked-in tree must be byte-identical.

## Runtime and claim limits

The enrichment is `stored_not_activated`. It is not imported by backend
runtime source and is not exposed by any API or frontend.

It does not claim:

- PC-client-only assets or behavior;
- UI displayability;
- partner-skill behavior;
- ranch outputs;
- inheritable or random passive pools;
- IV, inheritance, mutation, cake, or incubation mechanics;
- expected breeding attempts or probability costs.

Runtime activation belongs to the separately reviewed gender-aware planning
loop.
