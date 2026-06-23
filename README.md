# Rhiz — Speak Together

Rhiz is a structured-deliberation platform built with [Reflex](https://reflex.dev).
People post **concepts**, respond with **supports**, **detracts**, and
**points of order**, **up/down-vote** them, and discover related ideas through
trending lists and similarity search. Concepts can also be **distributed as
debates** — public, shareable pages (link + QR) that invite a wider audience
into a focused discussion and bridge them into the broader debate on the site.

## Features

- **Concepts & deliberation** — submit a concept (draft → published), respond
  with support / detract / point-of-order comments, and up/down-vote. Threaded
  comments per concept.
- **Discovery** — Trending (by upvotes and by support), and **Compare**, which
  surfaces similar concepts using pgvector embedding similarity.
- **Rich text** — concepts are authored in a TipTap editor and rendered
  read-only via sanitized Markdown.
- **Performance** — list pages use infinite scroll with server-side windowing,
  and concept tallies are computed in batched set-based queries (important
  because the app talks to a remote database).
- **Debates (distribution layer)**
  - Turn **any** concept into a debate from the concept's ⋯ menu (it keeps
    behaving normally elsewhere).
  - `/debate/<slug>` is **publicly readable** (concept + comments, no account);
    commenting, comparing, or proposing an alternative requires an account.
  - A "how this works" overlay onboards first-time visitors (auto-shown once).
  - **Your Debates** (`/your_debates`) — a user's own debates, with share
    link + QR and open/close/delete.
  - **All Debates** (`/debates`) — admin-only moderation of every debate, incl.
    delete on behalf of others.
  - **Email-verification signup** — when someone signs up via a debate link,
    their account is auto-enabled after they verify their email (normal signups
    still require manual approval).
- **Roles** — regular / moderator / admin. Who may create debates is controlled
  by the `DEBATE_CREATE_MIN_ROLE` setting (default: admin).

## Tech stack

- **Reflex** (Python full-stack; React/Vite frontend, FastAPI/granian backend)
- **PostgreSQL + pgvector** via **SQLModel**
- **fastembed** (`sentence-transformers/all-MiniLM-L6-v2`) for concept embeddings
- **Azure**: Static Web Apps (frontend) + Container Apps (backend) + Azure
  Communication Services (transactional email)

## Local setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

### Local Postgres with pgvector

A Postgres 16 + `pgvector` image lives at `docker/db/Dockerfile`. Start it with
Compose from the repo root:

```bash
docker compose up db
```

It exposes Postgres on `localhost:5432` with database `reckon` and credentials
`postgres` / `password`. Compose-internal services use
`postgresql://postgres:password@db:5432/reckon`; to connect from outside
Compose, set `DB_URL` accordingly.

### Run the app

```bash
set -a && source .env && set +a   # loads DB_URL, PUBLIC_BASE_URL, etc.
reflex run
```

Frontend serves on `:3000` (or `:3001`), backend on `:8000` — confirm from the
startup banner.

## Environment variables

| Variable | Purpose |
|---|---|
| `DB_URL` | PostgreSQL connection string (defaults to the local Compose DB in `rxconfig.py`). |
| `API_URL` | Public backend URL the frontend connects to. |
| `PUBLIC_BASE_URL` | Public site origin used to build **debate share links / QR codes and the email-verification link** (e.g. `https://www.rhiz.ai`). Defaults to `http://localhost:3000` for dev — **must be set in production**. |
| `RUN_MIGRATIONS_ON_START` | Backend container entrypoint runs `reflex db migrate` on start when `1` (default). Set to `0` in production — migrations are applied manually (see below). |
| `TOOLBAR_ENABLED` | Toggles the editor toolbar. |
| `POSTHOG_PROJECT_API_KEY` | Optional analytics; unset disables the client script. |

## Database & migrations

Schema is defined by the SQLModel models in `rhiz/state/base.py`. Migrations live
in `alembic/` (gitignored — they're force-added when needed) and are normally
applied with:

```bash
reflex db migrate
```

> **Note:** the production database's alembic history is currently out of sync,
> so schema changes are applied directly (idempotent `CREATE … IF NOT EXISTS` /
> `ALTER TABLE … ADD COLUMN IF NOT EXISTS`) until the history is reconciled. The
> migration files are still authored for the record. Because of this, the
> production backend container runs with `RUN_MIGRATIONS_ON_START=0` so it does
> **not** run `reflex db migrate` on start, and the `alembic/` dir + `alembic.ini`
> are kept out of the backend image (`.dockerignore`) — shipping them makes
> `reflex run`'s schema check import the local `alembic/` dir and crash.

## Deployment (Azure, via GitHub Actions)

Production runs as a **statically-exported Reflex frontend** on Azure Static Web
Apps talking to a **containerized backend** on Azure Container Apps. Both are
deployed by GitHub Actions workflows.

- **Backend → Azure Container Apps** — `.github/workflows/deploy-backend.yml`.
  Runs automatically on push to `master` that touches app code
  (`Dockerfile`, `requirements.txt`, `rxconfig.py`, `rhiz/**`, `scripts/**`), or
  manually via *Run workflow*. It builds the Docker image, pushes it to ACR, and
  updates the Container App, setting `API_URL`, `PUBLIC_BASE_URL`, `DB_URL`, and
  `RUN_MIGRATIONS_ON_START=0`. The container runs the **backend only**
  (`reflex run --env prod --backend-only` → granian on `:8000`); the deploy
  fails loudly if the new revision does not reach a healthy `Running` state.
- **Frontend → Azure Static Web Apps** — `.github/workflows/static-app.yml`
  (manual *Run workflow*). It runs `reflex export --frontend-only` against the
  backend `API_URL` and publishes `swa-build/` to Static Web Apps.
  `deploy/staticwebapp.config.json` adds a `navigationFallback` to the Reflex
  React-Router SPA shell (`/__spa-fallback.html`) so direct hits / refreshes /
  **QR codes** on dynamic routes (`/debate/<slug>`, `/concept/<id>`, …) resolve
  client-side instead of 404-ing.

Typical release: push to `master` (backend deploys automatically), then run the
**Deploy Static Web App** workflow to publish the frontend.

Required repository **secrets**:

- Backend: `AZURE_CREDENTIALS`, `ACR_NAME`, `ACR_LOGIN_SERVER`, `PUBLIC_API_URL`,
  `DB_URL`, `CONTAINERAPP_NAME`, `RESOURCE_GROUP`
- Frontend: `AZURE_STATIC_WEB_APPS_API_TOKEN`

## Legacy VM setup (manual, archival)

Earlier deployments used a single Azure VM. Retained for reference:

```bash
# create resource group + supporting resources
./scripts/azure-create-vm.sh
# db templates: ./scripts/parameters.json, ./scripts/template.json
# create db `reckon`, enable pgvector:
#   https://learn.microsoft.com/azure/postgresql/flexible-server/how-to-use-pgvector

az ssh vm --resource-group reckon-rg --vm-name reckon --subscription <SUBSCRIPTION_ID>

# on the VM:
type -p curl >/dev/null || (sudo apt update && sudo apt install curl -y)
# install gh (see https://cli.github.com), then:
gh auth login
gh repo clone journey42/reckon
sudo apt install docker.io docker-compose
sudo DOMAIN=reckon-dev.eastus.cloudapp.azure.com docker-compose build
cp ~/reckon/scripts/azure/reckon.service /etc/systemd/system/reckon.service
sudo systemctl daemon-reload && sudo systemctl enable reckon && sudo systemctl start reckon
sudo systemctl status reckon
```
