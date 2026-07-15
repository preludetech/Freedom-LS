# Hosting other apps on the same VM — research

> **Question raised:** the `support-concrete-project-deployment` effort provisions a single Vultr VPS
> running the concrete FLS stack (Caddy + Gunicorn + PostgreSQL via Docker Compose). Can that same VM
> also host **other, unrelated sites** (other Django projects, a static marketing site, a small API)?
> Do we "just add another `docker-compose.yml`"?

## Short answer

**Yes — and the architecture already points this way.** "Just add another docker-compose" is
*almost* right, with **one caveat about the proxy layer**.

The design already runs **more than one compose stack on the same host**: `concrete_project_idea.md`
§"Environments: staging + prod on one VPS" (`concrete_project_idea.md:135–151`) launches the same app
twice with different `COMPOSE_PROJECT_NAME` + `--env-file`, giving each its own containers, network,
and named volumes ("the two stacks never share state"), all fronted by **one shared Caddy routing by
hostname**. Hosting a *third, unrelated* Django site is the same pattern with a different app image
and a different hostname. Nothing about the topology has to change.

The single caveat: **only one process on the VM can bind host ports 80 and 443.** So each extra app
must **not** bring its own port-binding reverse proxy — every site is proxied by the *one* shared
Caddy edge.

## The load-bearing constraint

A production HTTP/HTTPS site needs ports 80 and 443. On a single host those ports can be bound by
**exactly one process**. If two independent compose stacks each ship their own proxy binding
`80:80`/`443:443`, the second `docker compose up` fails with a port-in-use error.

- The repo **today** binds these on the `nginx` service (`docker-compose.yml`, `ports: "80:80"`).
- The **target** (Spec 5 §5.3) binds them on Caddy.

Either way, the port-owning proxy must be a **single shared edge** in front of *all* apps — not a
per-app service that ships once per stack. This is the same reason the idea already speaks of "**one
shared Caddy**" fronting both the staging and prod stacks rather than one Caddy per stack.

Everything behind that edge (the Django `web` containers, the Postgres containers) publishes **no
host ports** — it is reachable only over an internal Docker network, and the edge proxies to it by
container name. That is also the DB-security posture Spec 1 §5.1-D already requires (the `db` service
publishes no `ports:`).

## Recommended pattern — one shared edge + per-app stacks on a shared network

Author Caddy as its **own standalone "edge" compose stack** that owns 80/443, and put every app stack
on a **shared external Docker network** so the edge can reach each app's `web` container across
compose projects. Adding a site is then: bring up its stack, add one host block, reload Caddy.

```
                 ┌───────────────────────── VPS ─────────────────────────┐
[Cloudflare] ──► │  edge stack:  Caddy  (binds :80/:443, auto-HTTPS)      │
                 │        │  routes by Host header, reverse_proxy only    │
                 │        ├── fls.example.com        → fls_web:8000        │
                 │        ├── staging.example.com    → fls_staging_web:8000│
                 │        └── other.example.com      → other_web:8000      │
                 │                                                          │
                 │  shared external network:  edge                         │
                 │   ├─ FLS stack     (COMPOSE_PROJECT_NAME=fls)           │
                 │   │    web + db(named vol)   — no host ports            │
                 │   ├─ FLS staging   (COMPOSE_PROJECT_NAME=fls_staging)   │
                 │   │    web + db(named vol)   — no host ports            │
                 │   └─ Other Django  (COMPOSE_PROJECT_NAME=other)         │
                 │        web + db(named vol)   — no host ports            │
                 └────────────────────────────────────────────────────────┘
```

Why the edge is its **own** stack and not a service inside the FLS compose: if Caddy lived inside the
app compose, running that compose twice (staging + prod) would start two Caddys both grabbing 80/443
— the exact collision above. Keeping the edge separate is what lets the *same* app compose file run N
times, and lets a completely different app join without touching FLS's files.

### 1. The shared network (create once per host)

```bash
docker network create edge
```

### 2. The edge stack (`edge/docker-compose.yml`)

```yaml
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data      # cert storage — persist so HTTPS survives restarts
      - caddy_config:/config
    networks:
      - edge

networks:
  edge:
    external: true            # created above; shared by every app stack

volumes:
  caddy_data:
  caddy_config:
```

### 3. The shared `edge/Caddyfile` — one block per site

```caddyfile
# FLS (proxy-only: WhiteNoise serves /static, media is on S3 — no file_server here)
{$HOST_DOMAIN} {
    reverse_proxy fls_web:8000
}

# Another, unrelated Django site on the same VM
other.example.com {
    reverse_proxy other_web:8000
}
```

Caddy sets `X-Forwarded-Proto`/`-For`/`-Host` automatically on `reverse_proxy` and acquires/renews
certs per host with no Certbot (Spec 5 §5.3). Reload after editing:

```bash
docker compose -p edge exec caddy caddy reload --config /etc/caddy/Caddyfile
```

### 4. Each app stack joins `edge` and publishes no host ports

A second, non-FLS Django project's compose looks like any normal single-VPS Django stack — it just
attaches its `web` to the external `edge` network and exposes nothing to the host:

