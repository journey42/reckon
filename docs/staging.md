# Staging

Staging is a copy of production that reviewers and the regression pass can break
things in. Three resources, all in `reckon-rg`:

| resource | name | notes |
| --- | --- | --- |
| static site | `rhiz-web-staging` | canonical URL `https://mango-tree-0e1baaf0f.eastus2.1.azurestaticapps.net`, serves the `staging` branch |
| backend | `rhiz-backend-staging` | `https://rhiz-backend-staging.politefield-c0f001d2.eastus.azurecontainerapps.io`, scales 0→1 |
| database | `reckon-db-staging` | point-in-time restore of `reckon-db`; **stopped when not in use** |

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
export RHIZ_BASE=https://mango-tree-0e1baaf0f.eastus2.1.azurestaticapps.net
export DB_URL=<the dsn that backend is using>          # staging only — see guard
export RHIZ_REG_ADMIN_PASSWORD=... RHIZ_REG_USER_PASSWORD=...
python scripts/seed_staging_test_user.py               # accounts + fixtures
python scripts/staging_regression.py                   # 13 checks
```

Both scripts refuse to run against a production host. They are meant to be run
after every staging deploy, and before anything from `staging` is merged to
`master`.

## Post-test cleanup

```bash
az postgres flexible-server stop -g reckon-rg -n reckon-db-staging   # keeps data, stops compute
```

Stopped, the restore still bills storage (a few dollars a month); deleted, the
next restore costs another 5-10 minutes. Neither affects production.

## Known state / history

- `reckon-db-staging` was deleted at some point after 2026-09-26, which is why
  the staging backend has been broken since: its `db-url` secret points at a
  host that no longer resolves. Bring-up step 1 recreates it.
- Before 2026-10-26 the staging site's canonical URL was pinned to the
  `feed-declutter` branch so reviewers saw the newest approved build there; that
  also meant the URL 404'd whenever no `feed-declutter` build was current. It
  now follows the branch you deploy from.
- Staging sends **real** email if `AZURE_COMMUNICATION_CONNECTION_STRING` is set
  as a GitHub secret — it shares the `reckon.cc` / `rhiz.ai` ACS resource with
  production. Set `MAIL_DRY_RUN=1` on the staging container app if you want mail
  printed to the container log instead of sent.
