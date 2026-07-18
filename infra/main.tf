terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "pubsub.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
    "drive.googleapis.com",
    "firestore.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.key
  disable_on_destroy = false
}

# --- PubSub topics -----------------------------------------------------------

resource "google_pubsub_topic" "drive_updated" {
  name = "drive-updated"
}

resource "google_pubsub_topic" "trello_board_updated" {
  name = "trello-board-updated"
}