```yaml
# other-app/docker-compose.yml   (run with: docker compose -p other --env-file other.env up -d)
services:
  web:
    build: .
    container_name: other_web        # the name Caddy's reverse_proxy targets
    env_file: [other.env]
    expose:
      - "8000"                        # visible on the edge network only, not the host
    depends_on:
      db:
        condition: service_healthy
    networks:
      - default                       # talk to its own db
      - edge                          # be reachable by the shared Caddy

  db:
    image: postgres:17
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - other_db_data:/var/lib/postgresql/data   # named volume, never a bind mount
    # no ports: — DB is not published to the host

networks:
  edge:
    external: true

volumes:
  other_db_data:
```

The FLS stack is identical in shape (it just uses the FLS image and `container_name: fls_web`), so
the FLS `docker-compose.yml` needs only two additions to participate: attach `web` to the external
`edge` network, and drop the bundled `nginx` service (its job moves to the shared edge).

## Recipe — adding a new site to an existing host

1. **Create the app repo / compose** with its own `Dockerfile` (or a prebuilt image) and a
   `docker-compose.yml` whose `web` service attaches to the external `edge` network and publishes
   **no** host ports.
2. **Give it its own identity:** unique `COMPOSE_PROJECT_NAME` and a dedicated `--env-file`
   (`other.env`) so its containers, network, and volumes never collide with FLS's.
3. **Give it its own database:** its own Postgres container + named volume (see below).
4. **Bring it up:** `docker compose -p other --env-file other.env up -d`.
5. **Route it:** add a host block to the shared `Caddyfile`
   (`other.example.com { reverse_proxy other_web:8000 }`) and reload Caddy.
6. **Point DNS at the VM** for the new hostname (Cloudflare A/AAAA record, orange-cloud proxy per the
   FLS edge posture). Caddy provisions the TLS cert on first request.

That is the whole "add another docker-compose" story — plus steps 5–6 for the shared proxy and DNS,
which are the parts "just another compose" glosses over.

## Database isolation options

- **Default (recommended for V1): one Postgres container per app**, each with its own named volume.
  This matches the FLS stacks' "never share state" rule (`concrete_project_idea.md:143–144`): a bad
  migration, a runaway query, or a restore on one app cannot touch another. Costs ~one Postgres
  process worth of RAM per app.
- **Alternative: one shared Postgres, a database + role per app.** Saves the per-app Postgres memory
  overhead, but couples the apps' blast radius — a shared-server outage, a bad `pg_upgrade`, or a
  connection-limit exhaustion hits everyone, and backup/restore is no longer per-app. Only worth it
  under real RAM pressure; keep per-app DBs until then.

## Resource & operational notes

- **RAM is the first ceiling on a small VPS.** Each site adds a Gunicorn worker set **and** (by
  default) a Postgres. Budget accordingly and prefer a **vertical resize** (a Vultr reboot-resize)
  before turning a single box into a fleet — the idea defers Swarm/k8s until the multi-project fleet
  genuinely outgrows one resized VPS (`concrete_project_idea.md:533–541`).
- **Log caps apply per app.** The per-service `json-file` `max-size` + `max-file` caps (Spec 5 §5.2)
  must be set on every service of every stack, or one chatty app can fill the disk for all of them.
- **Backups multiply.** Each app's `pg_dump` + off-box sync is separate; the backup job must enumerate
  every app database, not just FLS's.
- **Health & redirects are unaffected.** FLS's `/health/*` stays off the public vhost (Spec 2) and
  the shared edge only proxies — no per-app coupling.

## Implication for Spec 5 (callout — not a change to that spec)

Spec 5 §5.2/§5.3 describes Caddy as part of the app `docker-compose.yml`. For this multi-app story
(and even for the staging+prod story the idea already commits to), the cleanest shape is to author
**Caddy as a standalone edge stack** with the app stacks joining a shared external network — so the
app compose can run N times and other apps can attach without editing FLS's files. This is a
structuring note for whoever implements Spec 5; it does **not** change the spec's requirements
(single shared Caddy, auto-HTTPS, host routing, proxy-only, `{$HOST_DOMAIN}`, no `/health/*` route
— all still hold). It only says *where* the Caddy service is defined: its own compose, not embedded
in the app's.

## Current-vs-target note

This recipe is written against the **target** Caddy edge, which is not built yet: the repo today
still ships `nginx` in `docker-compose.yml`, and `docs/product/deployment.md` marks the Caddy/edge
architecture as **planned**. The same shared-edge shape works in the interim with **nginx** as the
single edge (one nginx binding 80/443, `proxy_pass` per `server {}` block, manual Certbot for certs)
— but the moment you have more than one site to route, Caddy's automatic per-host HTTPS is the reason
the target picks it. Build the edge on Caddy when Spec 5 lands; don't reintroduce a per-app proxy.

## References

- `concrete_project_idea.md` §"Environments: staging + prod on one VPS" (`:135–151`) — the existing
  two-stacks-one-host, one-shared-Caddy pattern this generalizes; k8s/Swarm fleet threshold (`:533–541`).
- Spec 5 (`../../1. next/support-concrete-project-deployment-5-template-repo-scaffolding/1. spec.md`)
  §5.2 (compose: named volumes, log caps, `COMPOSE_PROJECT_NAME`, no published `5432`), §5.3
  (Caddyfile: proxy-only, auto-HTTPS, host routing, `{$HOST_DOMAIN}`).
- `docker-compose.yml` (repo root) — current `nginx` edge binding `80:80`, to be superseded.
- `docs/product/deployment.md` — records the Caddy target as planned, nginx as current.
- Spec 1 §5.1-D — `db` publishes no host ports (the same "no host ports behind the edge" posture used
  for every app here).
