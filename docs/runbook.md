# Day-of runbook (production)

The short version: **read the logs, restart if wedged, don't deploy anything new.**

Production is `www.rhiz.ai` (Static Web App `rhiz-web`, branch `master`) and
`rhiz-backend` (Container App, `reckon-rg`, East US). Database is
`reckon-db` (PostgreSQL 16, General Purpose `D2ds_v5`).

## Is it up?

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://www.rhiz.ai/demo     # 200
curl -sS -o /dev/null -w '%{http_code}\n' \
  'https://rhiz-backend.politefield-c0f001d2.eastus.azurecontainerapps.io/_event/?token=x'  # 400 = healthy
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

There is **one replica on purpose**: this is an ACA *express* environment, which
does not support sticky sessions, and Reflex keeps a user's state in the process
it connected to. More than one replica means people get silently logged out or
lose an answer mid-session. Do not raise `maxReplicas`.

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

## Email

Credentials come from the Container App secret `acs-connection-string`
(`AZURE_COMMUNICATION_CONNECTION_STRING`). `MAIL_DRY_RUN` must **not** be set in
production, or nothing is sent. The deploy workflow refuses to roll out an image
if the credential is missing, so a successful deploy implies mail is configured.

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
