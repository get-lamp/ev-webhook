variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run and Artifact Registry"
  type        = string
  default     = "southamerica-east1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "webhook"
}

variable "artifact_repo" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "webhook"
}

variable "service_account_email" {
  description = "Service account for Cloud Run (leave empty to use default compute SA)"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Deployment environment (local / production)"
  type        = string
  default     = "production"
}

# ── Webhook callback URLs (this service's own endpoints) ──────────────────

variable "drive_webhook_url" {
  description = "Full URL that Drive / localwatch POSTs to (this service's /drive/updated endpoint)"
  type        = string
}

variable "trello_webhook_url" {
  description = "Full URL that Trello POSTs to (this service's /trello/updated endpoint)"
  type        = string
  default     = ""
}

variable "topic_blueprint_push_url" {
  description = "Full URL of the workshop service endpoint that receives blueprint snapshots"
  type        = string
  default     = ""
}

# ── Drive ─────────────────────────────────────────────────────────────────

variable "watch_folder_id" {
  description = "Google Drive folder ID to watch for file changes"
  type        = string
}

# ── Trello ────────────────────────────────────────────────────────────────

variable "trello_api_key" {
  description = "Trello API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "trello_api_token" {
  description = "Trello API token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "trello_board_id" {
  description = "Trello board ID to monitor"
  type        = string
  default     = ""
}

# ── PubSub push subscription endpoints (where PubSub delivers messages) ───

variable "drive_push_endpoint_url" {
  description = "Workshop service URL that receives drive-updated PubSub messages"
  type        = string
  default     = ""
}

variable "trello_push_endpoint_url" {
  description = "Workshop service URL that receives trello-board-updated PubSub messages"
  type        = string
  default     = ""
}

variable "workshop_service_account_id" {
  description = "Account ID of the workshop service account (for PubSub OIDC push auth)"
  type        = string
  default     = "workshop"
}
