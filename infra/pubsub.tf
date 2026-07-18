# Push subscriptions — deliver messages to downstream Cloud Run endpoints.
# Created only after the downstream service is deployed and push_endpoint_url is known.
# Set push_endpoint_url in terraform.tfvars and re-run `terraform apply`.

resource "google_pubsub_subscription" "drive_updated_push" {
  count = var.push_endpoint_url != "" ? 1 : 0

  name  = "drive-updated-push"
  topic = google_pubsub_topic.drive_updated.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = var.push_endpoint_url

    oidc_token {
      service_account_email = google_service_account.workshop.email
    }
  }
}

resource "google_pubsub_subscription" "trello_board_updated_push" {
  count = var.push_endpoint_url != "" ? 1 : 0

  name  = "trello-board-updated-push"
  topic = google_pubsub_topic.trello_board_updated.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = var.push_endpoint_url

    oidc_token {
      service_account_email = google_service_account.workshop.email
    }
  }
}
