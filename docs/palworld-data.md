# Reviewed Palworld Data

PalNavi stores reviewed real-game data separately from fictional test fixtures.
The first production artifact is:

`datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/`

## Source boundary

The dataset combines two exact, complementary inputs:

1. PalCalc `db.json` at commit
   `8b7e2f779e47fddae16ddcb973e828ba20c02b80` supplies 299 calculation
   records, localizations, breeding powers, available statistics, work
   suitability, and guaranteed passive IDs.
2. The checksum-locked Palweave JSON export supplies stable public slugs,
   source ordinary/special labels, gender constraints, and 44,851 expanded
   outcomes. Its CSV twin is independently cross-checked during generation.

The generator verifies the byte count, SHA-256, and, for Git inputs, Git blob
SHA-1 before parsing. It also cross-checks all PalCalc breeding rows against
both audited Palweave exports.

The same dataset directory also contains
`native-acquisition-lock.json`. It independently binds the public Linux
dedicated-server Build `24181105`, exact depot manifest, selected PAK,
DepotDownloader release, Atlas extractor commit and dependency graph, and a
successful no-mappings probe. It is acquisition provenance for later
field-extraction loops, not an input to the breeding dataset generator.
The reproducible operator and offline-validation procedures are documented in
`docs/palworld-native-acquisition.md`.

The separately versioned `enrichment/` directory uses that acquisition lock
and a checked Atlas patch to add reviewed fields without changing the completed
Loop 008 files. Its extraction, row accounting, normalization, and validation
contract is documented in `docs/palworld-enrichment.md`.

## Normalized identities

Source slugs use hyphens. PalNavi IDs replace them with underscores so they
match the existing species identifier contract. The mapping is bijective for
all 299 records.

The flower variant of Gumoss needs one explicit mapping:

```text
PalCalc PlantSlime_Flower -> Palweave gumoss-flower -> PalNavi gumoss_flower
```

Its English display name is also `Gumoss`, so a display-name-only slug would
otherwise collide with ordinary Gumoss.

## Count semantics

| Scope | Count |
| --- | ---: |
| Calculation records | 299 |
| Source-derived outcomes | 44,851 |
| Source-classified ordinary outcomes | 44,603 |
| Source-classified special outcomes | 248 |
| Normalized same-species outcomes | 299 |
| Normalized ordinary-power outcomes | 44,418 |
| Normalized fixed-special outcomes | 132 |
| Normalized gender-directed outcomes | 2 |
| Gender-dependent parent-pair families | 1 |

The normalized result-kind counts do not split the source labels one-to-one.
For example, some source-special rows are identical-parent results and are
normalized as `same_species`.

## Runtime status

The dataset is `stored_not_activated`. PalNavi's current route contract treats
parents as an unordered species-only pair. It cannot distinguish the two
gender-directed results for the same species pair without silently selecting
the wrong child.

A later runtime-integration loop must add gender-aware inventory and request
semantics, update canonical identity rules, and review route behavior before
this dataset becomes the API default.

## Base-snapshot and enrichment boundaries

The immutable `pals.json` does not contain normalized values for:

- roster classification or UI displayability;
- elements per Pal;
- ranch outputs;
- partner-skill IDs or descriptions;
- per-Pal active-skill assignments;
- complete per-Pal passive-skill assignments;
- inheritance, mutation, gender-odds, incubation, or cake-effect probabilities.

The adjacent enrichment now stores:

- a `287 + 11 + 1` roster classification;
- one or two native elements for every calculation record;
- native male probability and its exact decimal female complement;
- 2,356 Pal/skill/learned-level entries;
- direct fixed assignments from `PassiveSkill1` through `PassiveSkill4`.

All 753 native Pal rows and 5,772 active-skill rows are accounted as joined or
excluded. PalCalc/native comparisons cover gender probability and direct fixed
passives for all 299 records, producing 598 exact matches and no differences.

These facts remain `stored_not_activated`. Product logic must not copy them
into runtime repositories until the gender-aware planner loop reviews schema,
inventory, request, route, API, and compatibility behavior.
