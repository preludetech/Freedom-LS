# Hosting FreedomLS: a deployment playbook for South Africa

**Vultr's Johannesburg data centre is the strongest overall choice for FreedomLS**, combining the lowest price among ISO 27001-certified providers with a South African point of presence ($40–48/month for a production-ready VPS). No South African-headquartered hosting provider currently holds ISO 27001 certification—a critical gap that rules out the obvious local options if certification support is non-negotiable. The practical path forward is a single Vultr VPS running Docker Compose, with Ansible for server management and a clear upgrade path to separated services as tenant count grows.

This recommendation balances all five stated priorities: cost-sensitivity, South African latency, ISO 27001 compatibility, automation via Terraform/Ansible, and Docker-native deployment. The rest of this report details the provider landscape, deployment architecture, scaling triggers, and compliance specifics.

---

## The South African hosting gap: no local provider holds ISO 27001

The local VPS market is surprisingly thin when filtered against FreedomLS's requirements. Six South African providers were evaluated, and while several offer competitive pricing and Johannesburg-based infrastructure, **none hold ISO 27001 certification**, and only one (CloudAfrica) exposes a documented API for automation.

**xneelo** (formerly Hetzner South Africa—a separate company from Hetzner Germany) offers the cheapest local option at approximately **R582/month (~$32)** for 4 vCPU, 8 GB RAM, and 100 GB NVMe. It has unlimited bandwidth, hourly billing, and 25 years of operational history. However, xneelo explicitly states it has "not undertaken the SOC 2 or ISO 27001 accreditation." It also has no public API, no Terraform provider, and no managed database service. For a solo developer who needs IaC and compliance documentation, these are significant gaps.

**CloudAfrica** stands out as the most developer-friendly local provider, with an OpenAPI specification published on GitHub and Packer images suggesting an IaC-oriented culture. Its 8-core/8 GB/96 GB SSD plan costs **R731/month (~$41)**. It offers VPC and advanced firewall capabilities—unique among SA providers. But ISO 27001 certification is unconfirmed, and no managed PostgreSQL is available.

**Afrihost** should be avoided for this use case. Its cloud servers use **HDD-based SAN storage**, not SSD, which creates unacceptable database performance for a Django/PostgreSQL workload. At R1,130/month (~$63) for 4 vCPU/8 GB, it is also the most expensive local option for inferior hardware.

| Provider | ~4 vCPU / 8 GB price | Storage | ISO 27001 | API / Terraform | Managed PostgreSQL |
|---|---|---|---|---|---|
| xneelo | R582/mo (~$32) | NVMe SSD | ❌ No | ❌ None | ❌ No |
| CloudAfrica | R731/mo (~$41) | SSD | ❌ Unconfirmed | ✅ OpenAPI | ❌ No |
| Afrihost | R1,130/mo (~$63) | HDD | ❌ No | ❌ None | ❌ No |
| RSAWEB | Quote-based | SSD | ❌ Unconfirmed | ❌ None | ❌ No |
| Axxess | ~R800–1,500 est. | SSD | ❌ No | ❌ None | ❌ No |

Every South African VPS provider supports Docker installation on root-access Linux instances. None offer managed PostgreSQL—you will self-manage the database regardless of which local provider you choose.

---

## Vultr Johannesburg is the clear primary recommendation

Among international providers with South African data centres, **Vultr dominates across every evaluation criterion**. Its Johannesburg region provides local latency. Its compliance portfolio is comprehensive. Its tooling is mature. And its pricing undercuts the hyperscalers by 3–5×.

**Vultr's key specs for FreedomLS:**

- **Regular Performance:** 4 vCPU, 8 GB RAM, 160 GB SSD, 4 TB bandwidth — **$40/month**
- **High Performance (NVMe):** 4 vCPU, 8 GB RAM, 180 GB NVMe, 6 TB bandwidth — **$48/month**
- **Certifications:** ISO/IEC 27001:2022, ISO 27017, ISO 27018, SOC 2+ Type II (with HIPAA), PCI-DSS, CSA STAR Level 1
- **Automation:** Official Terraform provider, full REST API, CLI tools
- **Managed PostgreSQL:** Available (starts ~$15/month for 1 vCPU/1 GB; ~$60/month for 2 vCPU/4 GB—verify Johannesburg region availability)
- **Container support:** Docker, Vultr Kubernetes Engine (VKE) for future orchestration
- **Hourly billing**, no contracts

