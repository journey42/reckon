# Day-of runbook (production)

The short version: **read the logs, restart if wedged, don't deploy anything new.**

Production is `www.rhiz.ai` (Static Web App `rhiz-web`, branch `master`) and
`rhiz-backend-ha` (Container App, `reckon-rg`, East US, **1 replica, sticky
sessions**). Database is `reckon-db` (PostgreSQL 16, **Burstable `B1ms`,
HA off**).

That is the post-conference cost posture, not the capacity used during the
event. Before the conference production ran **2 replicas** and `D2ds_v5` with
**zone-redundant HA**; both were downgraded afterwards on the basis of measured
load (DB CPU peaked around 6%, 14 connections, ~1-7 backend requests/hour).
Raise it again — matching the shape below — before a high-traffic event:

```bash
az containerapp update -n rhiz-backend-ha -g reckon-rg --min-replicas 2 --max-replicas 3
az postgres flexible-server update -n reckon-db -g reckon-rg \
  --zonal-resiliency Enabled --sku-name Standard_D2ds_v5 --tier GeneralPurpose
```

Zone-redundant HA is not available on Burstable, so re-enabling HA means going
back to a General Purpose SKU; each `az postgres flexible-server update` is a
restart (a few minutes), so do them in a quiet window. `B1ms` allows 100
connections, which is comfortable — the app held 14.

Two older things still exist and are deliberately kept:

* `rhiz-backend` — the previous single-replica app on the *express* environment
  (`rhiz-env`). It is the rollback target and no longer receives traffic. It is
  now at `--min-replicas 0`, so a rollback to it pays a cold start (~30-60s) on
  the first request; the image (`5a064fe`) is still in the registry.
* `rhiz-env` — the express environment. `rhiz-env-ha` is the standard
  (workload-profiles) environment that supports session affinity.

## Is it up?

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://www.rhiz.ai/demo     # 200
curl -sS -o /dev/null -w '%{http_code}\n' \
  'https://rhiz-backend-ha.proudbay-01371b35.eastus.azurecontainerapps.io/_event/?token=x'  # 400 = healthy
```

`400 "Invalid transport"` is the app saying hello. `502`/`503` is the platform or
a crashed container. The scheduled **Uptime check** workflow runs the same
checks every 10 minutes and fails loudly.

## What is it doing?

`az containerapp logs show` **does not work for this app** — it needs
`properties.eventStreamEndpoint`, which this environment does not expose, and it
dies with `KeyError: 'eventStreamEndpoint'`. The console output is forwarded to a
Log Analytics workspace, so query that:

```bash
python scripts/prod_logs.py --minutes 15            # recent lines
python scripts/prod_logs.py --minutes 60 --errors   # only error-ish lines
python scripts/prod_logs.py --grep rotate           # find a specific thing
```

Requires `az login` with read access to `workspace-reckonrgzwFp`.

## Restarting the backend

`rhiz-backend-ha` runs **2 replicas with sticky sessions** (`stickySessions.
affinity = sticky`), which is what makes replicas safe: Reflex keeps a user's
state in the process they connected to, so the platform must keep routing that
browser to the same one. Session affinity is only available on standard
(workload-profiles) environments — the express environment cannot do it, which
is why the old `rhiz-backend` was pinned to a single replica.

Do not remove the sticky-session setting while running more than one replica.

`az containerapp revision restart` may return `InternalServerError`. In order of
preference:

```bash
# 1. nudge the template (creates a new revision)
az containerapp update -n rhiz-backend -g reckon-rg \
  --set-env-vars DEPLOY_PING=$(date +%s)

