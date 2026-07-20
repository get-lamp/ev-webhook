PROJECT    := workshop-502013
SA_NAME    := workshop
SA_EMAIL   := $(SA_NAME)@$(PROJECT).iam.gserviceaccount.com

.PHONY: lint test init setup docker-up docker-down

lint:
	pipenv run ruff format .
	pipenv run ruff check --fix

test:
	@gcloud beta emulators pubsub start --project=test-project --quiet &>/dev/null & \
	PID=$$!; \
	trap 'kill $$PID 2>/dev/null; wait $$PID 2>/dev/null' EXIT; \
	for i in $$(seq 1 20); do \
		curl -s http://localhost:8085 >/dev/null 2>&1 && break; \
		sleep 0.5; \
	done; \
	PUBSUB_EMULATOR_HOST=localhost:8085 pipenv run pytest . -v

# --- Docker -------------------------------------------------------------------

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

# --- GCP service account (run once) ------------------------------------------

init:
	gcloud config set project $(PROJECT)
	gcloud iam service-accounts create $(SA_NAME) \
		--display-name="Workshop Service Account" \
		--project=$(PROJECT)
	@echo "Waiting for IAM propagation..."
	@sleep 10

login:
	gcloud auth application-default login \
		--client-id-file=$(HOME)/.config/gcloud/workshop-oauth-client.json \
		--scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive" \
		--project=$(PROJECT)
	gcloud config set project $(PROJECT)

# --- Daily dev setup (idempotent) --------------------------------------------

setup:
	@test -f $(HOME)/.config/gcloud/application_default_credentials.json \
		|| { echo "ERROR: ADC not found — run 'make login' first"; exit 1; }
