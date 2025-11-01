#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
TEMPLATE_PATH="${REPO_ROOT}/deploy/containerapp.yaml"

log() {
  printf '%s\n' "[deploy] $*"
}

die() {
  printf '%s\n' "[deploy][error] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

require_cmd az
require_cmd docker
require_cmd git
require_cmd python3


ENV_FILE=${ENV_FILE:-"${REPO_ROOT}/.env"}
if [[ -f "${ENV_FILE}" ]]; then
  log "Loading environment from ${ENV_FILE}"
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
else
  log "Environment file ${ENV_FILE} not found; falling back to current shell variables"
fi

if ! az account show >/dev/null 2>&1; then
  die "Azure CLI is not logged in. Run 'az login' first."
fi

RG=${AZURE_RESOURCE_GROUP:-reckon-rg}
LOCATION=${AZURE_LOCATION:-eastus}
ENV_NAME=${ACA_ENV_NAME:-reckon-env}
APP_NAME=${ACA_APP_NAME:-reckon-app}
ACR_NAME=${ACR_NAME:-reckonregistry}
DOMAIN_INPUT=${ACA_DOMAIN:-reckon.cc}
DOMAIN_NO_HTTP=${DOMAIN_INPUT#http://}
DOMAIN=${DOMAIN_NO_HTTP#https://}
DEFAULT_PUBLIC_URL="https://${DOMAIN}"
PUBLIC_URL_RAW=${ACA_PUBLIC_URL:-${DEFAULT_PUBLIC_URL}}
if [[ ${PUBLIC_URL_RAW} == http://* || ${PUBLIC_URL_RAW} == https://* ]]; then
  PUBLIC_URL=${PUBLIC_URL_RAW}
else
  PUBLIC_URL="https://${PUBLIC_URL_RAW}"
fi
IMAGE_TAG=${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD)}
APP_IMAGE_NAME=${APP_IMAGE_NAME:-reckon-app}
CADDY_IMAGE_NAME=${CADDY_IMAGE_NAME:-reckon-caddy}

DB_URL=${ACA_DB_URL:-${DB_URL:-}}
if [[ -z "${DB_URL}" ]]; then
  die "Set ACA_DB_URL (or DB_URL) to the production database connection string before running this script."
fi

# Normalize DB connection string so SQLAlchemy can parse it.
if [[ "${DB_URL}" != *"://"* ]]; then
  DB_URL="postgresql://${DB_URL}"
  log "Normalized DB_URL to use postgresql:// scheme"
fi

# Ensure SSL is required unless explicitly set.
if [[ "${DB_URL}" == postgresql://* && "${DB_URL}" != *"sslmode="* ]]; then
  if [[ "${DB_URL}" == *"?"* ]]; then
    DB_URL="${DB_URL}&sslmode=require"
  else
    DB_URL="${DB_URL}?sslmode=require"
  fi
  log "Appended sslmode=require to DB_URL"
fi

log "Ensuring Azure Container Apps extension is available"
az config set extension.use_dynamic_install=yes_without_prompt >/dev/null
if ! az extension show --name containerapp >/dev/null 2>&1; then
  az extension add --name containerapp >/dev/null
fi

log "Using resource group: ${RG}"
log "Granting registry permissions to the current principal"
ALIAS="acr-pusher-${RANDOM}"
az ad signed-in-user show --query objectId -o tsv >/dev/null 2>&1 || ALIAS=""
if [[ -n "${ALIAS}" ]]; then
  PRINCIPAL_ID=$(az ad signed-in-user show --query objectId -o tsv)
  az role assignment create --assignee "${PRINCIPAL_ID}" --scope $(az acr show --name "${ACR_NAME}" --resource-group "${RG}" --query id -o tsv) --role "AcrPush" >/dev/null 2>&1 || true
fi

log "Using container app environment: ${ENV_NAME}"
log "Using container app name: ${APP_NAME}"
log "Image tag: ${IMAGE_TAG}"
log "Public URL: ${PUBLIC_URL}"

if ! az group show --name "${RG}" >/dev/null 2>&1; then
  die "Resource group '${RG}' not found."
fi

if ! az acr show --name "${ACR_NAME}" --resource-group "${RG}" >/dev/null 2>&1; then
  log "Creating Azure Container Registry ${ACR_NAME}"
  az acr create \
    --name "${ACR_NAME}" \
    --resource-group "${RG}" \
    --location "${LOCATION}" \
    --sku Basic \
    --admin-enabled true >/dev/null
else
  log "Using existing Azure Container Registry ${ACR_NAME}"
fi

# Ensure admin user is enabled so docker push works
az acr update --name "${ACR_NAME}" --resource-group "${RG}" --admin-enabled true >/dev/null

ACR_SERVER=$(az acr show --name "${ACR_NAME}" --resource-group "${RG}" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "${ACR_NAME}" --resource-group "${RG}" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "${ACR_NAME}" --resource-group "${RG}" --query "passwords[0].value" -o tsv)
# Normalize potential Windows-style line endings returned by az CLI
ACR_SERVER=${ACR_SERVER//$'\r'/}
ACR_USERNAME=${ACR_USERNAME//$'\r'/}
ACR_PASSWORD=${ACR_PASSWORD//$'\r'/}

APP_IMAGE="${ACR_SERVER}/${APP_IMAGE_NAME}:${IMAGE_TAG}"
CADDY_IMAGE="${ACR_SERVER}/${CADDY_IMAGE_NAME}:${IMAGE_TAG}"

log "Logging Docker into ${ACR_SERVER}"
if command -v docker >/dev/null 2>&1; then
  if ! echo "${ACR_PASSWORD}" | docker login "${ACR_SERVER}" --username "${ACR_USERNAME}" --password-stdin >/dev/null; then
    log "Admin credentials failed, trying token-based login"
    ACR_TOKEN=$(az acr login --name "${ACR_NAME}" --expose-token --output tsv --query accessToken)
    if [[ -z "${ACR_TOKEN}" ]]; then
      die "Failed to obtain ACR access token for ${ACR_NAME}"
    fi
    ACR_TOKEN=${ACR_TOKEN//$'
'/}
    echo "${ACR_TOKEN}" | docker login "${ACR_SERVER}" --username 00000000-0000-0000-0000-000000000000 --password-stdin >/dev/null
  fi
else
  die "Docker CLI not available; cannot log into ${ACR_SERVER}"
fi

log "Building application image ${APP_IMAGE}"
docker build \
  --build-arg API_URL="${PUBLIC_URL}" \
  -t "${APP_IMAGE}" \
  "${REPO_ROOT}"

log "Building caddy image ${CADDY_IMAGE}"
docker build \
  -t "${CADDY_IMAGE}" \
  -f "${REPO_ROOT}/Caddy.Dockerfile" \
  "${REPO_ROOT}"

log "Pushing images to ${ACR_SERVER}"
docker push "${APP_IMAGE}" >/dev/null
docker push "${CADDY_IMAGE}" >/dev/null

# Ensure Microsoft.App resource provider is registered before managing env
if [[ $(az provider show --namespace Microsoft.App --query "registrationState" -o tsv 2>/dev/null || echo Unknown) != "Registered" ]]; then
  log "Registering Microsoft.App resource provider (this may take a minute)"
  az provider register --namespace Microsoft.App --wait >/dev/null
fi

ENV_ID=$(az containerapp env show --name "${ENV_NAME}" --resource-group "${RG}" --query id -o tsv 2>/dev/null || echo "")
if [[ -z "${ENV_ID}" ]]; then
  log "Container Apps environment ${ENV_NAME} not found; creating it now"
  az containerapp env create \
    --name "${ENV_NAME}" \
    --resource-group "${RG}" \
    --location "${LOCATION}" >/dev/null
  ENV_ID=$(az containerapp env show --name "${ENV_NAME}" --resource-group "${RG}" --query id -o tsv)
else
  log "Found existing Container Apps environment ${ENV_NAME}"
fi

TEMP_YAML=$(mktemp)
trap 'rm -f "${TEMP_YAML}"' EXIT

log "Preparing deployment manifest"
export APP_NAME_ENV="${APP_NAME}"
export LOCATION_ENV="${LOCATION}"
export ENV_ID_ENV="${ENV_ID}"
export ACR_SERVER_ENV="${ACR_SERVER}"
export ACR_USERNAME_ENV="${ACR_USERNAME}"
export ACR_PASSWORD_ENV="${ACR_PASSWORD}"
export DB_URL_ENV="${DB_URL}"
export CADDY_IMAGE_ENV="${CADDY_IMAGE}"
export APP_IMAGE_ENV="${APP_IMAGE}"
export DOMAIN_ENV="${DOMAIN}"
export PUBLIC_URL_ENV="${PUBLIC_URL}"

python3 - "${TEMPLATE_PATH}" "${TEMP_YAML}" <<'PY'
import sys, os
from pathlib import Path

template, destination = sys.argv[1:]
replacements = {
    "__ACA_NAME__": os.environ["APP_NAME_ENV"],
    "__LOCATION__": os.environ["LOCATION_ENV"],
    "__MANAGED_ENV_ID__": os.environ["ENV_ID_ENV"],
    "__ACR_SERVER__": os.environ["ACR_SERVER_ENV"],
    "__ACR_USERNAME__": os.environ["ACR_USERNAME_ENV"],
    "__ACR_PASSWORD__": os.environ["ACR_PASSWORD_ENV"],
    "__DB_URL__": os.environ["DB_URL_ENV"],
    "__CADDY_IMAGE__": os.environ["CADDY_IMAGE_ENV"],
    "__APP_IMAGE__": os.environ["APP_IMAGE_ENV"],
    "__DOMAIN__": os.environ["DOMAIN_ENV"],
    "__PUBLIC_URL__": os.environ["PUBLIC_URL_ENV"],
}

text = Path(template).read_text()
for key, value in replacements.items():
    text = text.replace(key, value)
Path(destination).write_text(text)
PY

if az containerapp show --name "${APP_NAME}" --resource-group "${RG}" >/dev/null 2>&1; then
  log "Updating existing Container App ${APP_NAME}"
  az containerapp update \
    --name "${APP_NAME}" \
    --resource-group "${RG}" \
    --yaml "${TEMP_YAML}" >/dev/null
else
  log "Creating new Container App ${APP_NAME}"
  az containerapp create \
    --name "${APP_NAME}" \
    --resource-group "${RG}" \
    --yaml "${TEMP_YAML}" >/dev/null
fi

log "Deployment submitted. Current revisions:"
az containerapp revision list --name "${APP_NAME}" --resource-group "${RG}" \
  --query '[].{name:name, traffic:trafficWeight, active:active}' -o table

log "Run database migrations if needed:"
log "  az containerapp exec --name ${APP_NAME} --resource-group ${RG} --command \"reflex db migrate\""
