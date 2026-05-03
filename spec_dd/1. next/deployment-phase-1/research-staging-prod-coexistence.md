# Research: Co-locating staging and production on a single Vultr VPS

## TL;DR — Recommended topology

Run one Caddy, one Postgres container, two Django stacks. Use separate Compose projects per environment, separate Docker networks, and separate logical Postgres databases (NOT separate Postgres containers). Apply hard memory limits to staging so it cannot starve production. Keep Caddy as the single ingress with two virtual hosts.

```
                    Cloudflare (DNS, WAF, free tier)
                                |
                  ----------------------------
                  |                          |
      app.example.com (prod)     staging.example.com
                  |                          |
                  +----------+ +-------------+
                             v v
                          [ Caddy ]            <- single instance, ports 80/443
                             |
          +------------------+------------------+
          |                                     |
prod_web (gunicorn :8000)             staging_web (gunicorn :8000)
compose project: fls-prod              compose project: fls-staging
network: fls-prod-net                  network: fls-staging-net
          |                                     |
          +-------------+   +-------------------+
                        v   v
                    [ Postgres 17 ]          <- single instance
                    databases: fls_prod, fls_staging
                    roles:     fls_prod (owns fls_prod)
                               fls_staging (owns fls_staging)
                    network: fls-db (internal only)
```

---

## 1. Cleanest pattern for two isolated environments on one host

### 1.1 Project-level isolation: separate Compose projects

Two Compose projects with distinct `COMPOSE_PROJECT_NAME` values give you independent lifecycle (`up`/`down`/`logs`) and independent `.env` files. A "one mega compose file with profiles" approach is the wrong unit of isolation here — the blast radius of a typo on `compose down` becomes the entire host.

Recommended layout:

```
/srv/fls/
  caddy/        # ingress, project: fls-ingress
  postgres/     # shared DB, project: fls-db
  prod/         # production app, project: fls-prod
  staging/      # staging app, project: fls-staging
```

Each app compose declares only `web` (and later `worker`) — no DB, no Caddy. They join shared external networks.

### 1.2 Networks (4 external Docker networks)

| Network | Purpose | Containers |
|---|---|---|
| `fls-ingress` | Caddy <-> app web | caddy, prod_web, staging_web |
| `fls-db` | apps <-> Postgres | postgres, prod_*, staging_* |
| `fls-prod-net` | Internal to prod | prod_web, prod_worker |
| `fls-staging-net` | Internal to staging | staging_web, staging_worker |

Postgres is NOT on `fls-ingress`. Caddy is NOT on `fls-db`. Standard least-privilege.

### 1.3 Postgres: one container, two databases (Option A — recommended)

| Option | RAM | Isolation | Backup | Upgrades |
|---|---|---|---|---|
| **A. One Postgres, two DBs** | ~600 MB | Logical only | Per-DB pg_dump | Both upgrade together |
| B. Two Postgres containers | ~1.2 GB | Process-level | Two scripts | Staging can preview |
| C. Managed Postgres for prod | ~300 MB on box | Best | Mixed | Clean |

Option A wins for Phase 1: 600 MB RAM saving matters on an 8 GB box, and per-database role permissions (separate `fls_prod`/`fls_staging` roles) prevent cross-DB queries. The legitimate reason to choose B is testing a Postgres major-version upgrade — handle that as a temporary side-by-side at upgrade time, not as steady state.

Init multiple DBs via a script in `/docker-entrypoint-initdb.d/`:

```bash
#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE USER fls_staging WITH PASSWORD '${STAGING_DB_PASSWORD}';
    CREATE DATABASE fls_staging OWNER fls_staging;
    GRANT ALL PRIVILEGES ON DATABASE fls_staging TO fls_staging;
EOSQL
```

### 1.4 Volumes

- One named volume `fls_pgdata` for Postgres (one data dir holds both DBs).
- Separate bind-mounted media dirs per env so staging cannot serve prod media.
- Per-env log dirs under `/srv/fls/{prod,staging}/logs/` so they rotate independently.

### 1.5 Ports

Both `web` containers can bind 0.0.0.0:8000 inside their own network namespaces — no host conflict. Caddy reaches them by Docker DNS (`prod_web:8000`, `staging_web:8000`). Only 80/443 are published. Postgres is never published.

### 1.6 Compose project naming

Set `COMPOSE_PROJECT_NAME=fls-prod` / `fls-staging` in each `.env` so container names are deterministic regardless of directory rename.

---

## 2. Hostname routing via Caddy

### 2.1 Single Caddy, two virtual hosts (recommended)

