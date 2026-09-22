#!/usr/bin/env bash
# Provision the Rhiz staging environment.
#
# Reuses production's Container App Environment (rhiz-env) and ACR
# (rhizregistry), so staging adds no environment-management fee. The database
# is a point-in-time restore of reckon-db onto the cheap burstable SKU, so
# staging tests against real data. Pair with stopping the DB between sessions.
#
# Idempotent-ish: each step is skipped if the resource already exists.
set -euo pipefail

RG="${RG:-reckon-rg}"
SUB="${SUB:-ba96b303-2d6d-4450-82a1-50de5bb7b50e}"
DB_SRC="${DB_SRC:-reckon-db}"
DB_STG="${DB_STG:-reckon-db-staging}"
ACA_STG="${ACA_STG:-rhiz-backend-staging}"
SWA_STG="${SWA_STG:-rhiz-web-staging}"
ACR="${ACR:-rhizregistry}"
IMAGE="${IMAGE:-rhizregistry.azurecr.io/rhiz-backend:latest}"

az account set --subscription "$SUB" 2>/dev/null

echo "== 1. Postgres: point-in-time restore of $DB_SRC -> $DB_STG =="
if az postgres flexible-server show --name "$DB_STG" --resource-group "$RG" >/dev/null 2>&1; then
  echo "   already exists, skipping."
else
  # Same admin credentials as the source; a B1ms keeps the staging bill low.
  # Inherits the source's SKU (B1ms) and storage (32 GB) — already the cheap tier.
  az postgres flexible-server restore \
    --resource-group "$RG" \
    --name "$DB_STG" \
    --source-server "$DB_SRC" \
    --yes
  echo "   restore submitted (async; server appears in a few minutes)."
fi

echo "== 2. Static Web App: $SWA_STG (Free tier) =="
if az staticwebapp show --name "$SWA_STG" --resource-group "$RG" >/dev/null 2>&1; then
  echo "   already exists, skipping."
else
  az staticwebapp create \
    --name "$SWA_STG" --resource-group "$RG" --sku Free \
    --location eastus2 >/dev/null
  echo "   created."
fi

echo "== 3. Container App: $ACA_STG (shares rhiz-env; scales to zero) =="
# The database connection string equals production's except for the host:
# a restore keeps the source server's admin login and password.
STAGING_HOST="$DB_STG.postgres.database.azure.com"
if [ -z "${DB_URL_STAGING:-}" ]; then
  DB_URL_STAGING="$(python3 - "$STAGING_HOST" <<'PY'
import os, re, sys
src = os.environ.get("DB_URL", "")
host = sys.argv[1]
# swap the host in the source URL, preserving scheme/user/pass/db
print(re.sub(r"@[^/]+", "@" + host, src, count=1))
PY
)"
fi
export DB_URL_STAGING
echo "   staging DB host: $STAGING_HOST"

if az containerapp show --name "$ACA_STG" --resource-group "$RG" >/dev/null 2>&1; then
  echo "   already exists, skipping."
else
  # Registry auth mirrors production (admin username = registry name).
  ACR_PASS=$(az acr credential show --name "$ACR" --query "passwords[0].value" -o tsv)
  az containerapp create \
    --name "$ACA_STG" \
    --resource-group "$RG" \
    --environment rhiz-env \
    --image "$IMAGE" \
    --registry-server "$ACR.azurecr.io" \
    --registry-username "$ACR" \
    --registry-password "$ACR_PASS" \
    --ingress external --target-port 8000 --transport auto \
    --min-replicas 0 --max-replicas 1 \
    --secrets db-url="$DB_URL_STAGING" posthog-key="${POSTHOG_SECRET_KEY:-}" \
    --env-vars \
      DB_URL=secretref:db-url \
      POSTHOG_SECRET_KEY=secretref:posthog-key \
      RUN_MIGRATIONS_ON_START=1 \
      SUNEDITOR_TOOLBAR_ENABLED=0 \
      PUBLIC_BASE_URL="https://placeholder-staging.example" \
      API_URL="https://placeholder-staging.example" \
    --query "properties.configuration.ingress.fqdn" -o tsv
  echo "   created."
fi

FQDN=$(az containerapp show --name "$ACA_STG" --resource-group "$RG" \
  --query "properties.configuration.ingress.fqdn" -o tsv)
SWA_URL=$(az staticwebapp show --name "$SWA_STG" --resource-group "$RG" \
  --query "defaultHostname" -o tsv)

echo "== 4. Point app env vars at the real staging URLs =="
az containerapp update --name "$ACA_STG" --resource-group "$RG" \
  --set-env-vars \
    API_URL="https://$FQDN" \
    PUBLIC_BASE_URL="https://$SWA_URL" \
    DB_URL=secretref:db-url \
    POSTHOG_SECRET_KEY=secretref:posthog-key \
    RUN_MIGRATIONS_ON_START=1 \
    SUNEDITOR_TOOLBAR_ENABLED=0 \
  >/dev/null

echo
echo "STAGING BACKEND : https://$FQDN"
echo "STAGING FRONTEND: https://$SWA_URL"
echo "STAGING DB      : $DB_STG ($STAGING_HOST) — remember: stop it between test sessions."
