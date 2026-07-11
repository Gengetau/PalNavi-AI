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
   `palnavi.domain.data.validation.relationship_content_sha256` and place the resulting
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

## Future production data

Production datasets require a separately authorized loop. They must declare a non-empty
explicit game-version scope and permission-compatible provenance. Source review, license
assessment, import tooling, special breeding rules, and update policy must be approved before
any real facts are committed. No current maintenance step performs network access.
