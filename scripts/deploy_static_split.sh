#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
STATICWA_CONFIG_TEMPLATE="${REPO_ROOT}/deploy/staticwebapp.config.json"

log() {
  printf '%s\n' "[split-deploy] $*"
}

die() {
  printf '%s\n' "[split-deploy][error] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

require_cmd az
require_cmd docker
require_cmd git
require_cmd python3
require_cmd npx

ENV_FILE=${ENV_FILE:-"${REPO_ROOT}/.env"}
if [[ -f "${ENV_FILE}" ]]; then
  log "Loading environment from ${ENV_FILE}"
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
else
  log "Environment file ${ENV_FILE} not found; relying on current shell variables"
fi

if ! az account show >/dev/null 2>&1; then
  die "Azure CLI is not logged in. Run 'az login' first."
fi

RG=${AZURE_RESOURCE_GROUP:-reckon-rg}
LOCATION=${AZURE_LOCATION:-eastus}
ACA_ENV_NAME=${ACA_ENV_NAME:-reckon-env}
BACKEND_APP_NAME=${BACKEND_APP_NAME:-reckon-backend-split}
BACKEND_IMAGE_NAME=${BACKEND_IMAGE_NAME:-reckon-backend}
SWA_NAME=${SWA_NAME:-reckon-static-web}
SWA_LOCATION=${SWA_LOCATION:-centralus}
SWA_SKU=${SWA_SKU:-Standard}
LINK_BACKEND=${LINK_BACKEND:-1}

DB_URL=${ACA_DB_URL:-${DB_URL:-}}
if [[ -z "${DB_URL}" ]]; then
  die "Set ACA_DB_URL (or DB_URL) to the production database connection string before running this script."
fi

# Normalise DB URL so SQLAlchemy understands it.
if [[ "${DB_URL}" != *"://"* ]]; then
  DB_URL="postgresql://${DB_URL}"
  log "Normalised DB_URL to use postgresql:// scheme"
fi

if [[ "${DB_URL}" == postgresql://* && "${DB_URL}" != *"sslmode="* ]]; then
  if [[ "${DB_URL}" == *"?"* ]]; then
    DB_URL="${DB_URL}&sslmode=require"
  else
    DB_URL="${DB_URL}?sslmode=require"
  fi
  log "Appended sslmode=require to DB_URL"
fi

IMAGE_TAG=${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD)}
BACKEND_IMAGE=${BACKEND_IMAGE:-${BACKEND_IMAGE_NAME}}

ACR_NAME=${ACR_NAME:-reckonregistry}

log "Ensuring Azure Container Registry ${ACR_NAME} exists"
if ! az acr show --name "${ACR_NAME}" --resource-group "${RG}" >/dev/null 2>&1; then
  die "ACR ${ACR_NAME} not found in resource group ${RG}. Create it first or set ACR_NAME."
fi

ACR_SERVER=$(az acr show --name "${ACR_NAME}" --resource-group "${RG}" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "${ACR_NAME}" --resource-group "${RG}" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "${ACR_NAME}" --resource-group "${RG}" --query "passwords[0].value" -o tsv)
ACR_SERVER=${ACR_SERVER//$'\r'/}
ACR_USERNAME=${ACR_USERNAME//$'\r'/}
ACR_PASSWORD=${ACR_PASSWORD//$'\r'/}

BACKEND_IMAGE_REF="${ACR_SERVER}/${BACKEND_IMAGE}:${IMAGE_TAG}"

log "Logging Docker into ${ACR_SERVER}"
if ! echo "${ACR_PASSWORD}" | docker login "${ACR_SERVER}" --username "${ACR_USERNAME}" --password-stdin >/dev/null; then
  die "Docker login to ${ACR_SERVER} failed"
fi

log "Resolving Container Apps environment ${ACA_ENV_NAME}"
if ! az containerapp env show --name "${ACA_ENV_NAME}" --resource-group "${RG}" >/dev/null 2>&1; then
  die "Container App environment ${ACA_ENV_NAME} not found in ${RG}"
fi

ENV_ID=$(az containerapp env show --name "${ACA_ENV_NAME}" --resource-group "${RG}" --query id -o tsv)
ENV_DOMAIN=$(az containerapp env show --name "${ACA_ENV_NAME}" --resource-group "${RG}" --query properties.defaultDomain -o tsv)
ENV_DOMAIN=${ENV_DOMAIN//$'\r'/}

if [[ -z "${PUBLIC_API_URL:-}" ]]; then
  PUBLIC_API_URL="https://${BACKEND_APP_NAME}.${ENV_DOMAIN}"
fi
log "Backend will be exposed at ${PUBLIC_API_URL}"

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  log "Building backend image ${BACKEND_IMAGE_REF}"
  docker build \
    --build-arg API_URL="${PUBLIC_API_URL}" \
    -t "${BACKEND_IMAGE_REF}" \
    "${REPO_ROOT}"

  log "Pushing backend image ${BACKEND_IMAGE_REF}"
  docker push "${BACKEND_IMAGE_REF}" >/dev/null
else
  log "Skipping backend image build/push (SKIP_BUILD=${SKIP_BUILD})"
fi

log "Deploying backend container app ${BACKEND_APP_NAME}"
if az containerapp show --name "${BACKEND_APP_NAME}" --resource-group "${RG}" >/dev/null 2>&1; then
  log "Updating existing Container App ${BACKEND_APP_NAME}"
  az containerapp registry set \
    --name "${BACKEND_APP_NAME}" \
    --resource-group "${RG}" \
    --server "${ACR_SERVER}" \
    --username "${ACR_USERNAME}" \
    --password "${ACR_PASSWORD}" >/dev/null

  az containerapp secret set \
    --name "${BACKEND_APP_NAME}" \
    --resource-group "${RG}" \
    --secrets "db-url=${DB_URL}" >/dev/null

  az containerapp update \
    --name "${BACKEND_APP_NAME}" \
    --resource-group "${RG}" \
    --image "${BACKEND_IMAGE_REF}" \
    --min-replicas 1 \
    --max-replicas 3 \
    --cpu 0.5 \
    --memory 1Gi \
    --set-env-vars \
      RUN_MIGRATIONS_ON_START=0 \
      DB_URL=secretref:db-url \
      API_URL="${PUBLIC_API_URL}" \
      TRANSFORMERS_CACHE=/tmp/.cache/huggingface/hub >/dev/null

  az containerapp ingress enable \
    --name "${BACKEND_APP_NAME}" \
    --resource-group "${RG}" \
    --type external \
    --target-port 8000 \
    --transport auto >/dev/null
else
  log "Creating new Container App ${BACKEND_APP_NAME}"
  az containerapp create \
    --name "${BACKEND_APP_NAME}" \
    --resource-group "${RG}" \
    --environment "${ACA_ENV_NAME}" \
    --image "${BACKEND_IMAGE_REF}" \
    --ingress external \
    --target-port 8000 \
    --min-replicas 1 \
    --max-replicas 3 \
    --cpu 0.5 \
    --memory 1Gi \
    --registry-server "${ACR_SERVER}" \
    --registry-username "${ACR_USERNAME}" \
    --registry-password "${ACR_PASSWORD}" \
    --secrets "db-url=${DB_URL}" \
    --env-vars \
      RUN_MIGRATIONS_ON_START=0 \
      DB_URL=secretref:db-url \
      API_URL="${PUBLIC_API_URL}" \
      TRANSFORMERS_CACHE=/tmp/.cache/huggingface/hub >/dev/null
fi

BACKEND_FQDN=$(az containerapp show --name "${BACKEND_APP_NAME}" --resource-group "${RG}" --query properties.configuration.ingress.fqdn -o tsv)
BACKEND_FQDN=${BACKEND_FQDN//$'\r'/}
BACKEND_URL="https://${BACKEND_FQDN}"
log "Backend reachable at ${BACKEND_URL}"

# Ensure Static Web App exists.
if ! az staticwebapp show --name "${SWA_NAME}" --resource-group "${RG}" >/dev/null 2>&1; then
  log "Creating Static Web App ${SWA_NAME} (${SWA_SKU})"
  az staticwebapp create \
    --name "${SWA_NAME}" \
    --resource-group "${RG}" \
    --location "${SWA_LOCATION}" \
    --sku "${SWA_SKU}" >/dev/null
else
  log "Using existing Static Web App ${SWA_NAME}"
fi

# Optionally link backend for integrated auth/proxy.
if [[ "${LINK_BACKEND}" == "1" ]]; then
  BACKEND_ID=$(az containerapp show --name "${BACKEND_APP_NAME}" --resource-group "${RG}" --query id -o tsv)
  BACKEND_ID=${BACKEND_ID//$'\r'/}
  log "Linking backend ${BACKEND_ID} to Static Web App ${SWA_NAME}"
  if ! az staticwebapp backends link \
    --name "${SWA_NAME}" \
    --resource-group "${RG}" \
    --backend-resource-id "${BACKEND_ID}" \
    --backend-region "${LOCATION}" >/dev/null; then
    log "Warning: backend link failed (requires Standard SKU). Continuing without link."
  fi
fi

# Build static assets pointing to backend URL.
export API_URL="${BACKEND_URL}"
log "Exporting frontend with API_URL=${API_URL}"
reflex export --frontend-only --no-zip >/dev/null

STATIC_SOURCE="${REPO_ROOT}/.web/build/client"
STATIC_OUTPUT="${REPO_ROOT}/.web/_static"
if [[ ! -d "${STATIC_SOURCE}" ]]; then
  die "Expected Reflex export output at ${STATIC_SOURCE}; run 'reflex export --frontend-only --no-zip' locally to verify."
fi
rm -rf "${STATIC_OUTPUT}"
mkdir -p "${STATIC_OUTPUT}"
cp -a "${STATIC_SOURCE}/." "${STATIC_OUTPUT}/"
cp "${STATICWA_CONFIG_TEMPLATE}" "${STATIC_OUTPUT}/staticwebapp.config.json"

# Obtain deployment token, preferring env override.
if [[ -z "${SWA_DEPLOYMENT_TOKEN:-}" ]]; then
  log "Fetching Static Web App deployment token"
  SWA_DEPLOYMENT_TOKEN=$(az staticwebapp secrets list --name "${SWA_NAME}" --resource-group "${RG}" --query properties.apiKey -o tsv)
fi

if [[ -z "${SWA_DEPLOYMENT_TOKEN}" ]]; then
  die "Unable to resolve Static Web App deployment token. Set SWA_DEPLOYMENT_TOKEN."
fi

log "Deploying static assets to ${SWA_NAME}"
npx -y @azure/static-web-apps-cli@2 deploy \
  --env production \
  --app-name "${SWA_NAME}" \
  --resource-group "${RG}" \
  --app-location "${STATIC_OUTPUT}" \
  --deployment-token "${SWA_DEPLOYMENT_TOKEN}" >/dev/null

log "Deployment complete"
log "Backend: ${BACKEND_URL}"
SWA_DEFAULT_URL=$(az staticwebapp show --name "${SWA_NAME}" --resource-group "${RG}" --query properties.defaultHostname -o tsv)
log "Frontend: https://${SWA_DEFAULT_URL}"
log "Remember to update OAuth redirects, CORS policies, and DNS/custom domains as needed before cutting traffic over."
