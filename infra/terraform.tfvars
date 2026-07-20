project_id     = "workshop-502013"
region         = "southamerica-east1"
service_name   = "webhook"
artifact_repo  = "webhook"

# ── App config ────────────────────────────────────────────────────────────

environment = "production"

# Webhook callback URLs (set to the deployed Cloud Run service URL + path)
drive_webhook_url      = ""
trello_webhook_url     = ""
topic_blueprint_push_url = ""

# Drive
watch_folder_id = ""

# Trello (set in CI/CD or via Terraform Cloud variables)
trello_api_key   = ""
trello_api_token = ""
trello_board_id  = ""

# ── PubSub push subscriptions ─────────────────────────────────────────────
# Set after the downstream workshop service is deployed.

drive_push_endpoint_url  = ""
trello_push_endpoint_url = ""
