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

The JSON data files are compact machine artifacts. Use the local validator
instead of manually reformatting them:

```bash
python tools/build_palworld_dataset.py \
  --validate-only \
  --output datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47
```

## Important limitations

`player_visible`, species elements, ranch outputs, partner-skill IDs, and
per-Pal active-skill IDs are `null` because the audited inputs do not provide
record-level evidence for them. The dataset also does not model inheritance,
mutation, gender-odds, incubation, or cake-effect probabilities.

Two outcomes represent one gender-directed parent-pair family. The current
PalNavi planner models only an unordered species pair with one child, so this
dataset is stored and validated but is not activated as the runtime default.
Runtime activation requires a separate schema and planner review.
