# Official Source Registry and Metadata Snapshots

PalNavi keeps a versioned registry of nine exact public Pocketpair source surfaces. The registry
is a provenance and change-detection boundary only. It does not approve page text for copying,
search indexing, generated summaries, factual answers, or mod operation.

The checked-in artifact is `config/official-sources-v1.json`. It contains only canonical HTTPS
URLs, publisher and source-kind metadata, observed documentation versions, sensitivity and usage
review status, a metadata-only capture policy, probe permission, verification time, and a declared
SHA-256 identity. It contains no guide, table, news, policy, artwork, screenshot, player record, or
other page body.

## Registry identity

The registry has schema version `1`. Its `sources` array is sorted by stable lowercase source ID.
Unknown fields, duplicate JSON keys, duplicate IDs or URLs, unsafe URLs, unknown enum values,
unbounded strings, noncanonical UTC timestamps, noncanonical order, and an identity mismatch are
rejected.

`registry_sha256` is SHA-256 over canonical JSON containing `schema_version` and `sources`. The
declared `registry_sha256` field itself is excluded. Canonical JSON uses sorted object keys, ASCII
escaping, UTF-8, and no insignificant whitespace.

The v1 set contains these source IDs:

- `palworld-mod-guideline`
- `palworld-news`
- `palworld-rest-info-doc`
- `palworld-rest-introduction`
- `palworld-rest-players-doc`
- `palworld-server-guide`
- `palworld-server-mods`
- `palworld-technology-ids`
- `pocketpair-derivative-work`

The registry file is the source of truth for their exact URLs and policy metadata. Adding an
unregistered path on an otherwise allowed host is rejected.

## Live metadata boundary

Live access is optional and accepts only a validated registry entry. It cannot accept a URL, host,
credential, cookie, proxy, header, provider, or retry option from a caller. The only allowed hosts
are:

- `docs.palworldgame.com`
- `news.palworldgame.com`
- `guideline.palworldgame.com`
- `www.pocketpair.jp`

Every request requires the exact registered HTTPS URL. Userinfo, ports, queries, fragments, IP
literals, hostname suffix tricks, unregistered paths, and runtime server endpoints are rejected
before transport. In particular, the public documentation URL for the players endpoint may be
fingerprinted, but PalNavi never calls a game server's players or info endpoint and never requests
Basic Auth.

The transport creates a fresh client per source with environment trust disabled, redirects
disabled, HTTP/2 disabled, no cookie or credential headers, identity content encoding, one GET,
one bounded timeout, and no retry. It accepts HTTP 200 only. Redirects, a `Location` header, a
changed final URL, compression, an unapproved content type, an invalid length, more than 2 MiB, or
malformed UTF-8 fail closed.

Response bytes are streamed into a SHA-256 digest and fatal UTF-8 decoder, then discarded.
Successful records may retain only status 200, canonical media type, bounded ETag and
Last-Modified values, exact final URL, byte length, and SHA-256. A manifest never includes a body,
arbitrary header, exception message, local path, credential, cookie, proxy setting, or transport
object. Cleanup is scheduled best-effort and cannot delay or replace an established outcome.

Sanitized outcomes are:

- `success`
- `network_restricted`
- `timeout`
- `redirect_rejected`
- `content_type_rejected`
- `response_too_large`
- `malformed_encoding`
- `unavailable`

## Snapshot manifest

A manifest contains schema version, registry identity, acquisition mode, injected UTC start and
completion times, one canonical record per source, and a deterministic `manifest_sha256`. Every
record declares `content_persisted: false`. Failure records contain no response metadata.

`manifest_sha256` is SHA-256 over canonical JSON of every manifest field except the declared
`manifest_sha256` itself. The registry identity is part of this calculation.

Generated snapshots are runtime data, not business-repository source. When live metadata is
permitted, place output beneath:

`/workspace/shared/data/palnavi-ai/official-sources/`

## CLI

The CLI defaults to deterministic synthetic mock acquisition:

```bash
cd backend
python -m palnavi.infrastructure.official_sources.cli \
  --output /absolute/path/to/palnavi-official-sources-mock.json
```

Live access requires the only network-enabling flag:

```bash
python -m palnavi.infrastructure.official_sources.cli \
  --live-metadata \
  --output /absolute/path/to/palnavi-official-sources-live.json
```

`--replace` explicitly permits replacement of an existing regular output file. Without it,
creation is atomic and no-clobber. Relative paths, non-JSON names, missing or symlinked parent
paths, symbolic-link targets, directories, devices, and existing targets are refused safely.

Successful stdout contains only mode, record count, outcome counts, and manifest digest. It never
prints URLs, response headers, output paths, source text, or exception details.

The mock transport uses only project-authored text labeled as synthetic and not Palworld
knowledge. Its private body locators use the reserved `.invalid` domain. It runs through the same
HTTP response evaluator as live transport and exercises success plus all seven controlled failure
categories. The fixed mock clock makes the same registry and fixtures produce the same manifest
identity.

If the single opt-in live attempt records `network_restricted`, do not retry or wait. Run the
default mock command and continue development. Network restriction is evidence about the
execution environment, not a project blocker.

## Governance

Changing the source set or policy metadata requires:

1. a new official-source research review;
2. exact URL and usage-scope review;
3. a mechanically recalculated registry digest;
4. strict registry, transport, manifest, CLI, and no-network tests;
5. an independent exact-head review before merge.

A successful fingerprint still does not make a source searchable. Content use requires a later,
source-specific approval of usage scope, version applicability, transformation, and import.
