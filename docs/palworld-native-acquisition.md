# Palworld Native Server Acquisition Lock

PalNavi has a deterministic acquisition-provenance lock for the public
Palworld Linux dedicated server associated with patch context v1.0.1. The lock
is stored beside the reviewed breeding dataset as
`native-acquisition-lock.json`.

This artifact closes a source-reproducibility gap. It does not add fields to
the normalized Pal records, activate the real dataset, or make claims about
PC-client-only assets.

## Locked identities

| Identity | Pinned value |
| --- | --- |
| Steam app | `2394010` |
| Branch | `public` |
| Build ID | `24181105` |
| Linux depot | `2394012` |
| Depot manifest | `2167164727892555341` |
| Selected file | `Pal/Content/Paks/Pal-LinuxServer.pak` |
| Selected-file bytes | `4,797,040,962` |
| Steam manifest SHA-1 | `b81698aff4e50356b9c2672ecadc59a2dd840ea3` |
| Local SHA-256 | `cad80fe15c38d74a795779fbab31f04bc2c15c37fb8a2188e4d89f3800fb0e68` |
| DepotDownloader | `3.4.0+c553ef4d60c00a4f5fd16c9fe017f569001589ff` |
| Atlas extractor commit | `0385b3fd8bd757240d4a2c79615145122669abd5` |
| .NET SDK | `10.0.302` |

The lock also binds the DepotDownloader release archive and executable, the
manifest binary and human-readable form, the .NET SDK archive, the Atlas
project file, and a sanitized NuGet dependency graph containing every resolved
package content hash.

## Generation protocol

Generation is an explicit operator action. The application never downloads a
depot during normal startup, API handling, tests, or dataset loading.

Prepare these content-addressed inputs outside the repository:

1. the pinned self-contained Linux x64 DepotDownloader executable and release
   archive;
2. an Atlas checkout at the exact commit above with its extractor dependencies
   already restored;
3. the pinned .NET SDK executable and release archive;
4. an empty, disposable work directory with at least 12 GB free.

Then run:

```bash
python tools/lock_palworld_server_acquisition.py \
  --lock datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/native-acquisition-lock.json \
  --work-dir /path/to/new-empty-work-directory \
  --observed-at 2026-07-24T08:27:26Z \
  --depot-downloader /path/to/DepotDownloader \
  --depot-downloader-archive /path/to/DepotDownloader-linux-x64.zip \
  --atlas-repo /path/to/PalworldAtlasData \
  --dotnet /path/to/dotnet \
  --dotnet-sdk-archive /path/to/dotnet-sdk-10.0.302-linux-x64.tar.gz \
  --nuget-packages /path/to/restored-nuget-packages
```

The tool performs the following fail-closed sequence:

1. verifies every caller-supplied tool archive and executable identity;
2. queries live anonymous Steam AppInfo and accepts only the versioned
   `2394012/24181105` result;
3. verifies the pinned manifest binary, text, counts, timestamp, selected PAK
   size, and Steam SHA-1;
4. requests depot `2394012` by exact manifest and a one-line file allowlist;
5. rejects any materialized non-metadata file other than the selected PAK;
6. independently recomputes the PAK SHA-1 and SHA-256;
7. verifies the Atlas commit, project, resolved dependency hashes, and .NET SDK;
8. removes connector-provided network routes, runs the probe without a
   mappings argument, and requires evidence that the extractor's optional
   unpinned Oodle download was unavailable;
9. accepts the probe only if all six required tables parse with nonzero rows;
10. emits the same canonical bytes twice from the same evidence and checks the
    result before atomically replacing the lock.

If Steam's public build changes, the old manifest becomes unavailable, any
hash differs, a mapping becomes necessary, or a required table cannot be
parsed, generation stops without publishing a new lock.

## Offline validation

Routine validation is network-free and does not require the PAK:

```bash
python tools/lock_palworld_server_acquisition.py \
  --validate-only \
  --lock datasets/palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47/native-acquisition-lock.json
```

The validator checks exact identities, nested source and generated-record
hashes, canonical JSON bytes, mappings status, the production gate, and
sanitization rules. Tests cover tampering with the build, asset, extractor,
probe, mappings result, and integrity hash.

## Probe result and limits

The pinned server PAK parsed all six required Atlas tables without a mappings
file: Pal parameters, unique breeding combinations, items, wild spawners,
spawner placements, and alpha spawners. Four optional tables also parsed. The
optional Pal-description localization table is absent from the dedicated
server package, which does not fail the production gate.

The successful probe proves that this server package is a suitable fixed input
for separately reviewed extraction work. It does not prove that every desired
field exists, define normalization rules, approve extracted rows for
production, or extend conclusions to the PC client.
