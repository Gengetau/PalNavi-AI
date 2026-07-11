# Initial Breeding Data Contracts

These contracts describe the foundation prototype. The bundled dataset is fictional and is
not a source of Palworld game facts.

## Identifiers and future versioning

Species use stable lowercase identifiers matching `^[a-z][a-z0-9_]{0,63}$`, such as
`pal_a`. A localized display name is a separate presentation attribute and must never be a
primary key. Production relationship records will require a schema version, applicable game
data version, source provenance, retrieval time, parser version, and validation status. Those
production metadata rules belong to a later controlled import loop.

## Relationship

```json
{"parent_a": "pal_a", "parent_b": "pal_b", "child": "pal_c"}
```

Parent order is not significant. Repeating the same unordered parent pair with different
children is rejected as conflicting input. Same-species parent pairs are representable; this
prototype operates at species level and does not model required individual quantities or sex.

## Route request

```json
{
  "target_id": "pal_d",
  "owned_species_ids": ["pal_a", "pal_b"],
  "objective": "minimum_generations",
  "fixture": "synthetic-v1"
}
```

Omit `relationships` to use the fictional fixture, or provide an explicit array of relationship
objects. `fixture` currently has only `synthetic-v1`; it must not be interpreted as a real game
version.

## Route response

A response has `status` equal to `success`, `unreachable`, or `invalid`. Successful responses
contain ordered `steps` and a `cost` object:

```json
{
  "status": "success",
  "target_id": "pal_c",
  "data_source": "synthetic-v1",
  "steps": [
    {"order": 1, "generation": 1, "parent_a": "pal_a", "parent_b": "pal_b", "child": "pal_c"}
  ],
  "cost": {"generations": 1, "breeding_steps": 1, "new_capture_count": 0},
  "reachable_species_ids": [],
  "errors": [],
  "message": null
}
```

Unreachable responses include the deterministic reachable species closure and a reason.
Domain-invalid relationship sets return `invalid` with error strings. Malformed HTTP objects
that cannot satisfy the declared API schema receive FastAPI's structured HTTP 422 validation
response.
