# Loop 008 Codex Report: Palworld v1 Data Ingestion

## Scope

Implemented the exact control command
`palnavi-ai-v1-loop-008-data-ingestion-command-001` on business baseline
`f9ddfafe140950c7958316e9c2c5f9c7c94f434e`.

No backend runtime, API, planner, repository, sample fixture, official-source
registry, or frontend behavior was changed.

## Source verification

Verified before parsing:

- PalCalc commit `8b7e2f779e47fddae16ddcb973e828ba20c02b80`;
- all four declared PalCalc Git blob SHA-1 identities;
- all four PalCalc byte counts and independently recorded SHA-256 identities;
- Palweave JSON at 8,049,960 bytes and SHA-256
  `9f558802ed3fa14b52c352d18a05cd40b295e636ccca249376293e80dc1643c4`;
- Palweave CSV at 2,128,682 bytes and SHA-256
  `db4e0e2b755ed3c01ef61744dfcc66c1af320ad444b4c0f47af687a3cf8f0b74`.

The generator cross-checked all 44,851 PalCalc breeding rows against both
Palweave exports before normalization.

## Produced artifacts

Dataset:

`datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/`

Generated machine identities:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `pals.json` | 393,010 | `d981831c11f552890ef0bd5cbbdda49208798c440a1b85cd272813207fe65da9` |
| `breeding-outcomes/` (30 parts) | 18,456,722 total | Per-part identities in `manifest.json` |
| `PALCALC-LICENSE.txt` | 1,058 | `60768557719376acb654991ff138d1b6ce5e9bf872582566b3f82b22e51ad5a4` |

Manifest content identity:

`b7fbe9b7395d2aef6758ff162da8fb738cf1fcd3ec5c7d50133c3d5edafdd30b`

## Normalized counts

| Scope | Count |
| --- | ---: |
| Pal calculation records | 299 |
| Outcomes | 44,851 |
| Source ordinary | 44,603 |
| Source special | 248 |
| Same species | 299 |
| Ordinary power | 44,418 |
| Fixed special | 132 |
| Gender directed | 2 |
| Gender-dependent pair families | 1 |

Every outcome reference resolves to a normalized Pal. All IDs satisfy the
PalNavi species identifier contract. The duplicate English display name for
the Gumoss flower variant is handled by one explicit, tested source mapping.

## Insufficient fields

The following remain unavailable rather than inferred:

- record-level player visibility for the stated 287-player roster;
- elements per Pal;
- ranch outputs;
- partner-skill IDs and descriptions;
- per-Pal active-skill assignments;
- complete per-Pal passive-skill assignments;
- inheritance, mutation, gender-odds, incubation, and cake-effect probabilities.

The independent compatibility methodology exposes checksums and counts, but its
linked public source repository currently returns not found. This dataset
therefore labels v1.0.1 compatibility as secondary community-audit evidence and
retains v1.0.0 as the source snapshot.

## Runtime boundary

The complete dataset is stored and validated but not activated. The existing
planner accepts an unordered species pair with one child and cannot represent
the two gender-directed outcomes for the Katress/Wixen family. Runtime
integration requires a separately reviewed gender-aware schema and planner
change.

## Validation evidence

- Dataset validate-only command: passed.
- Clean-directory regeneration and byte-for-byte comparison: passed.
- Backend: 286 tests passed.
- Ruff format and lint: passed.
- Strict mypy: passed for 41 source files.
- Frontend no-network tests: 136 passed.
- Frontend type check: passed.
- Frontend production build: passed.
- `npm audit --audit-level=high`: 0 vulnerabilities.
- `git diff --check`: passed.
- Changed-file machine-path, credential, private-key, and secret-like scan:
  passed.

The first two `npm ci` attempts were blocked by the pruned default npm cache
path. A task-local cache and clean dependency directory resolved the
environment failure; no lockfile or dependency version changed.
