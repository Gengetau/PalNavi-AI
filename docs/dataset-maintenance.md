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
