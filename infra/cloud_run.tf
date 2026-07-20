# Artifact Registry repository for container images
resource "google_artifact_registry_repository" "repo" {
  depends_on    = [google_project_service.apis["artifactregistry.googleapis.com"]]
  location      = var.region
  repository_id = var.artifact_repo
  format        = "DOCKER"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "webhook" {
  depends_on = [google_project_service.apis["run.googleapis.com"]]
  name       = var.service_name
  location   = var.region

  template {
    service_account = var.service_account_email != "" ? var.service_account_email : null

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/${var.service_name}:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }

      # ── App config ─────────────────────────────────────────────────
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      # Webhook callback URLs (this service)
      env {
        name  = "DRIVE_WEBHOOK_URL"
        value = var.drive_webhook_url
      }
      env {
        name  = "TRELLO_WEBHOOK_URL"
        value = var.trello_webhook_url
      }
      env {
        name  = "TOPIC_BLUEPRINT_PUSH_URL"
        value = var.topic_blueprint_push_url
      }

      # Drive
      env {
        name  = "WATCH_FOLDER_ID"
        value = var.watch_folder_id
      }

      # Trello
      env {
        name  = "TRELLO_API_KEY"
        value = var.trello_api_key
      }
      env {
        name  = "TRELLO_API_TOKEN"
        value = var.trello_api_token
      }
      env {
        name  = "TRELLO_BOARD_ID"
        value = var.trello_board_id
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    timeout = "60s"
  }
}