**Estimated monthly cost for a full FreedomLS production stack on Vultr JNB:**

| Component | Option A (lean) | Option B (comfort) |
|---|---|---|
| App server (4 vCPU, 8 GB) | $40 (SSD) | $48 (NVMe) |
| PostgreSQL | Self-managed on same VPS: $0 | Managed: ~$60 |
| Object storage (media) | ~$5 | ~$5 |
| **Monthly total** | **~$45** | **~$113** |

For Phase 1, Option A is sufficient. Run PostgreSQL in a Docker container on the same VPS.

**Runner-up options and why they fall short:**

**Linode/Akamai** has a Johannesburg distributed compute region, but it is limited-availability (requires contacting sales), only offers dedicated CPU plans (starting ~$72–86/month), and provides no managed services, no pooled transfer, and no block storage in that region. It is more expensive and more constrained than Vultr.

**Hetzner Cloud (Germany/Finland)** offers extraordinary value—a comparable server costs just **~$7–18/month** in EU regions with **20 TB bandwidth** included and full ISO 27001:2022 certification. However, it has no South African region. Latency from Johannesburg to Frankfurt runs **~150–170ms**, which is noticeable for an HTMX-driven interface that relies on server roundtrips for UI updates. Hetzner Cloud is an excellent choice for staging environments, CI runners, or if you later determine latency is tolerable for certain admin-facing workloads.

**AWS Cape Town** (af-south-1), **GCP Johannesburg** (africa-south1), and **Azure South Africa** all provide local presence with comprehensive ISO 27001 certification and managed services. But a comparable stack runs **$200–350/month** when you factor in compute, RDS/Cloud SQL, storage, and egress. That is 4–7× the Vultr cost and not viable for a bootstrapped business at early scale.

---

## Deployment architecture: Docker Compose on a single VPS

For a solo developer deploying a Django 6 application, the right architecture is deliberately simple: Docker Compose with three services behind Cloudflare's free tier for CDN/DDoS protection.

```
[Cloudflare CDN/WAF — free tier]
    → [Vultr JNB VPS]
        → Caddy (reverse proxy + automatic HTTPS)
        → Gunicorn + Django 6 (WSGI application)
        → PostgreSQL 16 (containerized)
        → (later) Redis + background worker
```

**Why Caddy over Nginx:** Caddy handles automatic HTTPS via Let's Encrypt with zero configuration. For a solo developer, eliminating Certbot management and Nginx config complexity is a meaningful operational win.

**PostgreSQL should start containerized.** On a single VPS, the performance difference between containerized and native PostgreSQL is negligible when using a named Docker volume. The operational simplicity of `docker compose up` bringing the entire stack online is worth more than marginal I/O gains. Key rule: always use a named volume, never a bind mount, and run automated `pg_dump` backups via cron with offsite sync (Backblaze B2 at $0.005/GB is ideal for this).

**Static files are simple with HTMX + Alpine.js.** The combined weight of HTMX (~14 KB) and Alpine.js (~43 KB) is trivial. Use WhiteNoise middleware in Django for compression and cache-busting headers, and configure Caddy to serve `/static/` and `/media/` directly from shared Docker volumes, bypassing Gunicorn for static requests.

**Gunicorn configuration for a 4-core VPS:**

```python
workers = 5          # 2 × CPU + 1
worker_class = "gthread"
threads = 2          # 10 concurrent request capacity
timeout = 60
max_requests = 1000  # Memory leak protection
preload_app = True   # Saves memory via copy-on-write
```

