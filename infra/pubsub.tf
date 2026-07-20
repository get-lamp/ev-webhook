# Look up the workshop service account for PubSub OIDC push authentication.
data "google_service_account" "workshop" {
  account_id = var.workshop_service_account_id
}

# Push subscriptions — deliver messages to downstream Cloud Run endpoints.

resource "google_pubsub_subscription" "drive_updated_push" {
  count = var.drive_push_endpoint_url != "" ? 1 : 0

  name  = "drive-updated-push"
  topic = google_pubsub_topic.drive_updated.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = var.drive_push_endpoint_url

    oidc_token {
      service_account_email = data.google_service_account.workshop.email
    }
  }
}

resource "google_pubsub_subscription" "trello_board_updated_push" {
  count = var.trello_push_endpoint_url != "" ? 1 : 0

  name  = "trello-board-updated-push"
  topic = google_pubsub_topic.trello_board_updated.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = var.trello_push_endpoint_url

    oidc_token {
      service_account_email = data.google_service_account.workshop.email
    }
  }
}
