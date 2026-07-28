# PalNavi AI 1.0.0-rc.1 Human Acceptance Package

## Decision boundary

This package describes a source-based release candidate for the human owner to
accept or reject. It is not a final `v1.0.0` release, installer, signed binary,
or remote deployment. The exact candidate Git Head and Tree are recorded in the
Loop 016 `agent-loop-business-receipt/v2` attached to the candidate pull
request. Check out that exact accepted commit before running this package.

PalNavi is advisory, local, and read-only. It does not access a running game,
read or mutate saves, automate gameplay, or establish that a Pal can be caught
in a particular place.

## Supported environment

| Component | Supported candidate range |
| --- | --- |
| Python | 3.12 or newer |
| Node.js | `^22.18.0` or `>=24.12.0` |
| npm | `>=11.9.0 <12` |
| Backend | FastAPI source application on loopback |
| Frontend | Vue 3 source application through local Vite |
| Distribution | Local source checkout only |

The deterministic API and planning workflows need no model provider or
credential. The optional explanation workflow requires a provider configured
locally as documented in `docs/model-providers.md`; provider setup is not
needed for knowledge search, the species catalog, or any breeding calculation.

## Clean Windows setup

Open PowerShell in an exact candidate checkout:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cd ..\frontend
npm ci
cd ..
python scripts\verify_v1_release_candidate.py
```

The verifier must print JSON with `"status": "verified"`,
`"product_version": "1.0.0-rc.1"`, the fixed dataset ID, eight API routes,
and `"network_required": false`.

## Clean portable-shell setup

From an exact candidate checkout:

```bash
cd backend
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cd ../frontend
npm ci
cd ..
python scripts/verify_v1_release_candidate.py
```

If `python3.12` is not the executable name on the host, use another Python
3.12-or-newer executable.

## Prepare synthetic knowledge

The repository intentionally ships only project-authored synthetic prose.
Import it into the ignored local SQLite database before exercising Knowledge:

```powershell
cd backend
python -m palnavi.infrastructure.knowledge_cli
cd ..
```

Successful output names the two synthetic documents as `created` or
`unchanged`. The command stores no provider credential.

## Run the local product

In terminal one, with the Python environment activated:

```powershell
cd backend
python -m uvicorn palnavi.api.main:app --host 127.0.0.1 --port 8000
```

In terminal two:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

Open the loopback URL printed by Vite, normally
`http://127.0.0.1:5173`. The frontend uses only relative `/api` requests and
the development proxy targets `127.0.0.1:8000`. Do not expose either service
to an untrusted network.

OpenAPI is available locally at `http://127.0.0.1:8000/docs`. A production
frontend build may be checked with `npm run build`, but this candidate does not
define a remote hosting target.

## Representative acceptance scenarios

### 1. Health and release identity

Open `http://127.0.0.1:8000/health`.

Expected result:

```json
{"status":"healthy"}
```

Open `http://127.0.0.1:8000/openapi.json` and confirm
`info.version` is `1.0.0-rc.1`.

### 2. Synthetic knowledge search

In the Knowledge workspace:

1. keep **Synthetic knowledge only** enabled;
2. enter `crystal moss`;
3. submit Search.

Expected outcome:

- one or more clearly labeled fictional synthetic results;
- canonical, inert citation details;
- no claim that the result is Palworld knowledge;
- no model provider required.

Explanation may return a controlled configuration error until a provider is
configured. That does not affect deterministic search or planning acceptance.

### 3. Owned-inventory production route

In the Breeding workspace, use the fixed production dataset and enter:

| Field | Value |
| --- | --- |
| Target species | `wixen_noct` |
| Target gender | `female` |
| Owned 1 | ID `dumud-1`, species `dumud`, gender `male` |
| Owned 2 | ID `katress-ignis-1`, species `katress_ignis`, gender `female` |
| Owned 3 | ID `wixen-1`, species `wixen`, gender `female` |

Expected outcome:

- success for target `wixen_noct / female`;
- first child `katress / male` from Dumud male and Katress Ignis female;
- second child `wixen_noct / female` from Katress male and Wixen female;
- two ordered breeding steps with source hashes;
- no new-capture, probability, cake, time, passive, or IV claim.

