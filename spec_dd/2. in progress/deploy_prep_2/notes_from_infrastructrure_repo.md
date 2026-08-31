# Freedom-LS: work to meet the contract

Gaps between `preludetech/Freedom-LS` and `docs/app_repo_contract/`. Blockers first. Clause IDs
point at the rule and its reasoning; this file records only the gap and the fix.

Freedom-LS is never deployed. `First-Class-Training/First-Class-LMS` carries it at
`submodules/Freedom-LS`, installs `freedom_ls` as an editable path dependency, and resolves its
templates from that tree at runtime (`IMAGE-14`). So everything here reaches
`first-class-ls-staging` and `first-class-ls-prod` through that image, and no item is done until
it covers both. Nothing here reaches the website box, which carries no `freedom_ls`.

Items whose fix belongs in the LMS repo rather than this one are in
[`first_class_ls.md`](first_class_ls.md). Where the two touch, both files say so.

Severity: **Blocker** breaks a real deploy or ships something that must not be in the image.
**High** deploys and is insecure, misleading, or operationally wrong. **Medium** works and needs
tidying.

---

## Already correct, and worth not undoing

Recorded because each of these is a thing an app repo usually gets wrong, and a later change
could quietly take one back.

- No `Dockerfile`, no `docker-compose.yml`, no `Caddyfile`, no entrypoint. The image, the stack
  and the edge belong elsewhere (`EDGE-5`, `LS-02`).
- `django-tasks-db` pinned exactly, with a test asserting the pin. The task backend is Postgres
  and there is no broker (`CI-15`).
- `fls_run_worker` consumes every queue rather than `default`, which is `COMPOSE-8`'s first
  binding property on `run_worker`.
- `fls_run_housekeeping` prunes with `--queue-name=*` and clears sessions, keeps one sweep's
  failure from stopping the other, and separates a sweep failure from a finding about another
  container. That is most of `COMPOSE-8`.
- `setup_initial_prod_data` generates the administrator's password, prints it once, and never
  resets one that exists (`CI-18`).
- Six per-bucket storage purposes with no shared fallback, and `E002` erroring on any alias that
  fell to local disk (`ENV-10`, `CI-17`).

---

## Blockers

### FLS-01. Test dependencies ship in the runtime image
`pyproject.toml`, `[project] dependencies`. Clause IMAGE-12.

`pytest-env` and `pytest-playwright` are runtime dependencies, not dev ones. `pytest-playwright`
pulls in `playwright`, whose wheel carries a browser driver. Every LS image built from this
submodule installs all of it into the runtime stage.

Fix: move both to the dev group. Then confirm against the built image rather than the file, per
`IMAGE-12`: `docker run --rm <image> pip list`.

### FLS-02. `/tmp/lms_templates` is the first template directory
`config/settings_base.py`, `TEMPLATES[0]["DIRS"]`.

`/tmp` is world-writable and the image runs as an unprivileged user (`IMAGE-2`), so anything in
the container that can write a file can put a template on the path Django searches first, ahead
of every app directory, with the cached loader holding it afterwards. The worker and housekeeping
heartbeats live in the same directory (`COMPOSE-8`), so it is a directory the app already writes
to by design.

The path does not exist, so the entry does nothing today except carry that.

Fix: delete the entry, or replace it with a directory inside the image that the runtime user
cannot write.

### FLS-03. The template manifest bootstraps a Site at `127.0.0.1:8000`
`claude_plugins/fls-dev/resources/template_repo_manifest.md`, "apps/project_setup". Clause CI-18.

The manifest is what a concrete project is built from, and it tells that project to ship
`apps/project_setup/management/commands/setup_initial_data.py`, creating the initial `Site` with
domain `127.0.0.1:8000` and a verified admin superuser.

The LS sets no `SITE_ID`, so `get_current_site(request)` resolves by request host. A `Site` row at
`127.0.0.1:8000` matches no request a stack receives, which is 500 on every login, signup,
password-reset and logout page, and no verification mail. That is `LS-08f` in
[`first_class_ls.md`](first_class_ls.md), and this manifest is where it comes from.

`setup_initial_prod_data` in this repo already does the job properly, taking the domain from
`HOST_DOMAIN`.

Fix: point the manifest at `setup_initial_prod_data <admin-email>` and drop the `project_setup`
bootstrap from the prescribed tree. Two commands that create the same two rows, one of them with
a loopback domain baked in, is one too many.

---

## High

