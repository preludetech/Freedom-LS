# Research: Ansible + GitHub Actions Deployment Automation

**Context.** FreedomLS (Django 6, PostgreSQL 17, Caddy, HTMX) deployed to a single Vultr High-Performance VPS in Johannesburg via Docker Compose. Staging and prod live on the same host as separate Compose projects. Solo developer. GHCR for images. Cloudflare for DNS. Sentry (free) and Uptime Kuma already in scope.

**Goal.** Push to a branch, get a deployment. No SSH-and-pray. Two-command bootstrap of a fresh VPS. Rollback in under 60 seconds. Secrets never live in plaintext in the repo.

This document is opinionated. Where there's a choice, it picks one and explains why.

---

## 1. Ansible playbook structure for a solo dev

### Repo layout

Keep Ansible in the same repo as the Django code. Ops-as-code, single source of truth, PRs that change deploy config travel with the code that needs it. A separate `infra` repo is overkill for one person.

```
deploy/
  ansible.cfg
  inventory/
    hosts.yml                    # production, staging hostgroups
    group_vars/
      all/
        vars.yml                 # non-secret defaults
        vault.yml                # ansible-vault encrypted
      production/
        vars.yml
        vault.yml
      staging/
        vars.yml
        vault.yml
  playbooks/
    bootstrap.yml                # run once on a fresh VPS (root)
    site.yml                     # converge full host (idempotent)
    deploy.yml                   # called by CI for app deploys
    backup.yml                   # ad-hoc DB backup
    restore.yml                  # ad-hoc DB restore
  roles/
    common/
    docker/
    caddy_config/
    app_bootstrap/
    backups/
    monitoring/
  files/
    caddy/Caddyfile.j2
    compose/docker-compose.prod.yml.j2
    compose/docker-compose.staging.yml.j2
    systemd/freedomls-backup.timer.j2
  requirements.yml               # collections (community.docker, etc.)
  .vault-pass.gpg                # encrypted with your GPG key, decrypted in CI
```

### `ansible.cfg`

Minimal, but force the safer defaults:

- `forks = 5`
- `host_key_checking = True` (fingerprint pinned in inventory)
- `pipelining = True`
- `vault_password_file = ./scripts/vault-pass.sh`
- `stdout_callback = yaml`

### `inventory/hosts.yml`

One physical host, two logical groups so role/var resolution is clean:

```yaml
all:
  children:
    production:
      hosts:
        fls-jhb-1:
          ansible_host: <vultr-ip>
          ansible_user: deploy
          compose_project: freedomls_prod
          app_domain: app.freedomls.example
          env_file: /opt/freedomls/prod/.env
    staging:
      hosts:
        fls-jhb-1:
          ansible_host: <vultr-ip>
          ansible_user: deploy
          compose_project: freedomls_staging
          app_domain: staging.freedomls.example
          env_file: /opt/freedomls/staging/.env
```

Same host appears in both groups. Group vars stack predictably: `all` -> `staging`/`production` -> host.

### Role breakdown

Six roles, each <100 lines of tasks. Anything bigger and you're hiding complexity.

#### `common`

Baseline hardening — runs first, runs often, idempotent.

Responsibilities:

- Set hostname and `/etc/hosts`.
- Configure `/etc/timezone` and enable `systemd-timesyncd`.
- Manage the `deploy` user (uid pinned, sudo without password for `docker compose` only via narrow sudoers snippet, authorized_keys from `vault.yml`).
- Disable root SSH login, password auth, X11 forwarding. Set `AllowUsers deploy`. Move SSH to a non-default port (e.g. 2202) — modest but real noise reduction.
- Install `unattended-upgrades` with `Unattended-Upgrade::Automatic-Reboot "false"` (we don't want surprise reboots; we'll handle reboots via Ansible).
- Install and configure `fail2ban` with the `sshd` jail.
- Configure `ufw`: deny incoming default, allow SSH (custom port), 80, 443. Outgoing open.
- Configure `journald` persistence and size cap (`SystemMaxUse=500M`).
- Set up `/etc/security/limits.d/` for the `deploy` user (`nofile 65536`).