### 4. Explicit minimum-new-capture route

In the Capture-ranked workspace, enter:

| Field | Value |
| --- | --- |
| Target species | `wixen_noct` |
| Target gender | `female` |
| Owned 1 | ID `katress-ignis-1`, species `katress_ignis`, gender `female` |
| Owned 2 | ID `wixen-1`, species `wixen`, gender `female` |
| Candidate | ID `capture-dumud`, species `dumud`, gender `male` |

Expected outcome:

- success using exactly one capture requirement, `capture-dumud`;
- the same two ordered breeding children, `katress` then `wixen_noct`;
- a visible statement that the candidate is user supplied and catchability is
  not verified;
- no location, rarity, difficulty, probability, or availability claim.

### 5. Explicit unsupported behavior

Submit a request whose owned inventory and explicit candidate set cannot reach
the target, or use an owned row with unknown gender.

Expected outcome:

- deterministic `unreachable` or `gender_required`, as applicable;
- no invented route, inferred capture, or model fallback.

## Supported data

| Property | Candidate support |
| --- | --- |
| Dataset ID | `palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47` |
| Content SHA-256 | `b7fbe9b7395d2aef6758ff162da8fb738cf1fcd3ec5c7d50133c3d5edafdd30b` |
| Calculation records | 299 |
| Normalized breeding outcomes | 44,851 |
| Source snapshot | Palworld `v1.0.0` |
| Audited compatible patch | Palworld `v1.0.1` |
| Catalog presentation locales | 17 |
| Production knowledge prose | Not available |

Localized names are presentation only. Stable species IDs enter every request.

## Explicitly unsupported

| Capability | Candidate behavior |
| --- | --- |
| Catchability, encounter availability, and locations | Not verified or inferred |
| Capture rarity, difficulty, spheres, or probability | Not available |
| Expected breeding attempts or reliability | Not available |
| Cake, incubation, and elapsed time | Not available |
| Passive-skill or IV planning | Deferred |
| Automatic player context or save parsing | Not implemented |
| Game process or mod integration | Not implemented |
| Gameplay or multiplayer automation | Out of scope |
| Production Palworld knowledge prose | Not ingested |
| Installer, signed binary, and remote deployment | Not produced |

## Residual risks and deterministic failure modes

- The production snapshot is version-bound. A later Palworld patch requires a
  new compatibility review before it can be presented as supported.
- General explicit-capture planning retains topology-distinct labels and is
  intentionally bounded. Excessive frontiers return
  `search_limit_exceeded`, never an approximate route.
- Capture candidates are assertions supplied by the user. The candidate does
  not prove they are obtainable.
- Knowledge prose is synthetic only. Optional model output is untrusted,
  retrieval-first, citation-bound, and can fail closed.
- The source candidate requires local Python and Node toolchains. No installer
  or signed distribution has been reviewed.
- The local Vite and Uvicorn workflow is a development-grade loopback run path,
  not a hardened remote service.

## Rollback

Stop the two local processes and return the source checkout to the previous
accepted business commit:

```text
ec2e11ab3a836868c9989410e041bd857acf65ad
```

Do this in a clean disposable checkout or with ordinary Git history-preserving
operations. Preserve any local `.local/knowledge.sqlite3` file separately if
you want to keep the synthetic knowledge cache; it is not part of release
identity.

No remote deployment or migration is created by this candidate, so rollback
does not require infrastructure or data-schema reversal.

## Human accept or reject checklist

Accept the v1 candidate only if all of the following are true:

- [ ] the offline verifier reports `verified`;
- [ ] health and OpenAPI version match this package;
- [ ] synthetic knowledge is clearly disclosed and searchable;
- [ ] the owned-inventory route scenario succeeds exactly;
- [ ] the explicit-capture route uses exactly the submitted candidate and
      retains the acquisition warning;
- [ ] unsupported behavior fails explicitly without fabricated facts;
- [ ] the visible local workflow is usable for the intended v1 purpose;
- [ ] the supported-data and residual-risk boundaries are acceptable.

Reject the candidate if any item fails or if the product outcome does not meet
the intended v1 experience. Record the failed item and observed result; the
control program will create a focused follow-up loop rather than treating
rejection as final acceptance.
