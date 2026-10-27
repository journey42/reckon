# Staging

Staging is a copy of production that reviewers and the regression pass can break
things in. Three resources, all in `reckon-rg`:

| resource | name | notes |
| --- | --- | --- |
| static site | `rhiz-web-staging` | canonical URL `https://mango-tree-0e1baaf0f.1.azurestaticapps.net` — exactly as `properties.defaultHostname` reports it — serving the `staging` branch |
| backend | `rhiz-backend-staging` | `https://rhiz-backend-staging.politefield-c0f001d2.eastus.azurecontainerapps.io` |
| database | `reckon-db-staging` | point-in-time restore of `reckon-db` |

Two things about the staging backend that cost time once already:

- **`minReplicas` must be 1, not 0.** At 0 the revision is never activated, so
  the container never starts — and because migrations run in the container's
  start path, `RUN_MIGRATIONS_ON_START=1` quietly does nothing and requests get
  `{"error":"Not found"}` from the ingress instead of the app. Production runs
- **The app had no ingress at all** (`external: null`, no target port), so
  nothing could reach it — which is also why it never activated. Enable it with
  `az containerapp ingress enable -n rhiz-backend-staging -g reckon-rg --type external --target-port 8000 --transport auto`.
  `az containerapp update --set properties.configuration.ingress.external=true`
  reports `Succeeded` and changes nothing, so verify against the ARM REST GET
  rather than the CLI's exit code.

### Things about this app the CLI will not tell you

- `az containerapp logs show` dies with `KeyError: 'eventStreamEndpoint'`, and
  the ARM `listLogs` operation 404s. To see the container's own output, run the
  deployed image locally: `docker pull rhizregistry.azurecr.io/rhiz-backend:<tag>`
  and `docker run` it with `-e DB_URL=... -e RUN_MIGRATIONS_ON_START=1`. That is
  how the migration path was verified end to end.
- `az containerapp revision restart` returns `InternalServerError` for this app.
  Nothing else reliably restarts a running container either: scaling to 0 does
  not tear the replica down while traffic keeps arriving, and re-applying the
  same image creates no revision. To force a fresh start, change something in
  the template (any env var value).
- If the FQDN answers `{"error":"App is not available"}` while the ARM API
  insists `healthState: Healthy, replicas: 1, trafficWeight: 100`, the rollout is
  wedged. Forcing a new revision clears it. Production, in the same managed
  environment, keeps serving throughout.
- **`PUBLIC_BASE_URL` must be the default hostname, not a region-qualified
  guess.** `mango-tree-0e1baaf0f.eastus2.1.azurestaticapps.net` resolves to
  nothing for this site; `mango-tree-0e1baaf0f.1.azurestaticapps.net` is the
  host. Per-branch *environments* do use the longer form
  (`mango-tree-0e1baaf0f-feeddeclutter.eastus2.1…`). Check with
  `az staticwebapp show -n rhiz-web-staging -g reckon-rg` rather than memory.

The database is a restore rather than a schema-only fixture on purpose: the
things that go wrong here are the things that only real rows show — a group
whose question lives on the founding concept, a room with a deadline already
past, an account that never verified.

## Bring it up

Run these from a machine with `az` logged in as an Owner of the subscription.
Nothing here touches production: the restore *reads* production, the workflows
are `workflow_dispatch` only, and `master` is the only branch that can deploy
production.

```bash
# 1. Database: restore to "now" (7 days of PITR are kept on reckon-db).
az postgres flexible-server restore \
  --resource-group reckon-rg --name reckon-db-staging --source-server reckon-db \
  --sku-name Standard_B1ms --storage-size 32 --public-access 0.0.0.0 \
  --yes
# --public-access 0.0.0.0 is the "Azure services" rule, which is what the
# container app needs; add your own IP too if you want psql access.

# 2. Point the workflow's secret at the restore. The restore keeps production's
#    login and password, so the staging DSN is production's DB_URL with the host
#    swapped. This pipes it straight from Azure into GitHub without printing it.
SUB=$(az account show --query id -o tsv)
az rest --method post \
  --url "/subscriptions/$SUB/resourceGroups/reckon-rg/providers/Microsoft.App/containerApps/rhiz-backend/listSecrets?api-version=2024-02-02-preview" \
  --body '{}' \
  | python3 -c '
import json,sys,re
d=json.load(sys.stdin)
dsn=next(s["value"] for s in d["value"] if s["name"]=="db-url")
sys.stdout.write(re.sub(r"@[^/?]+", "@reckon-db-staging.postgres.database.azure.com", dsn, count=1))
' | gh secret set DB_URL_STAGING --repo journey42/reckon

# 3. Frontend, from the staging branch.
gh workflow run "Deploy Static Web App (Staging)" --ref staging

# 4. Backend, from the staging branch. Runs the pending migrations on start.
gh workflow run "Deploy Backend (Staging)" --ref staging
gh run watch                                      # or: gh run list

# 5. Keep it awake, or nothing above takes effect (see the note at the top).
az containerapp update -n rhiz-backend-staging -g reckon-rg --min-replicas 1
```

