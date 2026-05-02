We need to deploy to

Staging and prod
Automate as much as possible

Phase 1 — Single VPS, everything containerized ($40–48/month)

Runs Django + PostgreSQL + Caddy in Docker Compose on one Vultr High Performance instance. Handles 50–200 concurrent users, comfortably supporting up to ~1,000 registered students. Add Uptime Kuma (self-hosted, free) for availability monitoring and Sentry's free tier for error tracking. This phase covers the first 6–12 months for most bootstrapped LMS deployments.
