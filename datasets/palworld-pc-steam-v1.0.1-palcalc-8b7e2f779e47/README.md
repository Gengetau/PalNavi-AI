# Palworld PC/Steam v1 breeding dataset

This directory contains reviewed, normalized static facts for PalNavi AI.

## Version meaning

- Source snapshot: Palworld `v1.0.0`
- Independently audited compatible public patch: PC/Steam `v1.0.1`
- PalCalc source commit:
  `8b7e2f779e47fddae16ddcb973e828ba20c02b80`

The files are not described as a native v1.0.1 extraction. A community audit
found the locked v1.0.0 Pal and breeding checksums unchanged for v1.0.1.

## Files

- `manifest.json` records exact source and generated-file identities, counts,
  provenance, known gaps, and runtime status.
- `pals.json` contains 299 breeding-engine calculation records with the fields
  actually available from the pinned PalCalc database.
- `breeding-outcomes/` contains all 44,851 audited parent-to-child outcomes in
  30 deterministic parts.
- `PALCALC-LICENSE.txt` is the required MIT notice for the source-derived data.
- `native-acquisition-lock.json` binds the exact Linux dedicated-server PAK
  and no-mappings extractor probe.
- `enrichment/` contains the separately reviewed native-field enrichment,
  complete source-row accounting, PalCalc/native diff, roster rules, source
  license, and a content-addressed manifest.

The JSON data files are compact machine artifacts. Use the local validator
instead of manually reformatting them:

```bash
python tools/build_palworld_dataset.py \
  --validate-only \
  --output datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47

python tools/build_palworld_enrichment.py \
  --validate-only \
  --dataset datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47
```

## Important limitations

The immutable `pals.json` snapshot still keeps `player_visible`, species
elements, ranch outputs, partner-skill IDs, and per-Pal active-skill IDs
unavailable. The adjacent enrichment supplies reviewed elements, gender
probabilities, active-skill learnsets, direct fixed passives, and roster
classification without rewriting that completed snapshot.

The enrichment does not provide UI displayability, ranch outputs, partner
skills, an inheritable passive pool, inheritance or mutation mechanics,
incubation formulas, cake effects, or route probability costs.

Two outcomes represent one gender-directed parent-pair family. The current
PalNavi planner models only an unordered species pair with one child, so this
dataset is stored and validated but is not activated as the runtime default.
Runtime activation requires a separate schema and planner review.
