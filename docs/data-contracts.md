# Versioned Breeding Data Contracts

The structured-data boundary accepts complete immutable dataset snapshots. The bundled
`synthetic-v1` snapshot is fictional test data and is not a source of Palworld facts.

## Independent identity and version concepts

- `dataset_id` is the stable logical identity used by repository callers. It is not a path.
- `schema_version` identifies this manifest/relationship contract, not a game release.
- `game_version_scope` declares applicability. Synthetic data must use
  `synthetic_test_only` with a null value; production data must use
  `explicit_game_version` with a non-empty value.
- `provenance` records where the facts came from. It does not mean they passed validation.
- `validation_status` states that the importer considers the complete snapshot validated.
- `content_identity` verifies canonical relationship content independently from filenames.

## Stable species and relationship identifiers

Species identifiers match `^[a-z][a-z0-9_]{0,63}$`. Localized display names are separate
presentation attributes and cannot be primary keys.

```json
{"parent_a": "pal_a", "parent_b": "pal_b", "child": "pal_c"}
```

Parent order is not significant. The importer canonicalizes parent order and rejects one
unordered pair mapping to conflicting children before any relationship reaches the planner.

## Manifest

Every snapshot requires a manifest equivalent to:

```json
{
  "schema_version": 1,
  "dataset_id": "synthetic-v1",
  "classification": "synthetic",
  "game_version_scope": {
    "kind": "synthetic_test_only",
    "value": null
  },
  "created_at": "2026-07-11T00:00:00Z",
  "importer_version": "palnavi-json-importer/1",
  "validation_status": "validated",
  "provenance": [
    {
      "source_id": "palnavi-authored-fictional-fixture",
      "source_type": "local_synthetic_fixture",
      "locator": "local:palnavi/synthetic-v1",
      "retrieved_at": "2026-07-11T00:00:00Z",
      "license_or_usage_note": "Project-authored fictional data for tests only; not Palworld game knowledge.",
      "evidence_quality": "synthetic_only"
    }
  ],
  "content_identity": {
    "algorithm": "sha256",
    "digest": "3c7efb29e6ca91c6b949ad3bcac1227566d66270cad1b723f077d213e1ccceb5"
  }
}
```

Timestamps must be timezone-aware ISO-8601 values. Each provenance record has a stable source
identifier, typed source, locator, retrieval timestamp, license/usage note, and evidence
quality. Synthetic snapshots may use only `local_synthetic_fixture` plus `synthetic_only` and
cannot claim official, community, or real-game applicability.

## Relationship document and content identity

```json
{
  "dataset_id": "synthetic-v1",
  "classification": "synthetic",
  "relationships": [
    {"parent_a": "pal_a", "parent_b": "pal_b", "child": "pal_c"}
  ]
}
```

For SHA-256 identity, relationships are converted to canonical parent order, deduplicated by
unordered parent pair, sorted by `(parent_a, parent_b, child)`, and encoded as compact JSON
with sorted object keys. The importer hashes UTF-8 bytes of
`{"relationships": <canonical rows>}` and compares the lowercase digest to the manifest.
Mismatch makes the entire dataset invalid.

## Repository result contract

The framework-independent read-only repository returns one of:

- `DatasetFound(snapshot)`: immutable metadata, a `frozenset` of stable species IDs, and a
  tuple of validated relationships;
- `DatasetNotFound(dataset_id)`: no dataset exists for the stable identifier;
- `DatasetInvalid(dataset_id, issues)`: the dataset exists or the identifier was supplied,
  but validation failed.

Each invalid issue has a stable `code`, a logical `field`, and a sanitized `message`. Codes
distinguish unsupported schema, missing classification/provenance, invalid version scope,
invalid identifiers, malformed rows, parent conflicts, invalid validation state, and content
identity mismatch. No issue includes a local filesystem path or stack trace.

## Route request

```json
{
  "target_id": "pal_d",
  "owned_species_ids": ["pal_a", "pal_b"],
  "objective": "minimum_generations",
  "fixture": "synthetic-v1"
}
```

Omit `relationships` to resolve `fixture` as a stable dataset ID through the repository.
Alternatively, provide an explicit relationship array. Explicit rows pass the same shared
identifier, row-shape, parent-order, and conflict validation before planning.

## Route response and HTTP policy

Successful fixture-backed responses retain `data_source` and add validated dataset metadata:

```json
{
  "status": "success",
  "target_id": "pal_c",
  "data_source": "synthetic-v1",
  "dataset": {
    "dataset_id": "synthetic-v1",
    "schema_version": 1,
    "classification": "synthetic",
    "game_version_scope": {"kind": "synthetic_test_only", "value": null},
    "created_at": "2026-07-11T00:00:00+00:00",
    "importer_version": "palnavi-json-importer/1",
    "validation_status": "validated",
    "provenance": [],
    "content_sha256": "3c7efb29e6ca91c6b949ad3bcac1227566d66270cad1b723f077d213e1ccceb5"
  },
  "steps": [
    {"order": 1, "generation": 1, "parent_a": "pal_a", "parent_b": "pal_b", "child": "pal_c"}
  ],
  "cost": {"generations": 1, "breeding_steps": 1, "new_capture_count": 0},
  "reachable_species_ids": [],
  "error_category": null,
  "errors": [],
  "message": null
}
```

The abbreviated empty provenance array above keeps the example compact; actual fixture-backed
responses include the validated structured records.

- HTTP 200: success, unreachable result, or existing request/domain-invalid behavior.
- HTTP 404: repository returned `dataset_not_found`.
- HTTP 422: repository returned `dataset_invalid`, explicit relationships failed shared
  validation, or FastAPI rejected a malformed HTTP schema.

Dataset/repository errors use `status: "invalid"`, a stable `error_category`, and structured
`errors`. They are never represented as a successful route and never expose internal paths.
