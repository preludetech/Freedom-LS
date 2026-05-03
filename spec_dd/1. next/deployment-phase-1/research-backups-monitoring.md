# Operational hygiene for Phase 1: backups, monitoring, alerting

**Scope.** Solo dev, FreedomLS (Django 6 + PostgreSQL 17 + Caddy + Docker Compose), single Vultr Johannesburg VPS, staging and prod on the same box, ISO 27001 evidence requirements, no production deployment exists yet.

**TL;DR — install on day one.**

1. Nightly `pg_dump --format=custom`, age-encrypted, pushed to **Backblaze B2** with object-lock + lifecycle. Retention: 14 daily / 8 weekly / 12 monthly / 7 yearly.
2. Quarterly restore drill into the staging stack on the same box. Save a checksum + screenshot per drill.
3. **Uptime Kuma** on a **Hetzner CX22 in Falkenstein (~EUR 4–5/mo)** monitoring the Vultr box from outside. Cloudflare Tunnel + Cloudflare Access (free) in front.
4. **Sentry SaaS free tier** with `sentry-sdk[django]`. `traces_sample_rate=0.1`, `profiles_sample_rate=0.0`, `send_default_pii=False`.
5. Alerts: email + a single Telegram channel. No pager. No SMS.
6. Vultr's built-in graphs + Uptime Kuma synthetic checks. **No** Prometheus/Grafana/Loki yet.
7. Docker `json-file` driver with `max-size: 20m, max-file: 5`. `unattended-upgrades`, `fail2ban`, SSH-key-only, login email via `pam_exec`.

**Defer:** PITR, Loki/Grafana, Netdata Cloud, Better Stack, separate metrics box.

---

## 1. PostgreSQL backups

**Schedule (grandfather-father-son):**

| Tier   | Frequency        | Retention | Bucket            |
|--------|------------------|-----------|-------------------|
| Daily  | 02:30 SAST       | 14 days   | `fls-daily`       |
| Weekly | Sunday 02:30     | 8 weeks   | `fls-weekly`      |
| Monthly| 1st of month    | 12 months | `fls-monthly`     |
| Yearly | 1 Jan            | 7 years   | `fls-yearly`      |

7-year tail aligns with POPIA/SARS defaults. For ~1,000 students the dump fits in well under 1 GB compressed; full nightly logical backups are cheap.

**Dump command.** Custom format only — supports parallel restore and selective restore:
```bash
docker compose exec -T postgres \
  pg_dump -U "$PGUSER" -d "$PGDATABASE" -Fc -Z 9 --no-owner --no-acl \
  > "/var/backups/fls/${DATE}.dump"
```
Don't use plain SQL (`-Fp`). Don't double-compress with gzip — `-Z 9` is enough.