# 2. or take it down and back up
az containerapp update -n rhiz-backend -g reckon-rg --min-replicas 0
#    then, after it has actually gone:
az containerapp update -n rhiz-backend -g reckon-rg --min-replicas 1
```

A restart costs ~30 seconds. There is a Startup (5 min grace) and a Liveness
probe (TCP on 8000) — the latter only checks the process still accepts
connections, so it will not restart the app for a 400 on `/_event`.

## Database

Migrations run automatically at container start
(`RUN_MIGRATIONS_ON_START=1`) and are idempotent; a bad migration stops the
container rather than serving a mismatched schema, which is why the first place
to look after a deploy is the logs.

```bash
psql "$DB_URL" -Atc "select version_num from alembic_version"   # expect c9d1e2f3a4b5
psql "$DB_URL" -Atc "select count(*) from \"user\""             # 138 at time of writing
```

Point-in-time restore is enabled (7 days). A pre-upgrade dump is kept at
`~/backups/reckon/`. Any restore is a new server plus a DSN secret change in the
Container App — not a quick fix, so prefer the dump only if data is actually lost.

The compute SKU is a cost decision, not a schema one: changing it never touches
rows. Taken before the November downgrade, `reckon-db` was 13 MB with 138 users,
17 groups, 1005 reckonings; the same table counts and the same `demo_room_slug`
were present immediately after.

## Email

Credentials come from the Container App secret `acs-connection-string`
(`AZURE_COMMUNICATION_CONNECTION_STRING`). `MAIL_DRY_RUN` must **not** be set in
production, or nothing is sent. The deploy workflow refuses to roll out an image
if the credential is missing, so a successful deploy implies mail is configured.

## Rollback (if the HA backend misbehaves)

The frontend's backend URL is baked in at export time, so rolling back is a
setting change plus one workflow run — about 4 minutes, no code revert:

```bash
gh variable set PUBLIC_API_URL --body https://rhiz-backend.politefield-c0f001d2.eastus.azurecontainerapps.io
gh workflow run "Deploy Static Web App" --ref master
```

That points `www.rhiz.ai` back at the old single-replica app. It is kept for
exactly this reason, but it now sits at `--min-replicas 0`, so a rollback pays a
cold start on the first request. To flip forward again, set the variable to
`https://rhiz-backend-ha.proudbay-01371b35.eastus.azurecontainerapps.io` and re-run the workflow.

Last-resort artefacts (pre-HA state) are in `/home/vince/backups/reckon/pre-ha-20261103T0044Z`: container app JSON, DB dump,
and `swa-build-5a064fe.tar.gz` — a byte-exact rebuild of the frontend that was
live before the switch.

## The registry keeps three images

`rhizregistry` is Basic, which includes 10 GB; every deploy tags an image with the
commit SHA, so the repository had grown to 93 manifests and 26.5 GB of layers —
about $1.6/month of storage and a slow `az acr` on every call. It was pruned to
the three images that can matter: `fec4732` (deployed now, also `latest`),
`5a064fe` (the rollback app) and `1f5b7ae` (the deploy before that).

So an older tag being gone is expected: rebuild it from the commit instead of
hunting for the image —

```bash
TAG=${GIT_SHA::7}
docker build --build-arg API_URL=https://rhiz-backend-ha.proudbay-01371b35.eastus.azurecontainerapps.io \
  -t rhizregistry.azurecr.io/rhiz-backend:$TAG .
docker push rhizregistry.azurecr.io/rhiz-backend:$TAG
```

— and when pruning again, `--dry-run` first: `az acr manifest list-metadata -r rhizregistry -n rhiz-backend`
lists manifests, and only a digest with no kept tag can go.

## Deploying (only if something must change)

- Backend: push to `master` → `Deploy Backend Container App` runs automatically.
- Frontend: **manual** — Actions → *Deploy Static Web App* → Run workflow
  (branch `master`). Deploy the backend first, then the frontend, so a new
  frontend never talks to an old backend.
- After either: check `python scripts/prod_logs.py --minutes 5 --errors` and
  confirm `https://www.rhiz.ai/demo` still renders.

The CI service principal's secret now expires **2027-11-02**. If a deploy fails
with `AADSTS7000222`, that is an expired credential, not a code problem.

## Known, accepted limitations

- No sticky sessions (express environment) → single replica, as above.
- Logs are not streamable; query Log Analytics with `scripts/prod_logs.py`.
- `Warning: Database is not initialized, run reflex db init first.` and the
  `RouterData.page` deprecation are printed at every start and are benign.
- The ACS key that was once hardcoded in the repo has **not** been rotated yet;
  do that after the event.
