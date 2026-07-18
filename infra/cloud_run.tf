# Artifact Registry repository for container images
resource "google_artifact_registry_repository" "repo" {
  depends_on  = [google_project_service.apis["artifactregistry.googleapis.com"]]
  location    = var.region
  repository_id = var.artifact_repo
  format      = "DOCKER"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "webhook" {
  depends_on = [google_project_service.apis["run.googleapis.com"]]
  name       = var.service_name
  location   = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/${var.service_name}:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    timeout = "60s"
  }
}