#### `docker`

Install Docker Engine + Compose v2 + the Compose plugin from Docker's apt repo (not Snap, not Ubuntu's `docker.io`).

Responsibilities:

- Add Docker's GPG key and apt source for Ubuntu 24.04 (noble).
- Install `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`.
- Install the `docker-rollout` Compose plugin (single shell script). Reference: https://github.com/Wowu/docker-rollout
- Add `deploy` user to `docker` group.
- Configure `/etc/docker/daemon.json`: `log-driver: json-file`, `log-opts: {max-size: "10m", max-file: "3"}`, `live-restore: true`, `default-address-pools` so we don't collide with Vultr's RFC1918 ranges.
- Login to GHCR using a pull-only PAT stored in vault.

#### `caddy_config`

Caddy runs in Docker Compose, not on the host. This role manages the Caddyfile and TLS state on the host that Caddy mounts.

Responsibilities:

- Create `/opt/freedomls/caddy/{config,data}` with correct ownership.
- Render `Caddyfile` from a Jinja template using inventory vars (staging + prod virtual hosts in one Caddyfile — one shared Caddy so port 80/443 isn't fought over).
- Render Cloudflare DNS API token into Caddy's environment file (for DNS-01 challenge).
- Reload Caddy via `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`.
- Notify a handler that runs `caddy validate` first (fail fast on bad config).

#### `app_bootstrap`

Prepares per-stack on-disk state so Compose can come up. Runs separately for `staging` and `production`.

Responsibilities:

- Create `/opt/freedomls/{stack}/` with subdirs: `compose/`, `media/`, `static/`, `postgres-data/`, `backups/`.
- Render `docker-compose.yml` from a Jinja template, parameterised by stack name, image tag (default `latest`), exposed ports (only Caddy publishes to host; web is internal-only), env_file path.
- Render `.env` from `vault.yml` (mode 0600, owner `deploy`).
- `docker network create freedomls_{stack}_internal` if missing.
- First-run only: `docker compose pull && docker compose up -d db` to get Postgres going so subsequent deploys can run migrations.
- Register a daily `systemd` service+timer for `manage.py clearsessions`.

#### `backups`

PostgreSQL backups to S3-compatible storage. Daily.

Responsibilities:

- Drop in a script `/usr/local/bin/freedomls-backup.sh` that runs `docker compose exec -T db pg_dump -Fc | age -r $PUBKEY | aws s3 cp - s3://...`.
- Encryption pubkey stored in role files; private key NOT on the box (offline only).
- Systemd service + timer (`OnCalendar=*-*-* 02:30:00`, `RandomizedDelaySec=15m`).
- Retention via S3 lifecycle policy.
- A second timer that does `pg_dump` to local disk weekly as belt-and-braces, retained 7 days.
- A simple healthcheck file written on success that Uptime Kuma can `curl`.

#### `monitoring`

Uptime Kuma + Sentry agent + node exporter optional.

Note: Uptime Kuma should NOT run on the box it monitors. Use this role for Sentry release notifications and a tiny disk/CPU alerter that posts to a Kuma push URL hosted elsewhere (see backups-monitoring research).

### Anti-patterns to avoid

- **Don't** create a `users` role separate from `common`. Solo dev, one user, no need.
- **Don't** template the Django app's settings via Ansible. Settings come from the image; Ansible only manages `.env`.
- **Don't** use `become: true` at the play level; scope it per-task.
- **Don't** vendor roles from Galaxy for things you can write in 30 lines.

References:

- Ansible best-practices directory layout: https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html
- `community.docker` collection: https://docs.ansible.com/ansible/latest/collections/community/docker/

---

## 2. Bootstrapping from blank Ubuntu 24.04

### Pre-Ansible (manual, ~5 minutes, one time)

1. Provision the Vultr instance: Ubuntu 24.04, High Performance plan, Johannesburg region, attach SSH key during creation.
2. Note the IPv4. Add an A record at Cloudflare for `app.freedomls.example` and `staging.freedomls.example`, **DNS only** (grey cloud) — proxy mode interferes with Caddy's HTTP-01 challenge if you don't configure DNS-01 first.
3. From your laptop: `ssh root@<ip>` once, accept the host key, exit.
4. `ansible-inventory --list -i deploy/inventory/hosts.yml` to confirm parsing.

### Ansible bootstrap play (`playbooks/bootstrap.yml`, runs as `root`)

Order of tasks:

1. **Wait for cloud-init.** `ansible.builtin.command: cloud-init status --wait`.
2. **APT base update.** `apt update && apt upgrade -y`. Reboot if `/var/run/reboot-required`.
3. **Set hostname + timezone.** `hostnamectl set-hostname fls-jhb-1`, `timedatectl set-timezone Africa/Johannesburg`.
4. **Time sync.** Ensure `systemd-timesyncd` is enabled and synced.
5. **Create `deploy` user.** UID 2000, primary group `deploy`, sudo membership, authorized_keys from vault.
6. **Sudoers snippet** at `/etc/sudoers.d/deploy`: tight whitelist, validated by `visudo -cf`.
7. **SSH hardening.** Template `/etc/ssh/sshd_config.d/99-fls.conf`:
    - `Port 2202`
    - `PermitRootLogin no`
    - `PasswordAuthentication no`
    - `KbdInteractiveAuthentication no`
    - `AllowUsers deploy`
    - `ClientAliveInterval 300`
    - `MaxAuthTries 3`
    - Validate with `sshd -t`, then restart sshd. After this point, root SSH is dead.
8. **Swap.** Vultr High Performance plans have RAM but no swap by default. 2 GB swapfile, `vm.swappiness=10`.
9. **`unattended-upgrades`** with security origins only, `Automatic-Reboot "false"`.
10. **fail2ban** with `[sshd]` enabled at the new port.
11. **UFW.** `ufw default deny incoming; allow 2202/tcp, 80/tcp, 443/tcp; --force enable`.
12. **Log rotation.** Docker container logs are capped via `daemon.json`. Add stanza for `/opt/freedomls/*/logs/*.log` (rotate weekly, 4 weeks, compress, copytruncate).
13. **Kernel sysctls.** `net.core.somaxconn=4096`, `vm.overcommit_memory=1` (Postgres likes this), `fs.file-max=2097152`.
14. **Docker engine** (handoff to `docker` role).
15. **GHCR login.** Stores a pull-only credential in `/home/deploy/.docker/config.json`.
16. **App bootstrap** for both stacks. Creates dirs, renders compose files and `.env`, brings up Postgres and Caddy.
17. **Caddy first run.** Issues TLS certs via Cloudflare DNS-01.
18. **Backups + monitoring.**
19. **Reboot once** at the end to confirm cold-start.

After this single `ansible-playbook playbooks/bootstrap.yml` run, the box is ready to receive `docker compose pull && docker compose up -d` from the deploy workflow.

References:

- Ubuntu 24.04 hardening: https://ubuntu.com/security/certifications/docs/usg
- Docker daemon log limits: https://docs.docker.com/config/containers/logging/configure/
- `unattended-upgrades`: https://wiki.debian.org/UnattendedUpgrades

---

## 3. GitHub Actions deploy workflow

### Workflow files

Two files, clear separation:

- `.github/workflows/ci.yml` — runs on every PR and every push to main: lint + test.
- `.github/workflows/deploy.yml` — runs on push to `main` (deploys staging) and on tag push `v*` (deploys prod).

### `ci.yml` shape

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy freedom_ls

  test:
    runs-on: ubuntu-24.04
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/test  # pragma: allowlist secret
      DJANGO_SETTINGS_MODULE: config.settings.test
      SECRET_KEY: ci-not-secret
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
      - run: uv run pytest -x --cov=freedom_ls --cov-report=xml
```

### `deploy.yml` shape

```yaml
name: Deploy
on:
  push:
    branches: [main]
    tags: ['v*']

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false

jobs:
  resolve-env:
    runs-on: ubuntu-24.04
    outputs:
      stack: ${{ steps.r.outputs.stack }}
      image_tag: ${{ steps.r.outputs.image_tag }}
    steps:
      - id: r
        run: |
          if [[ "${{ github.ref }}" == refs/tags/v* ]]; then
            echo "stack=production" >> $GITHUB_OUTPUT
            echo "image_tag=${GITHUB_REF_NAME}" >> $GITHUB_OUTPUT
          else
            echo "stack=staging" >> $GITHUB_OUTPUT
            echo "image_tag=staging-${GITHUB_SHA::12}" >> $GITHUB_OUTPUT
          fi

  build:
    needs: resolve-env
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ghcr.io/${{ github.repository }}/web
          tags: |
            type=raw,value=${{ needs.resolve-env.outputs.image_tag }}
            type=raw,value=latest,enable=${{ startsWith(github.ref, 'refs/tags/v') }}
            type=sha,format=long
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: deploy/docker/web.Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            GIT_SHA=${{ github.sha }}

  deploy:
    needs: [resolve-env, build]
    runs-on: ubuntu-24.04
    environment: ${{ needs.resolve-env.outputs.stack }}
    concurrency:
      group: deploy-${{ needs.resolve-env.outputs.stack }}
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
      - name: Install SSH key
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.DEPLOY_SSH_KEY }}
      - name: Add host to known_hosts
        run: ssh-keyscan -p 2202 -H ${{ secrets.DEPLOY_HOST }} >> ~/.ssh/known_hosts
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - name: Install Ansible
        run: pip install ansible==10.* ansible-lint
      - name: Decrypt vault
        run: echo "${{ secrets.ANSIBLE_VAULT_PASS }}" > .vault-pass
      - name: Run deploy playbook
        run: |
          ansible-playbook -i deploy/inventory/hosts.yml \
            deploy/playbooks/deploy.yml \
            --limit ${{ needs.resolve-env.outputs.stack }} \
            -e image_tag=${{ needs.resolve-env.outputs.image_tag }}
      - name: Smoke test
        run: |
          for i in {1..30}; do
            code=$(curl -s -o /dev/null -w "%{http_code}" \
              https://${{ vars.APP_DOMAIN }}/healthz)
            [[ "$code" == "200" ]] && exit 0
            sleep 5
          done
          exit 1
      - name: Rollback on failure
        if: failure()
        run: |
          ansible-playbook -i deploy/inventory/hosts.yml \
            deploy/playbooks/deploy.yml \
            --limit ${{ needs.resolve-env.outputs.stack }} \
            -e image_tag=last-known-good \
            -e skip_migrations=true
      - name: Notify Sentry of release
        run: |
          curl -X POST https://sentry.io/api/0/organizations/$ORG/releases/ \
            -H "Authorization: Bearer ${{ secrets.SENTRY_AUTH }}" \
            -d '{"version":"${{ needs.resolve-env.outputs.image_tag }}", "projects":["freedomls"]}'
```

### Secrets / vars used

GitHub repo Secrets:

- `DEPLOY_SSH_KEY` — ed25519 private key, public half in `deploy` user's `authorized_keys`.
- `DEPLOY_HOST` — IP address.
- `ANSIBLE_VAULT_PASS` — passphrase that decrypts `vault.yml`.
- `SENTRY_AUTH` — release tagging.

GitHub Environments:

- `staging` — no required reviewers, no wait timer.
- `production` — required reviewer (yourself), 5-minute wait timer (lets you Ctrl+C if you tagged the wrong commit), restricted to tags matching `v*`.

References:

- GitHub Actions deployments + environments: https://docs.github.com/en/actions/deployment/targeting-different-environments
- `docker/build-push-action` with GHA cache: https://docs.docker.com/build/ci/github-actions/cache/
- `webfactory/ssh-agent`: https://github.com/webfactory/ssh-agent

---

## 4. Migration strategy during deploy

### One-shot migration container

Run migrations as a **separate, ephemeral container** before swapping web. Don't bake migrations into web container startup — that races multiple replicas and obscures failures. The deploy playbook does:

```
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py collectstatic --noinput  # if not baked in
docker rollout web    # swap web container
```

### Order matters

1. Pull new image (`docker compose pull web`).
2. Run `migrate --plan --check`. If non-zero, proceed; if zero, skip step 3.
3. Run `migrate --noinput` against the live DB.
4. Swap web container with `docker rollout web`.
5. Smoke-test `/healthz`.

### Backwards-incompatible migrations: expand-contract

For a solo dev with one prod stack, true zero-downtime backwards-incompatible migrations are rarely worth the engineering. But the discipline is cheap:

- **Expand** (deploy N): add new column nullable, dual-write in code. New code reads either old or new.
- **Contract** (deploy N+1, days/weeks later): backfill, drop old column, remove dual-write.

Operations always safe in a single deploy:

- Adding a nullable column.
- Adding a column with a server-side default (Postgres 11+ does this in O(1)).
- Adding an index `CONCURRENTLY` (Django 4.0+: `AddIndexConcurrently`).
- Adding a new table.

Operations that need expand-contract:

- Renaming a column or table.
- Dropping a column the running code reads.
- Changing a column type incompatibly.
- Adding a `NOT NULL` column without default.
- Adding a unique constraint on existing data.

Operation that needs explicit downtime:

- Long-running data migrations on tables >10M rows. Run them as a Django management command outside the deploy.

### Static files: build-time vs runtime

**Build-time, baked into the image.** Run `collectstatic` in the Dockerfile during build:

```dockerfile
# build stage
RUN DJANGO_SECRET_KEY=build-only-not-secret \
    DATABASE_URL=sqlite:///tmp.db \
    python manage.py collectstatic --noinput
```

Then in the final stage, `COPY --from=build /app/staticfiles /app/staticfiles`. Use `whitenoise` to serve them from Django until you have a CDN.

References:

- Django migrations operations: https://docs.djangoproject.com/en/6.0/ref/migration-operations/
- Whitenoise: https://whitenoise.readthedocs.io/

---

## 5. Zero-or-low-downtime deploy on a single host

### The options

1. **`docker compose up -d` (naive).** Stops old container, starts new. ~3–10 seconds of 502s. Acceptable for staging.
2. **`docker-rollout` plugin.** Brings up a second copy of `web` alongside the old, waits for healthcheck, drains the old. Caddy load-balances during the swap. Effectively zero downtime for stateless web. https://github.com/Wowu/docker-rollout
3. **Blue-green compose stacks.** Two complete Compose projects, Caddy switches its upstream. Heaviest, only useful when the *whole stack* needs atomic swap. Overkill here.

### Recommendation: `docker-rollout` for prod, naive for staging

For prod web container: use `docker-rollout`. Caddy upstreams `web:8000`; the plugin scales to N+1, waits for healthcheck, then drains the old. Caddy's `lb_policy round_robin` and `health_uri /healthz` handle in-flight requests.

Critical: the web container needs a real healthcheck endpoint (`/healthz` returning 200 only after Django is ready *and* DB connection is alive).

For Postgres / Caddy / monitoring containers: a quick `docker compose up -d` is fine.

For staging: don't bother with rollout. `docker compose up -d --pull always web` is fine. 5 seconds of 502s on staging is a feature — it forces you to feel the deploy mechanism on a low-stakes target.

References:

- `docker-rollout`: https://github.com/Wowu/docker-rollout
- Caddy active health checks: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#active-health-checks

---

## 6. Secrets handling end to end

### The chain of custody

```
[Dev's GPG key, offline]
        |
        | encrypts
        v
[deploy/inventory/group_vars/{env}/vault.yml]   <-- in the repo, encrypted
        |
        | decrypted by ansible-vault during CI
        v
[GitHub Actions runner, ephemeral]
        |
        | renders to .env via template task, scp'd
        v
[/opt/freedomls/{prod,staging}/.env on the VPS, mode 0600, owner deploy]
        |
        | mounted as env_file in compose
        v
[web container env vars at runtime]
```

### Where each key lives

- **Ansible vault passphrase**: GitHub repo Secret `ANSIBLE_VAULT_PASS`. Also stored offline in the developer's password manager.
- **Per-environment app secrets** (`SECRET_KEY`, DB password, `SENTRY_DSN`, etc.): in `inventory/group_vars/{production,staging}/vault.yml`, encrypted with the vault passphrase.
- **SSH deploy key**: GitHub repo Secret `DEPLOY_SSH_KEY` (private), public half on the VPS.
- **GHCR pull credential on the host**: a long-lived PAT with `read:packages` scope, stored in `vault.yml`.
- **Cloudflare API token** (for Caddy DNS-01): in `vault.yml`, rendered into Caddy's env file.
- **Postgres backup encryption pubkey**: in repo, plaintext (it's a public key). Private half is offline only.

### Staging vs prod env files coexisting

Two completely separate `.env` files in two separate directories. Different DB, different `SECRET_KEY`, different `ALLOWED_HOSTS`, different `SENTRY_ENVIRONMENT`. The Compose project name (`COMPOSE_PROJECT_NAME=freedomls_prod` vs `freedomls_staging`) keeps container names, networks, volumes from colliding. The `.env` files NEVER share secrets.

### Rotation cadence

- App `SECRET_KEY`: every 12 months, or immediately on suspected compromise.
- DB password: every 12 months.
- SSH deploy key: every 12 months, or on laptop loss.
- GHCR pull PAT: every 90 days.
- Vault passphrase: only on suspected compromise.

References:

- `ansible-vault`: https://docs.ansible.com/ansible/latest/vault_guide/index.html
- Cloudflare API token scopes: https://developers.cloudflare.com/fundamentals/api/get-started/create-token/

---

## 7. Rollback

### Tag strategy

**Never deploy `:latest` to prod.** Production deploys use **immutable tags** so a rollback is just "deploy the previous tag."

Tag scheme:

- Every build pushes `ghcr.io/.../web:sha-<full-git-sha>` (immutable, content-addressed).
- Staging builds additionally push `:staging-<short-sha>` and `:staging-latest`.
- Prod releases (tag push) additionally push `:vX.Y.Z` and `:latest`.
- Compose file references the tag via `${IMAGE_TAG}` from `.env`. Ansible writes `IMAGE_TAG=v1.4.2` into prod's `.env` at deploy time.

### Last-known-good tracking

After every successful deploy + smoke test, the playbook writes the deployed tag to `/opt/freedomls/{stack}/last-known-good` on the host. Rollback = read that file, re-deploy with that tag, skip migrations.

Also push a moving `:last-known-good-prod` and `:last-known-good-staging` tag in GHCR.

### Rollback playbook

`playbooks/deploy.yml` accepts `-e image_tag=...` and `-e skip_migrations=true`. On failure, CI re-invokes it with `image_tag=$(cat last-known-good)`. Manual rollback from your laptop:

```
ansible-playbook -i deploy/inventory/hosts.yml playbooks/deploy.yml \
  --limit production -e image_tag=v1.4.1 -e skip_migrations=true
```

### Should we downgrade migrations?

**Default: no.** Forward-only migrations, paired with expand-contract. Reasons:

- Django's `migrate <app> <previous>` is risky for migrations that destroyed data.
- The whole point of expand-contract is that the old code can run against the new schema. So rollback of *code* is safe even with a newer schema.
- If you really need to undo a destructive schema change, restore from the pg_dump taken minutes before the deploy.

### Pre-deploy DB snapshot

The `deploy.yml` playbook includes a task right before `migrate`:

```yaml
- name: Snapshot DB pre-migration
  command: >
    docker compose -p {{ compose_project }} exec -T db
    pg_dump -Fc -U {{ db_user }} {{ db_name }}
    -f /backups/pre-deploy-{{ ansible_date_time.iso8601_basic_short }}.dump
```

Local snapshot only (not S3) — speed matters. Retention: 7 days, cleaned up by daily cron.

References:

- Docker image tag immutability: https://docs.docker.com/build/ci/github-actions/manage-tags-labels/
- Django migration rollback: https://docs.djangoproject.com/en/6.0/topics/migrations/#reversing-migrations

---

## 8. Branch -> environment mapping

### Recommendation: trunk-based + tags

```
feature branch -> PR -> merge to main         => deploys to staging
git tag v1.2.3 + push                         => deploys to production
```

Why this works for a solo dev:

- **`main` is always deployable.** PRs gate it (CI must pass). Every merge gets exercised on staging within minutes.
- **Tags are explicit.** You decide when to ship to prod by `git tag v1.2.3 && git push --tags`. No accidental prod deploys.
- **Tag is the version.** Image tag, Sentry release, changelog entry, all the same string.
- **Rollback is `git tag v1.2.3-rollback <previous-good-sha> && git push --tags`** — re-deploying is a normal tag push.

### Hotfix flow

1. Branch off the prod tag: `git checkout -b hotfix/login-bug v1.2.3`.
2. Fix, PR, merge to `main` (deploys to staging).
3. Tag a patch version: `git tag v1.2.4 && git push --tags`.
4. If `main` has unshippable changes since v1.2.3, branch from the tag, fix, tag `v1.2.3.1` from the hotfix branch.

### Branch protections

- `main`: require PR, require CI green, require linear history. No direct push.
- Tags `v*`: protected, only push from `main`.
- `production` GitHub Environment: required reviewer = self.

References:

- Trunk-based development: https://trunkbaseddevelopment.com/
- GitHub Environments: https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment#required-reviewers

---

## Cross-cutting opinions

1. **One Caddy, two upstreams.** Don't run a Caddy per stack. One Caddy reverse-proxies to `web` in each Compose project via shared external Docker network `caddy_net`.
2. **Postgres per stack.** Two separate Postgres containers, two separate data volumes. Sharing a Postgres between staging and prod is a footgun. (Note: the staging-prod-coexistence research recommends one Postgres with two databases — see that research for the tradeoff. Pick one; don't mix.)
3. **No Kubernetes.** Phase 1 is single-host Compose.
4. **Image build happens in CI, not on the host.** The VPS pulls finished images.
5. **Ansible runs from CI in normal flow, from laptop in emergencies.**
6. **Healthchecks everywhere or nowhere.** Half-implemented healthchecks are worse than none.
7. **Backups verified weekly, automatically.** Untested backups are not backups.
8. **The deploy playbook is idempotent.** Running it twice with the same `image_tag` is a no-op.

---

## Suggested order of implementation

1. **Week 1**: `Dockerfile` (multi-stage), local `docker-compose.yml` reproducing the stack, `/healthz` endpoint, GHA `ci.yml` (lint + test only).
2. **Week 2**: Ansible repo skeleton, `bootstrap.yml`, `common` + `docker` roles. Bootstrap a throwaway VPS, tear it down, redo it.
3. **Week 3**: `app_bootstrap` + `caddy_config` roles, manual deploy of staging Compose stack from your laptop, TLS working.
4. **Week 4**: GHA `deploy.yml`, `docker-rollout`, smoke tests, rollback path.
5. **Week 5**: Tag-driven prod deploy, `production` environment gate, prod stack on the same box.
6. **Week 6**: `backups` role, S3 lifecycle, weekly restore verification job.
7. **Week 7**: `monitoring` integration (Uptime Kuma off-box), Sentry release tagging, runbook.

## Open questions for the spec phase

- **Postgres location**: shared instance with two DBs (per staging-prod-coexistence research) or separate Postgres per stack (this doc's section "Cross-cutting opinions"). Pick one before writing the compose files.
- **CI runner**: GitHub-hosted runners are fine; self-hosted on the VPS would couple build and prod (don't).
- **Healthcheck design**: what exactly does `/healthz` exercise? DB ping yes, Redis no (none yet), R2 reachability no (out of band).
- **First-deploy bootstrap**: do we need a "createsuperuser" task in the deploy playbook, or a one-shot Ansible task?