**Encryption.** Use **age** (https://github.com/FiloSottile/age), not GPG, unless audit demands OpenPGP. Generate keypair offline; only the public key goes on the server; private key in 1Password + paper backup. `age -r "$AGE_PUBLIC_KEY" -o "${DATE}.dump.age" "${DATE}.dump"`. Test decryption on a different machine before going live — the most common backup failure is "the only key was on the box that died."

**Where to send: Backblaze B2.**

| Provider | Storage $/GB-mo | Egress $/GB | Notes |
|----------|-----------------|-------------|-------|
| **B2**   | $0.006          | $0.01 (3× free) | Cheapest; Object Lock for ISO evidence |
| **R2**   | $0.015          | $0 | Free egress is great but 2.5× storage; better for media |
| **Vultr Object Storage** | ~$5 flat (250 GB) | $0.01 | Same vendor — bad idea for backups |

Use `rclone` to push. Configure B2 bucket lifecycle server-side (don't rely on `rclone delete`). Use scoped application keys, never the master. Enable Object Lock (compliance mode) for monthly/yearly.

**Cron script `/opt/fls/bin/backup.sh`:** dump → age encrypt → rclone copy to tier-appropriate bucket → prune local cache (`-mtime +3`) → ping `https://healthchecks.io` (free 20 checks). On failure, stderr to ops email.

---

## 2. Restore drills

**Cadence:** monthly automated smoke restore, quarterly full drill with human checklist, annual DR scenario (rebuild from scratch on a fresh VPS).

**Yes — staging on the same box doubles as the restore target.** This is the recommended pattern: staging is *always* the latest restored prod backup, refreshed weekly via cron:

1. Pull latest dump from B2.
2. Decrypt with private key (kept on staging side, separate from prod).
3. Drop staging DB, recreate, `pg_restore -j 4`.
4. Run `scrub_pii.sql` (anonymise emails, null phones, fake names).
5. Log `accounts_user` and `student_progress` row counts to audit log.

**Caveat:** the private decryption key must NOT live on prod. In Phase 1 with both envs on one box, use soft separation (separate Linux user, key file readable only by staging user). Move to a real separate ops host when you can.

**ISO 27001 evidence (control A.8.13).** Per drill, keep a 5-line markdown file in a private `restore-drills/` git repo: date/time, backup filename + SHA-256, `pg_restore` exit code + duration, post-restore sanity SQL output, screenshot, anomalies, sign-off. Auditors prefer consistency over volume.

---

## 3. Point-in-time recovery (PITR)

**Phase 1 verdict: not worth it.** Daily logical backup gives RPO ~24h, which is correct for a bootstrapped LMS with bursty low-RPS writes. WAL archiving doubles operational complexity and silent WAL-archive failures are a classic foot-gun.

**Graduate when any of:** DB > 10 GB and `pg_dump` > 30 min; tenant contract demands RPO ≤ 1h; revenue-bearing data (payments, exam grading); multi-tenant where one tenant's mistake should not require restoring everyone.

**Graduation paths:**
- **Path A (recommended): Vultr Managed PostgreSQL** at ~$60/mo for 2vCPU/4GB. Backups + 7-day PITR + replication included. Best ergonomics-per-rand.
- **Path B: pgBackRest or WAL-G self-managed** to B2/R2. pgBackRest is best-in-class; WAL-G is simpler. ~1 day to set up, ~1 hr/mo to babysit.

Document Path A in the Phase 2 runbook now so it doesn't get postponed.

---

## 4. Application and file backups

| Asset | Where it lives | Backup strategy |
|-------|----------------|-----------------|
| App code | GitHub | Git remotes (GitHub + Codeberg mirror) |
| Ansible playbooks | Private GitHub repo | Same |
| `.env` files | On the server | **`sops` + age**, committed to git encrypted |
| Caddyfile, compose, systemd, cron | Ansible repo | Already in git |
| User-uploaded media (R2) | R2 bucket | R2 versioning + weekly `rclone sync r2:fls-media b2:fls-media-mirror` |
| Caddy TLS certs | Disk | **Don't back up** — Caddy re-issues |
| age/TLS private keys | 1Password + paper | Out-of-band only |
| SSH host keys | Server | Capture in Ansible (sops-encrypted) so rebuilds keep identity |

**`.env` story:** sops (https://github.com/getsops/sops) with age key, encrypted in-place, committed. Single source of truth, decryptable on the box via Ansible.

**Not backed up:** `/var/lib/docker`, Caddy `data/` (ACME), OS package state, container logs.

If your Ansible repo + latest DB dump aren't enough to rebuild prod from a fresh Ubuntu image, it has gaps. Test this in the annual DR drill.

---

## 5. Uptime Kuma hosting

**Constraint:** Kuma on the box it monitors gives false negatives during the exact incident you care about. Must live elsewhere.

| Option | Cost | Verdict |
|--------|------|---------|
| **Hetzner CX22 / CAX11 (Falkenstein)** | EUR 3.79–4.51/mo | **Recommended.** ISO 27001 certified provider, different continent from Vultr JNB (a feature for a watchdog) |
| Oracle Cloud Always Free | $0 | **Avoid for ops infra** — account-reclamation horror stories make it unfit for the one thing that has to be up when nothing else is |
| Vultr second instance | $6/mo | Vendor concentration; defeats the watchdog point |
| Fly.io shared-cpu-1x | ~$2/mo | Volume backups awkward; works but Hetzner is more predictable |

**Expose securely with two layers:**
1. **Cloudflare Tunnel** (`cloudflared`) — no inbound port on Hetzner.
2. **Cloudflare Access** (free, ≤50 users) — gates the tunnel with email OTP or GitHub SSO.

Alternative: **Tailscale** + Kuma bound to tailnet IP only. Simpler, but only works from devices with Tailscale.

**What Kuma should monitor day one:** HTTPS GET on `app.freedomls.example/healthz/` (Django view that touches DB) + same on staging; TCP/22; cert expiry; push monitor for backup cron; DNS apex. 60s for HTTP, 5m for push (30h grace).

---

## 6. Sentry free tier

**What's covered (2026):** 5,000 errors/mo, 10,000 perf units/mo, 1 GB attachments, 1 user, 30-day retention, no SSO. Plenty for Phase 1 *if* you don't generate noise. Next step is Team plan ($26/mo). **Self-hosted Sentry is strongly not recommended** at this scale (Kafka + ClickHouse + Redis + multiple Postgres).

**Django config:**
```python
sentry_sdk.init(
    dsn=env("SENTRY_DSN"),
    integrations=[
        DjangoIntegration(transaction_style="url", middleware_spans=True, signals_spans=False),
        LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
    ],
    environment=env("DJANGO_ENV"),
    release=env("GIT_SHA"),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.0,
    send_default_pii=False,
    max_breadcrumbs=50,
    before_send=scrub_pii,
)
```

`send_default_pii=False` is POPIA-friendly. Add a `before_send` scrubber for SA-specific PII (ID numbers, phone numbers). `release=$GIT_SHA` from the Docker build for regression bisection.

**Source maps:** server-rendered Django + HTMX, no JS bundle, skip until a real frontend bundle exists.

**Performance:** 10% trace sampling samples hundreds of transactions/day for a low-traffic LMS, plenty to catch N+1 regressions. Profiling off until there's a perf problem. Drop `/healthz/` and `/favicon.ico` via `traces_sampler`.

---

## 7. Alerting routes

**Pager-fatigue principle:** one (1) channel that vibrates the phone. Everything else is email.

| Source | Severity | Channel |
|--------|----------|---------|
| Kuma DOWN (2 fails) | High | **Telegram bot (vibrate)** |
| Kuma RECOVERED | Info | Telegram (silent) |
| Kuma cert <14d | Low | Email |
| Sentry new issue | Med | Telegram (silent) + email |
| Sentry spike >50/hr | High | Telegram (vibrate) |
| Backup missing >30h | High | Email + Telegram |
| fail2ban ban | Low | Email **digest daily** |
| SSH login | Med | Email immediately |
| unattended-upgrades reboot needed | Low | Email |

**Why Telegram:** 30-second `@BotFather` setup, free, reliable cross-device push, no team workspace. Slack requires a workspace; Discord feels weird for ops; PagerDuty/Opsgenie/Better Uptime are overkill and not free; email-only misses 03:00 incidents because mobile email push is unreliable.

---

## 8. Server-level metrics

**Day one: Vultr's built-in monitoring + Kuma synthetic checks + a `/healthz/` endpoint** that returns Postgres connection state, cache state, and `shutil.disk_usage`. That's the entire Phase 1 metrics story.

**Add a real stack when:** second VPS appears, unreproducible slowness reports, async workers/queue depth visibility needed, SLA reporting required.

**Phase 2 candidates (best ergonomics first):**
1. **Netdata Cloud free tier** — one agent per host, hosted dashboard, free for personal/unlimited nodes. Best dev ergonomics. Bind agent to localhost; ship over TLS to Netdata Cloud. Don't expose 19999.
2. **Grafana Cloud free tier** — 10k metrics, 50 GB logs, 50 GB traces, 14-day retention. OpenTelemetry-friendly.
3. **Self-hosted Prometheus + Grafana** — only when you have specific custom business KPIs SaaS can't easily ingest.

Don't install Prometheus + node_exporter "just in case" on the prod box — attack surface, RAM, upgrade tax.

---

## 9. Log management

**Hierarchy:**

| Level | What | When |
|-------|------|------|
| 0 | `docker logs` | Ad-hoc debug |
| 1 | `json-file` driver, size+rotation caps | **Phase 1 default** |
| 2 | `journald` + `logrotate` for non-Docker | Phase 1 |
| 3 | Loki / Grafana Cloud / Better Stack | Phase 2 |
| 4 | Structured logs + traces + correlation | Phase 3 |

**Day-one Compose snippet:**
```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "20m"
    max-file: "5"
    compress: "true"
```
~100 MB per service cap. Without this, one chatty bug fills the boot disk in a week.

**Caddy access logs** to a JSON file mounted from host:
```caddy
log {
  output file /var/log/caddy/access.log {
    roll_size 100MiB
    roll_keep 14
    roll_keep_for 720h
  }
  format json
}
```

**Postgres:** `log_min_duration_statement = 1000ms`, `log_checkpoints = on`, `log_connections = off`, `log_disconnections = off`.

**Django:** JSON to stdout (`python-json-logger`), ERROR to Sentry via `LoggingIntegration`, no request bodies, request-ID middleware to correlate with Sentry. JSON now makes Loki trivial later; plain text makes it painful.

**Ship logs externally when:** > 1 host, audit grep requests, or you fear local-log destruction. Phase 2: Grafana Cloud Loki (free 50 GB / 14d) via `promtail` or `vector`; or Better Stack.

**ISO 27001 (A.8.15) retention:** auth events (django-axes or signal handler) 12+ months; admin actions are in DB `LogEntry` already (covered by nightly backup); host `/var/log/auth.log` rotated monthly, shipped quarterly to B2.

---

## 10. Security monitoring

**Day one:**

| Tool | Purpose | Notify |
|------|---------|--------|
| `unattended-upgrades` | Auto patches | Email on action / reboot-required |
| `fail2ban` | SSH + Caddy admin brute-force | **Daily digest only** |
| `pam_exec` SSH hook | Login canary | Email immediately |
| `lynis` weekly cron | CIS audit | Email weekly |
| Cloudflare WAF (free) | Bots/exploits | CF dashboard |
| `auditd` (optional) | `/etc`, `/usr/local/bin` integrity | Email on change |

**unattended-upgrades:** set `Unattended-Upgrade::Mail`, `Automatic-Reboot "true"`, reboot window 04:00 SAST (after 02:30 backup). Tag the window in Kuma so the alert is expected.

**fail2ban:** `[sshd]` + a Caddy jail banning repeat 401s on `/admin/`. **No per-ban email** — set `action = %(action_)s` and send `fail2ban-client status sshd | mail` daily. 99% of bans are bots, per-ban mail is pure noise.

**SSH login email (the simplest, most effective intrusion canary):**
```
# /etc/pam.d/sshd
session optional pam_exec.so /usr/local/bin/ssh-login-notify
```
Three-line bash script reads `$PAM_USER`, `$PAM_RHOST`, hostname, date, mails ops. Pair with `PasswordAuthentication no` and a single allowed key.

**Defer:** OSSEC/Wazuh (Phase 2 earliest), CrowdSec (worth a look in Phase 2 — modern fail2ban with shared block lists), Tripwire/AIDE (auditd covers basics).

**Cloudflare in front of Caddy** — highest-value-per-effort security upgrade: hides origin IP, bot fight + WAF, edge TLS (Caddy stays on Full/strict to origin), 10k req/mo free rate-limiting. Enable before first paying customer.

---

## 11. Concrete day-one install list

**On the VPS (Ansible roles):**
docker + compose; unattended-upgrades; fail2ban (sshd + caddy); ufw (22, 80, 443); `/usr/local/bin/ssh-login-notify` via pam_exec; `/usr/local/bin/backup.sh` (pg_dump → age → rclone → healthcheck); `/etc/cron.d/fls-backup` 02:30; `/etc/cron.d/fls-restore-drill` Sun 03:30 → staging DB; rclone (B2 configured); age (public key only); sops; Caddy in Docker; PG 17 in Docker; FLS web in Docker; healthchecks.io ping integration.

**Off the box:**
Hetzner CX22 (Falkenstein) running Uptime Kuma (Docker) + cloudflared tunnel + Cloudflare Access policy; Sentry SaaS free tier; B2 buckets (daily/weekly/monthly/yearly + media-mirror); Cloudflare (DNS proxied + WAF + Access); Telegram bot.

**In a safe place:**
age private key (1Password + paper); B2 master key; CF API token; Vultr API token; restore-drill log (private git repo).

**Monthly ops overhead:**

| Item | Cost |
|------|------|
| Hetzner CX22 (Kuma) | ~EUR 4.51 (~$5) |
| B2 storage (10 GB) | ~$0.50 |
| Cloudflare / Sentry / Healthchecks / Telegram | $0 |
| **Total** | **~$5–6/mo** |

Whole observability + backup story under $6/mo and ~1 day of one-time setup. More elaborate is procrastination.

---

## 12. What to defer (and the trigger to revisit)

| Capability | Defer until |
|------------|-------------|
| WAL-based PITR | DB > 10 GB, RPO < 24h, or revenue-bearing data |
| Managed Postgres | DB > 20 GB, multi-tenant scale, or maintenance pain |
| Self-hosted metrics stack | > 1 host, custom KPIs, or SLA reporting |
| Loki / log shipping | > 1 host, audit grep, or investigation pain |
| Wazuh / OSSEC | First customer asking "describe your IDS" |
| PagerDuty | Team > 1, or 24/7 SLA committed |
| Self-hosted Sentry | Privacy/data residency contractual constraint |
| Separate ops VPS | Second person joins |
| Multi-region backups | Single-region B2 outage scares you, or compliance demands it |

---

## 13. References

- PostgreSQL backup — https://www.postgresql.org/docs/17/backup-dump.html
- PostgreSQL continuous archiving — https://www.postgresql.org/docs/17/continuous-archiving.html
- pgBackRest — https://pgbackrest.org/
- WAL-G — https://github.com/wal-g/wal-g
- age — https://github.com/FiloSottile/age
- sops — https://github.com/getsops/sops
- rclone — https://rclone.org/
- B2 Object Lock — https://www.backblaze.com/docs/cloud-storage-object-lock
- R2 versioning — https://docs.cloudflare.com/r2/buckets/object-versioning/
- Vultr Monitoring — https://www.vultr.com/docs/vultr-monitoring/
- Vultr Managed Databases — https://www.vultr.com/products/managed-databases/
- Uptime Kuma — https://github.com/louislam/uptime-kuma
- Hetzner Cloud — https://www.hetzner.com/cloud
- Hetzner ISO 27001 — https://www.hetzner.com/unternehmen/zertifizierung/
- Cloudflare Tunnel + Access — https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/self-hosted-public-app/
- Sentry Django — https://docs.sentry.io/platforms/python/integrations/django/
- Sentry pricing — https://docs.sentry.io/pricing/
- Telegram Bot API — https://core.telegram.org/bots
- Healthchecks.io — https://healthchecks.io
- Netdata Cloud — https://www.netdata.cloud/pricing/
- Grafana Cloud — https://grafana.com/products/cloud/
- Better Stack — https://betterstack.com/logs
- Docker json-file driver — https://docs.docker.com/engine/logging/drivers/json-file/
- Caddy logging — https://caddyserver.com/docs/caddyfile/directives/log
- unattended-upgrades — https://wiki.debian.org/UnattendedUpgrades
- fail2ban — https://github.com/fail2ban/fail2ban
- CrowdSec — https://www.crowdsec.net
- Cloudflare WAF — https://developers.cloudflare.com/waf/
- ISO/IEC 27001:2022 — https://www.iso.org/standard/27001