### FLS-04. `.env.example` models several things `ENV-5` and `ENV-6` forbid
`.env.example`. Clauses ENV-2, ENV-5, ENV-6, ENV-10.

This file is not the LS's authoritative key list. `ENV-2` is explicit that a vendored
`submodules/Freedom-LS/.env.example` is a different repo's list. But it is what the LS's list was
derived from, and four of its habits carried across or will:

- `SENTRY_RELEASE=` with an empty value. `env_file` beats image `ENV`, and an empty line counts,
  so that one line blanks the release baked in at build and Sentry events stop mapping to a
  deploy. `IMAGE-9` and `ENV-5` both exist to stop exactly this line.
- `HOST_DOMAIN="staging.freedomlearningsystem.org"`, quoted. `roles/app_env` writes values
  verbatim and compose strips no quotes, so quotes become part of the value (`ENV-6`).
- Trailing `# secret` and `# config` markers on value lines. Fine as documentation, and a live
  trap the moment somebody transcribes a line into `group_vars`. The LS repo has the same one as
  `LS-16`.
- `AWS_STORAGE_BUCKET_NAME` and `AWS_S3_CUSTOM_DOMAIN` are listed. Both are deliberately absent
  from this fleet, and why is `ENV-10`. Listed here they read as configuration somebody forgot to
  fill in.

Fix: remove the `SENTRY_RELEASE` line, unquote the values, and add a header saying values are
literal and the markers must never be carried across. The two absent keys can stay if the file
says in one line why they are blank, since this repo also serves deployments that are not this
fleet.

### FLS-05. `get_client_ip` falls back to `REMOTE_ADDR`
`freedom_ls/accounts/utils.py`. Clauses EDGE-11, EDGE-12.

When the named header is absent, or holds anything that is not one valid address, the function
returns `REMOTE_ADDR`. Behind this edge that is the Caddy container's own address on the `edge`
network: the same value for every visitor on the box, and a different value after the container
is recreated.

The two consumers then disagree. allauth, handed a header name, raises `PermissionDenied` rather
than falling back, so a missing header is loud. django-axes goes through this callable, so it
gets the fallback and locks quietly on an address every visitor shares. `EDGE-12` calls that
outcome the limit becoming the attack.

The fallback is right for a deployment with no proxy in front, which this repo also serves. It is
wrong the moment a header has been named.

Fix: fall back to `REMOTE_ADDR` only when no header is configured. With one named and absent,
raise or return nothing, so the failure is as loud for axes as it already is for allauth.

### FLS-06. Production logging writes rotating files to disk
`config/settings_prod.py`, `freedom_ls/deployment/settings_defaults.py`. Clause COMPOSE-9.

`build_logging_config(log_dir=BASE_DIR / "logs")` adds three `RotatingFileHandler`s. The comment
beside it says the file handlers are temporary, pending container-level log size caps, and that
dropping them earlier would move the disk-fill risk to an uncapped container log rather than
removing it.

That condition is now met. `roles/docker` caps `json-file` at `max-size=10m`, `max-file=3`
daemon-wide, and `COMPOSE-9` sets the same cap per service so the stack is correct on a host this
repo has not configured. Writing files as well puts a second copy of every line inside the
container's writable layer, where nothing rotates it against the disk the two Postgres data
directories are on.

This module is not what the LS deploys, so the binding fix is the LMS calling
`build_logging_config()` with no `log_dir`. The comment here should stop describing the condition
as unmet.

Fix: drop `log_dir` from this repo's own production settings, and rewrite the comment to say
stdout only, capped by the log driver.

### FLS-07. `docs/product/deployment.md` describes a different fleet
`docs/product/deployment.md`.

Read end to end it contradicts this repo in six places:

| It says | This fleet | Clause |
| --- | --- | --- |
| Caddy acquiring TLS automatically via Let's Encrypt | Cloudflare Origin CA from the vault. Every record is proxied and Full (strict), so an HTTP-01 challenge cannot complete | `EDGE-6` |
| The template repo owns the Caddy and compose scaffolding | `roles/edge` renders the whole proxy from the inventory, and an app repo ships nothing to `/opt/apps/edge/` | `EDGE-5` |
| `pg_dump` on cron, encrypted to Backblaze B2, "not automated" | `roles/backups`: `age`-encrypted `pg_dump -Fc` to Cloudflare R2 on a systemd timer, with retention and a recurring off-box restore drill | "Do not build these" |
| 4 vCPU, 8 GB VPS, gunicorn with 5 workers | `vc2-2c-4gb` and `vc2-1c-2gb`, `WEB_CONCURRENCY` 3 and 2, with per-service memory limits | `COMPOSE-10` |
| Cloudflare in front is "planned, not yet in place"; Ansible provisioning "not yet built" | Both are in place, and provisioning is this repo | `fleet.md` |
| The first-run bootstrap "belongs in the deploy sequence rather than in a one-time manual runbook" | The operator runs it by hand, once per stack, because it prints a password and an Actions log keeps whatever is printed into it | `CI-18` |

