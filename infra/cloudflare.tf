# ── Tunnel ──────────────────────────────────────────────────────────────────

resource "cloudflare_zero_trust_tunnel_cloudflared" "webhook" {
  account_id = var.cloudflare_account_id
  name       = var.service_name
  config_src = "cloudflare"
}

# ── Tunnel token (data source — tokens aren't a managed resource in v5) ─────

data "cloudflare_zero_trust_tunnel_cloudflared_token" "webhook" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.webhook.id
}

# ── Ingress rules ───────────────────────────────────────────────────────────

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "webhook" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.webhook.id
  source     = "cloudflare"

  config = {
    ingress = [
      {
        hostname = var.cloudflare_tunnel_domain
        service  = "http://webhook:8080"
      },
      {
        service = "http_status:404"
      }
    ]
  }
}

# ── DNS record (CNAME to tunnel) ────────────────────────────────────────────

data "cloudflare_zone" "main" {
  filter = {
    name = var.cloudflare_zone_name
  }
}

resource "cloudflare_dns_record" "webhook_tunnel" {
  zone_id = data.cloudflare_zone.main.zone_id
  name    = var.cloudflare_tunnel_domain
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.webhook.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1
}
