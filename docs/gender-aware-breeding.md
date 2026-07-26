# Gender-Aware Breeding and Route Planning

## Runtime boundary

Two read-only runtime paths use the accepted Palworld production breeding outcomes:

- `POST /api/v1/breeding/direct` performs one exact direct lookup;
- `POST /api/v1/breeding/gender-aware-routes` performs deterministic
  gender-capable multi-generation search.

A third read-only presentation path,
`GET /api/v1/palworld/species-catalog?dataset_id=<stable-id>`, returns the exact accepted
localized display names and Paldeck metadata for the same 299-species snapshot. It exposes no
breeding power, probability, statistics, skills, ranch output, source internal name, or local
path. Unknown or invalid data fails closed instead of substituting another dataset or a partial
catalog.

Neither endpoint mutates inventory. The pre-existing
`POST /api/v1/breeding/routes` endpoint, synthetic repository, request and response contracts,
and species-only planner remain unchanged as the rollback target.

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

The repository validates all 299 exact male and female probability pairs. The route planner uses
them only to decide whether a future offspring can satisfy a male or female state. Both values
are positive for every accepted species. Neither endpoint exposes the values, estimates expected
attempts, or uses elements, skills, roster fields, or fixed passives.

For the gender-probability fields only, this reviewed activation boundary supersedes the
historical `stored_not_activated` statements in the Loop 008 and Loop 010 data-generation
documents. Those documents remain the source and regeneration record; every other supplemental
field remains inactive.

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

## Multi-generation route request

The production route endpoint requires a concrete target gender and an inventory of stable
instance IDs, species IDs, and explicit genders:

```json
{
  "dataset_id": "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47",
  "target": {"species_id": "wixen_noct", "gender": "female"},
  "inventory": [
    {"instance_id": "dumud-1", "species_id": "dumud", "gender": "male"},
    {
      "instance_id": "katress-ignis-1",
      "species_id": "katress_ignis",
      "gender": "female"
    },
    {"instance_id": "wixen-1", "species_id": "wixen", "gender": "female"}
  ],
  "objective": "minimum_generations"
}
```

This request deterministically produces Katress male in generation one and then uses the
gender-directed Katress male plus Wixen female rule to produce Wixen Noct female in generation
two.

Every route state contains species, a concrete gender requirement, empty passive constraints,
empty IV constraints, and generation depth. Each step includes both gender-bound parents, the
selected feasible child gender, result kind, source-record hash, generation, and stable order.
Search minimizes maximum generation, then breeding-step count, then a stable source-bound
signature.

An explicit inventory gender of `unknown` returns `gender_required` before graph matching.
Omitted, `null`, or unrecognized inventory genders are request-validation errors. Duplicate
instance IDs, invalid identifiers, impossible states, and invalid data fail closed.

Route success costs contain generations and breeding-step count. They always include
`probability_dependent_cost_available: false` and `expected_attempts: null`; the planner does not
invent a 50:50 distribution or a probability-weighted cost model.

## Manual frontend workspace

The Vue interface defaults to the existing synthetic Knowledge workspace and offers a separate
verified-data Breeding workspace. The breeding form always submits the accepted dataset identity,
a concrete target gender, a stable target species ID, zero through 299 complete inventory rows,
and `minimum_generations`. The dataset identity and objective are visible but not editable.

Every added inventory row is explicit. The browser rejects blank or incomplete rows, invalid
species or instance IDs, duplicate instance IDs, and inventory overflow locally without issuing a
request. The form loads the fixed catalog only when the Breeding workspace is mounted, defaults
display locale to `en`, and offers the exact locale set `de`, `en`, `es`, `es-MX`, `fr`, `id`,
`it`, `ja`, `ko`, `pl`, `pt-BR`, `ru`, `th`, `tr`, `vi`, `zh-Hans`, and `zh-Hant`. Target and
inventory fields share one bounded suggestion list. Suggestions display an exact localized name
and stable ID; selection or an unambiguous exact localized name is normalized to the stable ID
before the request is built.

Catalog loading is independent from route submission and the immutable Loop 013 request
controller. A catalog failure displays an accessible warning, leaves manual stable-ID entry
enabled, and never starts a breeding request. Replaced catalog loads cannot overwrite newer work,
and component disposal aborts the active load.

The dedicated client reuses the same-origin, credential-omitting, redirect-rejecting,
cache-disabling, byte-bounded transport. It strictly validates JSON media type, UTF-8, exact
object keys, accepted content identities, state and identifier shapes, step order and generation
continuity, generated-parent availability, source-record SHA-256 values, target consistency, and
cost consistency before presentation.

The UI distinguishes successful routes, zero-step already-owned targets, `gender_required`,
`unreachable`, product `invalid`, FastAPI request validation, HTTP/contract conflicts, malformed
responses, and network failures. It renders backend values only as inert Vue text and keeps
dataset digests and source-record hashes in a secondary provenance disclosure. Request snapshots
are immutable; a newer submission aborts and supersedes an older one, retry reuses the last
snapshot, and component disposal aborts active work.

Inventory remains in component memory only. It is not stored in local storage, session storage,
IndexedDB, cookies, or a URL, and it is sent only to the same-origin route endpoint after explicit
submission.

## Rollback and non-goals

The pre-existing synthetic repository, multi-generation planner, route request, and route
response remain unchanged. Disabling both production endpoints or reverting their shared
repository dependency leaves that complete rollback path intact.

This feature does not implement expected attempts, offspring probability cost, inventory
persistence or consumption, passive or IV inheritance, mutation, cakes, incubation, partner
skills, ranch outputs, fuzzy aliases, translated or inferred display names, or save-file access.