```caddyfile
{ email ops@freedomls.example }

app.freedomls.example {
    encode zstd gzip
    reverse_proxy prod_web:8000 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
    }
    @static path /static/*
    handle @static { root * /srv/static/prod; file_server }
    @media path /media/*
    handle @media { root * /srv/media/prod; file_server }
    log {
        output file /var/log/caddy/prod-access.log {
            roll_size 50mb
            roll_keep 5
        }
    }
}

staging.freedomls.example {
    @internal { remote_ip 102.x.x.x/32 192.0.2.0/24 }
    handle @internal { reverse_proxy staging_web:8000 }
    handle { respond "Forbidden" 403 }
}
```

Two pieces of practical advice:
1. **Lock down staging at the edge** — IP allowlist, Caddy `basicauth`, or Cloudflare Access. Staging on a public hostname WILL be scanned and indexed. Add `X-Robots-Tag: noindex` and a `Disallow: /` robots.
2. **Persist Caddy's `/data` as a named volume** — losing ACME account keys triggers Let's Encrypt rate limits (50 certs/registered domain/week).

### 2.2 Why not `caddy-docker-proxy`

Auto-generated Caddyfile from labels is overkill for two sites. A 30-line hand-written Caddyfile is easier to reason about. Re-evaluate at Phase 3 with 5+ services.

### 2.3 Two Caddies?

No. They'd contend for ports 80/443. One Caddy, two site blocks.

### 2.4 Cloudflare interaction

- **Full (strict)** SSL mode in Cloudflare; Caddy's Let's Encrypt cert validates correctly.
- Or use Cloudflare Origin CA + Authenticated Origin Pulls and disable Caddy's Let's Encrypt for those hostnames so only Cloudflare can talk to your origin.
- Cloudflare Tunnel (`cloudflared`) is a clean alternative that hides the VPS IP entirely.

---

## 3. Resource sizing on 8 GB RAM

### 3.1 Memory budget

| Component | Typical | Worst case |
|---|---|---|
| Kernel + Ubuntu 24.04 | 300 MB | 400 MB |
| Docker daemon + containerd | 150 MB | 250 MB |
| Caddy | 40 MB | 100 MB |
| Postgres 17 (1 instance, 2 DBs) | 600 MB | 1.5 GB (shared_buffers=1GB) |
| Prod gunicorn (5 workers, gthread, preload) | 800 MB | 1.4 GB |
| Prod django-tasks worker | 200 MB | 400 MB |
| Staging gunicorn (2 workers) | 300 MB | 500 MB |
| Staging worker | 150 MB | 300 MB |
| Uptime Kuma | 100 MB | 200 MB |
| pg_dump (intermittent) | 50 MB | 200 MB |
| **Total committed** | **~2.6 GB** | **~5.3 GB** |
| **Free for kernel page cache** | **~5.4 GB** | **~2.7 GB** |

**8 GB is enough for Phase 1, with a slim margin under peak.** If page cache headroom drops below ~1.5 GB, Postgres latency degrades non-linearly.

### 3.2 Postgres memory settings (one instance, two DBs)

```conf
shared_buffers = 1GB              # ~12% of RAM (conservative for shared host)
effective_cache_size = 4GB
work_mem = 16MB
maintenance_work_mem = 256MB
max_connections = 50              # 25 prod + 15 staging + 10 admin/backup
wal_buffers = 16MB
random_page_cost = 1.1            # NVMe
effective_io_concurrency = 200    # NVMe
```

Use 15% (not 25%) for `shared_buffers` because we're sharing the host with two app stacks plus OS.

### 3.3 What gets squeezed first

1. **Postgres page cache** — invisible until P95 doubles.
2. **Gunicorn worker bloat** — mitigate with `--max-requests 1000 --max-requests-jitter 100`.
3. **Postgres connection memory** — ~10 MB/conn. Runaway count (leaked DB connections, buggy migration) spikes fast.
4. **Docker logs filling disk** — chatty container fills `/var/lib/docker` in hours without rotation.
5. **Worker count** — `2*cores+1=9` only applies if prod is the sole tenant. With staging on the same box: prod=5, staging=2.

### 3.4 CPU

4 vCPU is enough for 50–200 concurrent users on Django/HTMX. The risk is a staging deploy/test eating a CPU while a prod request queues. Solve with `cpus:` limits.

---

## 4. Risk profile and mitigations

### 4.1 Real failure modes from staging hurting prod