The last row is the one to fix first, because it is advice rather than description and following
it puts a generated administrator password in a CI log.

This is also where the scope question lands. Freedom-LS is a library with more than one
downstream project. A target architecture, a VPS price list, POPIA residency argument and scale
estimates are a deployment's, and each of those now has a repo that owns it. Every line in this
document that says "not yet built" is a status line about somebody else's work.

Fix: cut it back to what the application requires of any host, which is the "Application-Level
Capabilities" section and little else, and link a First Class deployment at
`docs/app_repo_contract/` instead of restating a stack.

### FLS-08. The security checklist asks for things this fleet answers differently
`docs/deployment-security-checklist.md`.

Three items read as failures here, and only one is:

- Section 2, "a dedicated database user (not the superuser)". `COMPOSE-6` requires
  `POSTGRES_USER` equal to `DB_USER`, which makes `DB_USER` the cluster superuser, because the
  official image runs `initdb --username="$POSTGRES_USER"`. `roles/backups` authenticates as that
  role over the container's local socket, which is what keeps the password off a command line
  `ps` would show. A separate application role would break the backup, which is the thing the
  checklist most wants working.
- Section 5, SSH restricted to known admin IPs or a VPN. This fleet leaves SSH open behind
  key-only auth and `fail2ban`, deliberately, because an operator's address is not fixed.
- Section 7, centralised logging to ELK, CloudWatch or Datadog. Errors go to Sentry and container
  logs are capped `json-file`. There is no log aggregator and none is planned.

Fix: mark these three as depending on the topology, and say what a same-host containerised
Postgres and a two-box fleet do instead. A checklist a correct deployment fails teaches operators
to skip lines.

---

## Medium

| ID | Gap | Fix | Clause |
| --- | --- | --- | --- |
| FLS-09 | `notify-downstream.yml` dispatches `fls-updated` to `first_class_ls` under `github.repository_owner`. The LS repo is `First-Class-Training/First-Class-LMS`, a different name under a different owner, so the dispatch cannot land | Name the repository in full, owner included | naming |
| FLS-10 | `danger_clear_all_course_progress` is in `freedom_ls.learner_progress`, which is installed in production, and has no `DEBUG` guard and no confirmation prompt. `danger_content_delete` has a prompt; this one does not | Add the prompt, or refuse to run when `DEBUG` is false | none |
| FLS-11 | `fls-content-plugin/` holds nothing but stale `__pycache__`. The live code is `claude_plugins/fls-content/validate/` | Delete the directory | none |
| FLS-12 | `docs/install.md` is zero bytes, and `docs/how tos/incorporate into another project.md`, which the template manifest links, does not exist | Write them or remove the links | none |

---

## Open decision, not a gap

### FLS-14. `AXES_LOCKOUT_PARAMETERS` carries a bare `"username"` rule
`config/settings_base.py`. Clause EDGE-12.

`EDGE-12` mandates `[["ip_address", "username"]]` and argues the flat entry against: a
username-only rule means a large enough set of addresses can lock a chosen learner out of their
own account, and axes sums failures across every attempt row sharing that username.

This repo sets both, and the comment gives a reason `EDGE-12` does not answer. allauth's
`login_failed` rate limit is the layer above the lockout, and it wraps allauth's own login view
and not `/admin/login/`. Without the flat rule, a spray that rotates source addresses against one
administrator account is capped by nothing at all.

Both readings are right about their own case and they point opposite ways. Neither states the
third option: put `/admin/` behind a Cloudflare access rule, which removes the exposure the flat
rule covers and lets `EDGE-12` stand. That would be an edge change in this repo, in the same
place `EDGE-8` already treats staging differently from prod, and `first_class_ls.md` already
records `/admin/` reachable from the public internet with no allowlist and no 2FA.

Recorded for a decision. Change neither side until it is made.