**Background tasks: start with Django 6's built-in `django.tasks` framework.** Django 6.0 (released December 2025) includes a native task abstraction via the `@task` decorator and `.enqueue()` method. The `django-tasks` backport package provides a `DatabaseBackend` that uses PostgreSQL as the broker—zero additional infrastructure. Run the worker as a separate container using `python manage.py db_worker`. This handles email notifications, certificate generation, and bulk operations without adding Redis or Celery to the stack. Graduate to Huey or Django-Q2 when you need scheduled/periodic tasks or Redis is already in the stack for caching.

---

## CI/CD: build on GitHub Actions, deploy via SSH pull

The optimal pipeline for a solo developer: test in CI, build a Docker image, push to GitHub Container Registry (GHCR), then SSH into the VPS and pull the new image.

The flow is: push to `main` → run Django tests against a PostgreSQL service container → build a multi-stage Docker image → push to `ghcr.io` → SSH to VPS and run `docker compose pull && docker compose up -d --no-deps web worker`. This keeps build load off the VPS and ensures reproducible deployments.

**For zero-downtime deploys**, install the `docker-rollout` CLI plugin on the VPS—it creates a new container, waits for its healthcheck, then removes the old one. At early scale, the 1–2 seconds of downtime from a simple `docker compose up -d` is perfectly acceptable.

**Security:** Generate a dedicated ed25519 SSH deploy key, store it in GitHub Secrets, and create a `deploy` user on the VPS with limited sudo permissions. Use GitHub's built-in `GITHUB_TOKEN` for GHCR authentication. Manage `.env` files on the VPS directly or via Ansible Vault—never commit secrets to git.

**Infrastructure as Code:** Ansible is the right starting tool, not Terraform. For 1–3 servers, writing Ansible playbooks for security hardening, Docker installation, and backup configuration provides documented, repeatable server setup. Terraform adds value at Phase 2 when you provision multiple VPS instances and need to manage firewall rules and DNS programmatically. Vultr has an official, mature Terraform provider ready when you need it.

---

## Phased scaling: triggers, not timelines

Scaling should be driven by monitoring data, not calendar dates. Each phase has specific triggers.

**Phase 1 — Single VPS, everything containerized ($40–48/month)**
Runs Django + PostgreSQL + Caddy in Docker Compose on one Vultr High Performance instance. Handles **50–200 concurrent users**, comfortably supporting up to ~1,000 registered students. Add Uptime Kuma (self-hosted, free) for availability monitoring and Sentry's free tier for error tracking. This phase covers the first 6–12 months for most bootstrapped LMS deployments.

**Move to Phase 2 when:** CPU consistently exceeds 70% during peak hours, or PostgreSQL data grows past 50 GB and backup/restore becomes unwieldy, or ISO 27001 auditors require automated point-in-time recovery for the database.

**Phase 2 — Separate database ($60–108/month)**
Move PostgreSQL to Vultr Managed Database (~$60/month for 2 vCPU/4 GB) or a separate dedicated VPS ($20–24/month). Add Redis for Django session storage and caching. The app VPS now handles only Django, Caddy, Redis, and the background worker. This supports **500+ concurrent users** and up to ~5,000–10,000 registered students.

**Move to Phase 3 when:** a single app server cannot handle peak load (exam periods, enrollment rushes), or institutional SLAs require zero-downtime deployments.

**Phase 3 — Horizontal scaling ($150–250/month)**
Add a second app VPS behind a load balancer. Move static/media files to S3-compatible object storage (Vultr Object Storage or Cloudflare R2). Session storage must be in Redis (not file-based). Add Prometheus + Grafana for infrastructure metrics. This handles **1,000+ concurrent users** across multiple tenants.

**Phase 4 — Container orchestration (when managing 3+ servers manually becomes error-prone)**
Docker Swarm is the natural first step—it uses nearly identical Compose file syntax and adds service replication, rolling updates, and self-healing. Only move to Kubernetes (via k3s or Vultr Kubernetes Engine) if you need CRDs, operators, GitOps with ArgoCD, or are running complex multi-service architectures. This is unlikely to be needed before **5,000+ concurrent users**.

---

## ISO 27001 compliance: what Vultr provides vs. what you must build

ISO 27001:2022 operates on a shared responsibility model. Choosing an ISO 27001-certified provider like Vultr is the single highest-leverage decision, but it covers only the "security OF the cloud." You own "security IN the cloud."