| Failure mode | Symptom | Mitigation |
|---|---|---|
| Long-locking ALTER TABLE on staging blocks `pg_catalog`, autovacuum | Prod slow, autovacuum lag | Per-DB roles; staging has no privileges in prod DB. Note: WAL throughput is still shared. |
| Staging load test saturates Postgres I/O | Prod P99 200ms→5s | `cpus`/`mem_limit` on staging; don't run heavy load tests on shared box |
| Staging memory leak triggers host OOM, kernel kills Postgres | Outage, possible corruption | `mem_limit` on staging (so it OOMs itself first); `oom_score_adj: -500` on Postgres |
| Logs spam fills `/var/lib/docker` | All containers die when disk 100% | `local` log driver with `max-size`/`max-file`; disk alert at 75% |
| Both DBs share WAL, staging bulk insert saturates fsync | Prod write latency jumps | Observe first; if it happens, split Postgres |
| Failed Caddy reload kills both sites | Total outage | `caddy validate Caddyfile` before reload; `caddy reload` is graceful |
| Backup job spikes I/O | Brief slowdown | Off-hours window; `nice`/`ionice`, or `cpus: 0.5` on backup container |
| Staging auth bug enables pivot | Lateral movement | Network segmentation, distinct DB creds, distinct `SECRET_KEY` |

### 4.2 Per-service resource limits

Staging (hard limits):
```yaml
services:
  web:
    deploy:
      resources:
        limits:    { cpus: '1.5', memory: 800M }
        reservations: { memory: 400M }
    mem_swappiness: 0
    logging:
      driver: local
      options: { max-size: 50m, max-file: 5 }
    networks: [fls-ingress, fls-db, fls-staging-net]
```

Prod (soft floor, generous limit):
```yaml
services:
  web:
    deploy:
      resources:
        limits:    { memory: 1500M }
        reservations: { memory: 800M }
```

`deploy.resources` is honoured by `docker compose up` from Compose v2 onward (originally Swarm-only). Verify with `docker stats`.

### 4.3 OOM protection for Postgres

```yaml
services:
  db:
    image: postgres:17
    oom_score_adj: -500
    deploy:
      resources:
        reservations: { memory: 1500M }
```

This biases the kernel OOM-killer toward app containers. Combined with app `mem_limit` (apps OOM themselves before kernel-wide pressure), this is the right pattern.

### 4.4 Disk fill mitigations

`/etc/docker/daemon.json`:
```json
{ "log-driver": "local", "log-opts": { "max-size": "50m", "max-file": "5" } }
```
Plus: logrotate on `/srv/fls/{prod,staging}/logs/`, `df` alert at 80%, Postgres `log_min_duration_statement=500ms`.

### 4.5 Security blast radius

- **Never** copy prod's `.env` to staging — distinct `SECRET_KEY`, DB role, media volume.
- Sanitize prod data before importing to staging (strip PII, randomize passwords).
- Staging IP-restricted at Caddy or Cloudflare Access.

---

## 5. When to split onto two VPSs — concrete triggers

Don't split on a feeling. Split when ANY is true for two consecutive weeks:

1. **Peak CPU > 70% for >15 min/day.**
2. **Postgres page cache hit ratio < 95%** (`pg_stat_database`).
3. **Total RSS > 6.5 GB at p95** (less than 1.5 GB free for kernel cache).
4. **Need to test destructive changes** safely — Postgres major upgrade, OS upgrade, Docker engine upgrade.
5. **Auditor asks** "is staging isolated from prod?" — cheapest answer is "yes, separate VPS."
6. **Second tenant of meaningful size** (500+ active students on one customer) where staging contention becomes contractual risk.
7. **Frequent heavy load tests** (Locust, k6) — load tests on prod's box defeat the purpose.

Cheap split option: Vultr Regular Performance 2 vCPU/4 GB at $24/month for staging, joined to the same Tailnet. DB can stay on the prod box (over Tailscale) or move to managed Postgres at the same time.

---

## 6. Backup implications

### 6.1 pg_dump cost

- Estimated DB sizes at 1000 students: prod ~2–5 GB, staging ~1 GB.
- Compressed `pg_dump -Fc`: prod ~400 MB–1 GB, staging ~200 MB.
- Time: ~50–100 MB/s on NVMe. 5 GB → ~1 minute.
- RAM: ~50–200 MB transient.

**8 GB box backs up both DBs comfortably.**

### 6.2 Schedule and retention

```
00:30  pg_dump fls_staging   -> /srv/fls/backups/staging/staging-YYYYMMDD.dump
01:00  pg_dump fls_prod      -> /srv/fls/backups/prod/prod-YYYYMMDD.dump
01:30  rclone sync backups   -> Backblaze B2
02:00  find ... -mtime +14 -delete
```

