# Gender-Aware Direct Breeding

## Runtime boundary

`POST /api/v1/breeding/direct` is the only runtime path that reads the accepted
Palworld production breeding outcomes. It performs a read-only direct lookup; it does not
replace `POST /api/v1/breeding/routes`, mutate inventory, estimate probabilities, or run a
multi-generation search.

The production repository accepts exactly:

- dataset `palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47`;
- main content identity
  `b7fbe9b7395d2aef6758ff162da8fb738cf1fcd3ec5c7d50133c3d5edafdd30b`;
- gender-data content identity
  `11173754c8dcf123df6be22823210d80f9b866732cbff80f112c70ba8208cfdf`;
- 299 species records and 44,851 direct outcomes;
- 44,849 wildcard rules and the two distinct gender-directed Katress/Wixen rules.

The repository verifies both manifests, every declared file byte count and SHA-256, all
source-record hash shapes, all species references, all result kinds, the native acquisition
lock, and the exact directed rows before it returns a snapshot. A mismatch returns a sanitized
`dataset_invalid` response and no query executes.

The gender-data files remain stored-only. This endpoint verifies their accepted identity but
does not parse or expose probabilities, elements, skills, or roster fields.

## Concrete query

A concrete query defaults to `query_mode: "concrete"` and requires an explicit gender on both
parents:

```json
{
  "dataset_id": "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47",
  "parent_a": {"species_id": "katress", "gender": "male"},
  "parent_b": {"species_id": "wixen", "gender": "female"}
}
```

Supported inventory gender values are `male`, `female`, and `unknown`. Explicit `null`, an
omitted gender, or any other value is invalid for a concrete request. `unknown` is accepted as
incomplete inventory state but returns `gender_required`; it never satisfies a concrete rule.
Two known parents of the same gender return `invalid`.

The successful request above returns `wixen_noct`. Exchanging both species and genders preserves
that result. Katress female plus Wixen male returns `katress_ignis`, also in either request order.

## Species-only query

Species-only lookup is a separate, explicit request shape. Set `query_mode` to `species_only` and
omit both gender properties:

```json
{
  "dataset_id": "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47",
  "query_mode": "species_only",
  "parent_a": {"species_id": "katress"},
  "parent_b": {"species_id": "wixen"}
}
```

For an ordinary or fixed wildcard rule, this returns the exact child. For Katress/Wixen it
returns `gender_required` with both concrete parent-gender orientations, children, result kinds,
and source-record hashes in stable order. Supplying a gender property in species-only mode is
invalid, including an explicit `null`.

## Response statuses

- `success`: one exact rule matched and includes the child, result kind, and source-record hash.
- `gender_required`: known species matched, but concrete opposite genders are required; every
  possible result is returned.
- `invalid`: the request reached the product rule but violates concrete breeding constraints, or
  the accepted repository failed validation.
- `not_found`: the dataset ID or direct rule does not exist.

Every successful repository-backed response includes the accepted main and gender-data content
identities. Error messages are stable and do not contain local paths or exception text.

## Rollback and non-goals

The pre-existing synthetic repository, multi-generation planner, route request, and route
response remain unchanged. Disabling the new direct endpoint or reverting its dependency leaves
that complete rollback path intact.

This feature does not implement gender-aware multi-generation planning, expected attempts,
offspring probability cost, inventory persistence, passive or IV inheritance, mutation, cakes,
incubation, partner skills, ranch outputs, frontend planning, or save-file access.
