# Allow unauthenticated access to the Cloud Run service
data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  location = google_cloud_run_v2_service.webhook.location
  project  = google_cloud_run_v2_service.webhook.project
  service  = google_cloud_run_v2_service.webhook.name

  policy_data = data.google_iam_policy.noauth.policy_data
}