Local 14d, B2 lifecycle 30d daily + 12wk weekly + 12mo monthly = ~36 dumps × ~1 GB = **~$0.18/month at B2 rates**.

### 6.3 What pg_dump does NOT cover

- **PITR** (needs WAL archiving) — skip until Phase 2 or when an auditor requires it.
- **Media files** — separate `restic`/`rclone sync` of `/srv/fls/{prod,staging}/media/` (likely larger than DB).
- **Caddy `/data` volume** (ACME keys) — small, but rate-limit pain if lost.
- **`.env` files** — encrypt and store in a password manager, NOT in B2 alongside DB dumps.

### 6.4 Test restores

Quarterly: spin up a temp Postgres container, `pg_restore`, run `manage.py check` and a sanity query. **Untested backup ≠ backup.**

### 6.5 Free DB cloning for staging refresh

`pg_dump fls_prod | psql fls_staging` (with sanitization) — no network transfer, ~30s for a 2 GB DB. Genuinely valuable for a solo dev.

---

## 7. Concrete recommendations for FLS (opinionated)

1. **Yes, run staging and prod on the same Vultr 4 vCPU / 8 GB / 180 GB NVMe box for now.** Right cost/complexity tradeoff at FLS's scale.
2. **Topology:** one Caddy, one Postgres (two DBs), two app Compose projects, four `docker-compose.yml` files, four external Docker networks.
3. **Day 1 hardening (non-negotiable):**
   - Per-service `mem_limit`/`cpus` on staging.
   - `oom_score_adj: -500` on Postgres.
   - `local` log driver with rotation in both `/etc/docker/daemon.json` and per-service compose.
   - Distinct DB role + `SECRET_KEY` + media bind mount per env.
   - Caddy IP-restricts staging OR Cloudflare Access in front; robots/noindex on staging.
   - `pg_dump` cron + B2 sync from Day 1.
4. **Don't skip:** `--max-requests 1000 --max-requests-jitter 100` on gunicorn; disk usage alert at 75%; quarterly restore tests.
5. **Plan migration symmetry now:** keep `docker-compose.yml` shape symmetric so moving staging to a second VPS is `scp` + `docker compose up -d`. Use Tailscale to keep the cross-host DB option open.
6. **Single biggest mistake to avoid:** sharing a `.env`/`SECRET_KEY` across prod and staging — converts a staging compromise into a prod compromise.
7. **Single biggest cost saver vs full separation:** the shared Postgres instance (~600 MB RAM saved). Split only when planning a major-version Postgres upgrade or when one of the section-5 triggers fires.

---

## Reference URLs

**Compose / multi-environment patterns**
- https://docs.docker.com/compose/how-tos/production/
- https://release.com/blog/6-docker-compose-best-practices-for-dev-and-prod
- https://collabnix.com/leveraging-compose-profiles-for-dev-prod-test-and-staging-environments/
- https://nickjanetakis.com/blog/best-practices-around-production-ready-web-apps-with-docker-compose

**Caddy reverse proxy patterns**
- https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- https://caddyserver.com/docs/caddyfile/patterns
- https://caddy.community/t/proxy-multiple-websites-all-running-inside-docker-containers/18894
- https://github.com/lucaslorentz/caddy-docker-proxy

**Postgres tuning and multi-DB**
- https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server
- https://www.enterprisedb.com/postgres-tutorials/how-tune-postgresql-memory
- https://www.crunchydata.com/blog/optimize-postgresql-server-performance
- https://github.com/mrts/docker-postgresql-multiple-databases

**Resource limits and noisy-neighbor protection**
- https://docs.docker.com/engine/containers/resource_constraints/
- https://howtodoinjava.com/devops/docker-memory-and-cpu-limits/

**Log management and disk pressure**
- https://docs.docker.com/engine/logging/configure/
- https://signoz.io/blog/docker-log-rotation/

**Backup automation**
- https://serversinc.io/blog/automated-postgresql-backups-in-docker-complete-guide-with-pg-dump/
- https://github.com/kartoza/docker-pg-backup

**Staging vs production — risks**
- https://nimbushosting.co.uk/blog/best-practices-why-use-a-separate-server-for-your-staging-environment
- https://entro.security/blog/securing-staging-environments-best-practices/

**Django settings and environment isolation**
- https://www.coderedcorp.com/blog/django-settings-for-multiple-environments/
- https://djangostars.com/blog/configuring-django-settings-best-practices/

**Django + Docker production guides**
- https://testdriven.io/blog/dockerizing-django-with-postgres-gunicorn-and-nginx/
