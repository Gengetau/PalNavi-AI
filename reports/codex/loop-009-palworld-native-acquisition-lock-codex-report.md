# Loop 009 Codex Report: Palworld Native Acquisition Lock

## Scope

Implemented control command
`palnavi-ai-v1-loop-009-native-acquisition-command-001` on exact business
baseline `0a5bdaf639a2799d3f4b3039fd370863a52d8b9e`.

The change establishes deterministic acquisition provenance only. It does not
modify backend runtime code, the API, planner, normalized Pal or breeding
records, frontend source, configuration, samples, workflows, releases, or
deployment.

## Live acquisition evidence

The generation tool ran from a new empty work directory and:

- verified DepotDownloader
  `3.4.0+c553ef4d60c00a4f5fd16c9fe017f569001589ff`;
- queried anonymous live Steam AppInfo for App `2394010`, branch `public`;
- observed the single Linux depot version directory
  `2394012/24181105`;
- verified exact manifest `2167164727892555341`, created
  `2026-07-13T09:20:38Z`;
- requested only `Pal/Content/Paks/Pal-LinuxServer.pak` from that exact
  manifest;
- downloaded `4,657,366,384` compressed bytes and materialized
  `4,797,040,962` PAK bytes;
- independently recomputed Steam SHA-1
  `b81698aff4e50356b9c2672ecadc59a2dd840ea3`;
- independently recomputed local SHA-256
  `cad80fe15c38d74a795779fbab31f04bc2c15c37fb8a2188e4d89f3800fb0e68`.

The generated lock stores no downloaded asset, raw table, mapping, texture,
caller path, network route, credential, token, or environment value.

## Extractor and mappings evidence

The operator checkout was at Atlas commit
`0385b3fd8bd757240d4a2c79615145122669abd5`. The tool bound:

- canonical repository `https://github.com/Awy64/palworld-atlas-data.git`;
- Atlas project SHA-256
  `3e40be050b850c887a9416c25d8be6d8b5cf437c7d0ca0cbf006588d86d9932a`;
- .NET SDK `10.0.302` and its archive SHA-256;
- a sanitized 32-package NuGet graph with every resolved package content
  SHA-512;
- dependency graph record SHA-256
  `d2df63b2c44fbccd291bbfe99168d460e40dcf301e026b29c6a2e4e8648fb32b`.

Atlas's own eight tests passed before the production probe. The probe then ran
without a mappings argument and without connector-provided network routes. It
explicitly reported that its optional unpinned Oodle download was unavailable,
yet passed the production gate.

All six required tables parsed with nonzero rows:

| Required table | Rows |
| --- | ---: |
| Pal parameters | 753 |
| Unique breeding combinations | 258 |
| Items | 2,466 |
| Wild spawners | 1,691 |
| Spawner placements | 8,253 |
| Alpha spawners | 159 |

Four optional tables also parsed. The optional Pal-description localization
table was absent from the dedicated-server PAK. The sanitized probe record
SHA-256 is
`5d6c8f7acb61e0e290681e260c197f19bfaee99349a0396b1ab0b904b2146b43`,
and mappings status is `mappings_not_required`.

After removing the tool's initial explicit loopback block in favor of removing
connector-provided network routes and requiring the Oodle failure evidence,
the actual PAK probe was rerun. It produced the same mappings status,
production result, and probe record SHA-256.

Independent pre-review compared the repository locator with the control source
lock and local Git remote, corrected an initial owner-name typo, downloaded the
fixed-commit archive from the corrected URL, and matched every tracked file
against the checkout before the revised lock was published.

## Produced artifacts

The canonical lock is
`datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/native-acquisition-lock.json`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Native acquisition lock | 13,726 | `57e19c299c805995b3efa3b8b442f12040fdd2396d761d638677098388223307` |
| Acquisition and validation tool | source file | `0cb34b0e2746715308fdff43a646d49830ffef835cb850e46ee6851f8380e532` |

The lock's source record SHA-256 is
`4b711767a73660878ab442819874866eceb51f3acd23a0e55c468209235539bf`,
and its generated-record SHA-256 is
`fef729bdc7be39a1d670dd932bf28d3d6bcb646d6544ac3ca33568b704cc7c36`.

The generator builds the canonical bytes twice from the same stable evidence
and refuses to publish if they differ. Routine `--validate-only` execution is
offline, requires no PAK, and verifies all nested identities and hashes.

## Validation evidence

- Full networked clean-directory acquisition and lock generation: passed.
- Live Build ID and exact manifest identity checks: passed.
- PAK byte count, Steam SHA-1, and local SHA-256 checks: passed.
- Atlas extractor tests: 8 passed.
- Atlas no-mappings production probe: passed.
- Backend: 297 tests passed, including 11 acquisition-lock tests.
- Ruff format and lint: passed.
- Strict mypy: passed for 41 source files.
- Offline lock validation: passed.
- Frontend no-network tests: 136 passed.
- Frontend type check: passed.
- Frontend production build: passed.
- `npm audit --audit-level=high`: 0 vulnerabilities.
- `git diff --check`: passed.

The first frontend dependency-install attempt omitted the restored shared
environment and tried to write npm state beneath the read-only base home. It
did not reach a test command. Re-running the exact gate after sourcing
the shared workspace environment entrypoint rebuilt dependencies with the
workspace cache, and all frontend checks passed without changing the lockfile.

## Remaining boundaries

- The lock covers the Linux dedicated server, not PC-client-only assets or
  behavior.
- It proves exact reacquisition and required-table parsing; it does not approve
  extracted rows or field normalization.
- The existing normalized dataset remains unchanged and
  `stored_not_activated`.
- Roster classification, elements, gender probability, guaranteed passives,
  and active-skill learnsets still require a separate extraction and
  normalization loop.
- Gender-aware planning and runtime activation remain a later, separately
  reviewed loop.
