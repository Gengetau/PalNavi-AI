# Dataset Maintenance

This guide governs local dataset snapshots. Loop 002 authorizes only project-authored
fictional data; it does not authorize acquiring or embedding real Palworld data.

## Creating or changing a snapshot

1. Choose a stable `dataset_id`; do not derive semantic identity from a directory name.
2. Write relationship rows with stable identifiers and unordered parent semantics.
3. Set the independent `schema_version`, classification, and game-version scope.
4. Add at least one structured provenance record with source type, locator, retrieval time,
   license/usage note, and evidence quality.
5. Set a timezone-aware creation timestamp, importer version, and validated status.
6. Canonicalize the relationships using the implementation in
   `palnavi.domain.data.validation.dataset_content_sha256` and place the resulting
   lowercase SHA-256 in the manifest.
7. Run the complete import, repository, API, planner, formatter, linter, and type-check suites.

Never edit relationships without updating the digest. Never copy a digest from a different
snapshot. A filename, successful JSON parse, or provenance claim is not evidence of validation.

## Synthetic classification rules

Synthetic datasets must use:

- `classification: synthetic`;
- `game_version_scope.kind: synthetic_test_only` and a null scope value;
- `source_type: local_synthetic_fixture`;
- `evidence_quality: synthetic_only`;
- warnings that the relationships are fictional and not game knowledge.

The importer rejects a synthetic manifest that claims official/community provenance or a
real-game version scope.

## Production data

The first separately authorized production artifact is the stored, not-yet-activated Palworld
v1 dataset documented in `docs/palworld-data.md`. It uses exact locked inputs, retains the
PalCalc MIT notice, and records unsupported facts as unavailable.

Regeneration is a two-stage operator action:

1. Download the six exact source files named in the dataset manifest outside the normal
   application runtime.
2. Pass all six local paths explicitly to `tools/build_palworld_dataset.py`.

The tool accepts no URL and performs no network access. It verifies byte counts, SHA-256 values,
Git blob identities, cross-export equality, normalized counts, references, gender constraints,
and generated-file identities before replacing outputs atomically.

Do not activate a production dataset merely because it validates. The current planner cannot
represent the gender-directed parent-pair family. Runtime activation requires a separately
reviewed contract and planner change.

Every future Palworld patch requires a newly pinned extraction or independently reproducible
audit, a complete field and outcome diff, a new compatibility decision, and regenerated
identities. Patch notes alone do not extend the compatibility window.

## Native server acquisition provenance

The versioned Palworld dataset now includes a separate, sanitized acquisition
lock for public Linux dedicated-server Build `24181105`. This lock establishes
that the exact depot manifest and selected server PAK can be acquired and
verified, and that the pinned Atlas extractor can parse its required tables
without mappings.

The acquisition tool is intentionally separate from
`build_palworld_dataset.py`:

- `tools/lock_palworld_server_acquisition.py` is a one-time, explicitly
  networked operator boundary that downloads proprietary bytes only into a
  caller-selected disposable directory and emits a content-only lock.
- `tools/build_palworld_dataset.py` remains fully offline and builds the
  reviewed normalized dataset from its six caller-supplied source files.

Normal tests use only `--validate-only`; they must not connect to Steam,
download an SDK, restore packages, run an extractor, or retain a PAK. See
`docs/palworld-native-acquisition.md` for pinned identities, prerequisites,
the exact generation command, cleanup expectations, and failure rules.

An accepted acquisition lock authorizes no field extraction by itself.
Loop 010 separately reviewed and stored a bounded enrichment for roster
classification, elements, gender probability, fixed passive assignments, and
active-skill learnsets. The accepted implementation is documented in
`docs/palworld-enrichment.md`; runtime activation remains a separate review.

## Native enrichment regeneration

`tools/build_palworld_enrichment.py` has two boundaries:

1. Generation requires explicit local paths for the exact PAK, raw patched
   Atlas snapshot, clean fixed-commit Atlas and PalCalc repositories, PalCalc
   inputs, Atlas license, and accepted roster-classification file.
2. Routine `--validate-only` uses only checked-in files, performs no network
   access, and fails closed for any source identity, row accounting, generated
   file, or runtime-status change.

The checked Atlas patch exports only seven Pal fields and three active-skill
fields. It must be applied to the exact upstream commit. Do not replace it with
a branch tip or expand it to localization, Blueprint, image, or unrelated
table fields in the same review.

Generation must start from a clean output directory and be repeated. Both
output trees must be byte-identical. The original PAK, SDK, NuGet cache,
patched checkout, and raw extraction are disposable operator inputs and must
not be committed.
