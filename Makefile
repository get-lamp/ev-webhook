SERVICE := webhook

PROJECT    := workshop-502013
SA_NAME    := workshop
SA_EMAIL   := $(SA_NAME)@$(PROJECT).iam.gserviceaccount.com

.PHONY: lint test init setup docker-up docker-down

lint:
	pipenv run ruff format .
	pipenv run ruff check --fix

test:
	@echo "Starting NATS..."
	docker compose up -d nats
	@for i in $$(seq 1 20); do \
		docker compose exec -T nats nc -z localhost 4222 >/dev/null 2>&1 && break; \
		sleep 0.5; \
	done
	NATS_URL=nats://localhost:4222 pipenv run pytest . -v
	@docker compose down nats

# --- Docker -------------------------------------------------------------------

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

# --- Trello webhooks ----------------------------------------------------------

.PHONY: trello-list trello-delete

trello-list:
	@eval $$(grep -E '^TRELLO_(API_KEY|API_TOKEN)=' .env) && \
	curl -s "https://api.trello.com/1/tokens/$$TRELLO_API_TOKEN/webhooks?key=$$TRELLO_API_KEY" | python3 -m json.tool

trello-delete:
	@if [ -z "$(ID)" ]; then echo "Usage: make trello-delete ID=<webhook_id>"; exit 1; fi
	@eval $$(grep -E '^TRELLO_(API_KEY|API_TOKEN)=' .env) && \
	curl -s -X DELETE "https://api.trello.com/1/webhooks/$(ID)?key=$$TRELLO_API_KEY&token=$$TRELLO_API_TOKEN"

# --- Cloudflare Tunnel --------------------------------------------------------

.PHONY: tunnel-init tunnel-token tunnel-up tunnel-down

tunnel-init:
	@eval $$(grep -E '^CLOUDFLARE_(ACCOUNT_ID|API_TOKEN)=' .env) && \
	cd infra && \
	TF_VAR_cloudflare_api_token=$$CLOUDFLARE_API_TOKEN \
	TF_VAR_cloudflare_account_id=$$CLOUDFLARE_ACCOUNT_ID \
	terraform apply \
		-target=cloudflare_zero_trust_tunnel_cloudflared.webhook \
		-target=data.cloudflare_zero_trust_tunnel_cloudflared_token.webhook \
		-target=cloudflare_zero_trust_tunnel_cloudflared_config.webhook \
		-target=cloudflare_dns_record.webhook_tunnel

tunnel-token:
	@cd infra && echo "CLOUDFLARE_TUNNEL_TOKEN=$$(terraform output -raw cloudflare_tunnel_token)"

tunnel-up:
	docker compose --profile tunnel up -d

tunnel-down:
	docker compose --profile tunnel down

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

del:
	sudo docker images -q --filter=reference='*$(SERVICE)*' | xargs -r sudo docker rmi -f