Which branch counts as "production" for the static site lives on the resource,
not in the workflow:

```bash
az rest --method get \
  --url "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/reckon-rg/providers/Microsoft.Web/staticSites/rhiz-web-staging?api-version=2022-09-01" \
  --query properties.branch -o tsv          # staging
```

The backend image is built with `API_URL` = the staging backend FQDN, and the
frontend is built with the same value baked in, so the two must be deployed
from the same branch or the site will talk to a backend running different code.

## Regression pass

`scripts/staging_regression.py` drives the deployed site in a real browser and
checks the deployment, not just the code: which backend the socket actually
connects to, whether deep links survive the static config, whether `/outbox.js`
is served instead of swallowed by the SPA fallback, and the specific bugs the
client reported.

```bash
export RHIZ_BASE=https://mango-tree-0e1baaf0f.1.azurestaticapps.net
export DB_URL=<the dsn that backend is using>          # staging only — see guard
export RHIZ_REG_ADMIN_PASSWORD=... RHIZ_REG_USER_PASSWORD=...
python scripts/seed_staging_test_user.py               # accounts + fixtures
python scripts/staging_regression.py                   # 14 checks
```

Both scripts refuse to run against a production host. They are meant to be run
after every staging deploy, and before anything from `staging` is merged to
`master`.

The seed script creates two throwaway accounts (`regtest_admin`,
`regtest_user`) and four fixtures: a group whose question sits on the group row,
a group whose question exists only on the founding concept (the #11653 shape), a
timed question and a permanent one. It goes through the app's own
`create_group`/`create_room`, so the rows are shaped like real ones rather than
like test data.

## Post-test cleanup

Staging is meant to stay up while the client is validating: DB running, backend
at one replica. When the review is over,

```bash
az postgres flexible-server stop -g reckon-rg -n reckon-db-staging
az containerapp update -n rhiz-backend-staging -g reckon-rg --min-replicas 0
```

Stopped, the restore still bills storage (a few dollars a month); deleted, the
next restore costs another 5-10 minutes. Neither affects production. Remember
that a stopped backend means migrations do not run — start it before trusting
the schema.

## Before the event: the migration

`RUN_MIGRATIONS_ON_START` used to be a lie. `scripts/db_migrate.py` stamped
`alembic_version` and stopped; nothing in the repo ran `alembic upgrade head`, so
a revision committed under `migrations/versions` never reached a deployed
database — and the stamp was written *back* to `LATEST_SQL_MIGRATION` on every
start, so a hand-applied schema counted as never applied. It now walks the stamp
forward to each head that is genuinely a descendant of it, and exits non-zero
rather than serve a schema it does not match.

Confirm it moved after a deploy:

```bash
psql "$DB_URL" -Atc "select version_num from alembic_version"   # expect the new head
```

Verified: staging went `a9b8c7d6e5f4 -> c9d1e2f3a4b5` and
`roomparticipant.intent_version` appeared; production is still `a9b8c7d6e5f4`
with the column absent, which is correct — the migration is staged, not applied.

## Known state / history

- `reckon-db-staging` was deleted at some point after 2026-09-26, which is why
  the staging backend has been broken since: its `db-url` secret points at a
  host that no longer resolves. Bring-up step 1 recreates it.
- Before 2026-10-26 the staging site's canonical URL was pinned to the
  `feed-declutter` branch so reviewers saw the newest approved build there; that
  also meant the URL 404'd whenever no `feed-declutter` build was current. It
  now follows the branch you deploy from.
- Staging sends **real** email only if you ask it to. The credential is wired from
  the `AZURE_COMMUNICATION_CONNECTION_STRING` GitHub secret, but the deploy sets
  `MAIL_DRY_RUN=1` by default, so staging prints mail to the container log instead
  of sending it — staging shares the `reckon.cc` / `rhiz.ai` ACS resource with
  production, and a verification email from staging is a real email to a real
  person. To test the mail flows for real: create the repository variable
  `STAGING_MAIL_DRY_RUN=0` (Settings → Secrets and variables → Actions → Variables)
  and redeploy, then use addresses you control.
