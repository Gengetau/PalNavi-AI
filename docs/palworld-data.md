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

## Unsupported fields

The audited inputs do not establish:

- a record-level mapping for the stated 287-player-visible roster;
- elements per Pal;
- ranch outputs;
- partner-skill IDs or descriptions;
- per-Pal active-skill assignments;
- complete per-Pal passive-skill assignments;
- inheritance, mutation, gender-odds, incubation, or cake-effect probabilities.

These fields remain `null` or explicitly unavailable. Product logic must not
fill them from display names, artwork, unversioned community tables, or guide
prose.
