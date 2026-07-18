output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.webhook.uri
}

output "artifact_repo" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}"
}
