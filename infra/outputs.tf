output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.webhook.uri
}

output "artifact_repo" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}"
}

# ── Cloudflare Tunnel ───────────────────────────────────────────────────────

output "cloudflare_tunnel_id" {
  description = "Cloudflare Tunnel ID"
  value       = cloudflare_zero_trust_tunnel_cloudflared.webhook.id
}

output "cloudflare_tunnel_token" {
  description = "Token for cloudflared daemon to authenticate the tunnel"
  value       = data.cloudflare_zero_trust_tunnel_cloudflared_token.webhook.token
  sensitive   = true
}

output "cloudflare_tunnel_domain" {
  description = "Public URL for the webhook service via Cloudflare Tunnel"
  value       = "https://${var.cloudflare_tunnel_domain}"
}
