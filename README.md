# Webhook

FastAPI service that receives Drive push notifications and Trello webhooks, then publishes events to Pub/Sub topics for downstream processing.

## Prerequisites

- Python 3.12
- [pipenv](https://pipenv.pypa.io/)
- Docker (for deploys)
- `gcloud` CLI with Pub/Sub emulator component (for tests)
- Authenticated GCP credentials (`gcloud auth application-default login`)

## Install

```bash
pipenv install --dev
```

Copy the `.env` file and fill in the required values:

```bash
cp .env.example .env  # or create .env manually
```

Required variables: `WEBHOOK_URL`, `WATCH_FOLDER_ID`, `TRELLO_API_KEY`, `TRELLO_API_SECRET`, `TRELLO_BOARD_ID`. Optional: `GCP_PROJECT_ID` (set to publish to Pub/Sub).

## Run locally

```bash
pipenv run uvicorn webhook.main:app --reload --port 8080
```

## Tests

```bash
make test
```

Starts the Pub/Sub emulator, runs the test suite, and cleans up. Requires `gcloud beta emulators pubsub` to be installed.

```bash
gcloud components install pubsub-emulator   # one-time
```

## Lint

```bash
make lint
```

Runs ruff format and check with auto-fix.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/inspect_drive.py` | Inspect the watched folder — shows metadata and lists files |
| `scripts/list_channels.py` | Show the active Drive watch channel stored in Firestore |

Run with:

```bash
pipenv run python scripts/inspect_drive.py
pipenv run python scripts/list_channels.py
```

## Architecture

```
Drive/Trello  ──HTTP──▶  FastAPI (Cloud Run)  ──publish──▶  Pub/Sub topics
                                                              │
                                              ┌────────────────┘
                                              ▼
                                        downstream push subscribers
```

- `POST /drive/updated` — Drive push notifications. Lists changes via the Drive API, publishes events to the `drive-updated` Pub/Sub topic.
- `POST /trello/updated` — Trello webhooks. Publishes the raw payload to the `trello-board-updated` Pub/Sub topic.
- `GET /health` — Liveness check.

Pub/Sub message schemas are in `webhook/schemas.py`.

## Infrastructure

Infrastructure is defined in `infra/` (Terraform):

- Cloud Run service (0–10 instances, 256 MiB, 60s timeout)
- Artifact Registry (Docker repo)
- Pub/Sub topics (`drive-updated`, `trello-board-updated`) with push subscriptions
- Firestore for watch channel state

### First-time setup

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # edit with your values
terraform apply
```

### Deploy

```bash
./deploy.sh
```

Builds the Docker image (`linux/amd64`), pushes to Artifact Registry, and deploys to Cloud Run. Prints the service URL on completion.
