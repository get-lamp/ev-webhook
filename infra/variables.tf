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

variable "push_endpoint_url" {
  description = "Cloud Run URL that PubSub push subscriptions deliver messages to"
  type        = string
  default     = ""
}