**What Vultr's ISO 27001:2022 certification covers:**

- Physical data centre security (biometrics, CCTV, 24/7 guards)
- Hardware maintenance and disposal
- Network backbone infrastructure
- Hypervisor/virtualization layer security
- Power redundancy and environmental controls
- Vultr's own operational procedures and staff training

**What you must implement and document yourself:**

- **OS hardening:** SSH key-only access, fail2ban, UFW firewall rules, unattended security updates, disabled root login
- **Encryption:** TLS 1.2+ on all traffic (Caddy handles this), encrypted backups via GPG before offsite sync, PostgreSQL SSL connections
- **Access control:** MFA on all admin access, RBAC within Django, documented access review process, least-privilege principle
- **Logging and monitoring:** Centralized logging (Loki or similar), failed login alerting, audit trail of deployments via Git history and CI/CD logs
- **Backup and disaster recovery:** Documented schedule, tested restores (quarterly), defined RTO/RPO, offsite backup storage
- **Incident response:** Written plan with escalation procedures, breach notification templates (POPIA requires prompt notification to the Information Regulator)
- **Change management:** Git-based workflow with PR reviews serves as documented change management
- **Vulnerability management:** Trivy for container image scanning, Dependabot for Python dependencies, periodic OWASP ZAP scans
- **ISMS documentation:** Information Security Policy, Risk Assessment, Statement of Applicability, Supplier Policy covering Vultr

**Why IaC is actually better than CapRover/Coolify for ISO 27001:** CapRover insists on running as root (violates least-privilege), has no RBAC, provides no enterprise audit trail, and its backup/restore process has been reported as non-functional. Coolify Cloud requires granting SSH access to the Coolify team. Neither holds any security certification, and neither has a formal vulnerability disclosure programme. An Ansible + Docker Compose approach, by contrast, provides version-controlled, auditable infrastructure where every configuration change is tracked in Git—exactly the kind of evidence ISO 27001 auditors want to see.

**POPIA and data residency:** South Africa's Protection of Personal Information Act does not impose a blanket data residency requirement. Cross-border transfers are permitted if the recipient jurisdiction provides adequate protection (EU countries qualify), or if binding agreements are in place. Hosting on Vultr Johannesburg keeps data in South Africa, which simplifies compliance argumentation and aligns with the June 2024 National Policy on Data and Cloud. This is a practical advantage, not a legal mandate—unless FreedomLS serves financial institutions or government entities, which may have sector-specific local hosting requirements.

**Estimated ISO 27001 certification costs for a small team:**

| Item | Estimated cost |
|---|---|
| Compliance automation platform (Vanta, Drata, or Sprinto) | $5,000–15,000/year |
| Initial certification audit | $10,000–25,000 |
| Annual surveillance audits | $5,000–10,000/year |
| Hosting infrastructure | $500–1,400/year |
| **First-year total** | **~$20,000–50,000** |

---

## Conclusion

The South African hosting market has a structural gap: local providers offer good pricing and Johannesburg latency but lack the compliance certifications, APIs, and managed services that a B2B SaaS product needs. Vultr bridges this gap uniquely—it is the only provider combining a Johannesburg data centre, ISO 27001:2022 certification, mature Terraform support, managed PostgreSQL, and pricing under $50/month for a production-capable VPS.

The deployment strategy should match the team's size, not the product's ambitions. A single Vultr VPS running Docker Compose (Caddy + Gunicorn + PostgreSQL) handles the first thousand users. Django 6's built-in task framework eliminates the need for Celery and Redis at launch. Ansible playbooks for server hardening create the documented, reproducible infrastructure that ISO 27001 auditors expect—and that CapRover and Coolify cannot provide.

Three decisions matter most right now: use Vultr Johannesburg for hosting, use Ansible + Docker Compose instead of a self-hosted PaaS, and begin ISO 27001 documentation from day one even if certification is months away. Everything else—managed databases, horizontal scaling, Kubernetes—follows naturally from monitoring data, not from architecture anxiety.
