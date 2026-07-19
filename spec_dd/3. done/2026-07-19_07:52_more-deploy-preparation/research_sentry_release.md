# Research: surfacing a blank SENTRY_RELEASE + build-time injection

Scope: two research questions for the `more-deploy-preparation` idea — (1) how FLS should make a
blank `SENTRY_RELEASE` (with `SENTRY_DSN` set) loud without breaking a working deploy, and (2) the
Docker build-time pattern for baking `SENTRY_RELEASE` into the image, sourced from CI's git SHA.
Also covers whether V1 should reach for `sentry-cli` release finalize/commit-association, and
cross-process consistency gotchas.

---

## 1. Surfacing a blank release when `SENTRY_DSN` is set

### FLS's existing conventions (the load-bearing prior art)

FLS already has an established, repo-wide pattern for exactly this class of problem —
"config is internally inconsistent, should be visible on every boot, must not crash a working
deploy" — and it is the **Django system-check framework**, not a runtime raise:

- `freedom_ls/course_access/checks.py` `check_preview_overrides_disabled_in_production` (W001) is
  the closest structural analog: a **conditional** Warning — "setting X is on when condition Y
  holds" — registered with no `deploy=True`, so it runs on every `manage.py check` /
  `migrate` / `runserver` / `test`, not just `check --deploy`.
- `freedom_ls/base/app_settings.py`'s `AppSettings`/`Setting`/`required_settings_errors()`
  machinery is FLS's house pattern for **unconditionally**-required settings (`required=True` →
  `Error` via `required_settings_errors()`), used by `course_access`'s own E001. It does **not**
  fit this case as-is: "`SENTRY_RELEASE` required *only if* `SENTRY_DSN` is set" is a conditional
  requirement, so this needs a bespoke check function shaped like `course_access`'s W001, not the
  generic `required_settings_errors()` helper (which assumes an unconditional `Error`).
- `freedom_ls/deployment/config.py`'s `AppSettings.__getattr__` already **strips whitespace and
  normalizes `""` to `None`** (`value not in (None, "")`) before returning, so `config.SENTRY_RELEASE`
  is already `None` for both an unset and a blank (`SENTRY_RELEASE=`) env var — the check does not
  need its own blank-string normalization, it can just test `not config.SENTRY_RELEASE`.
  (`/home/sheena/workspace/lms/freedom-ls-worktrees/more-deploy-preparation/freedom_ls/base/app_settings.py:36-39`)

There is **no existing checks.py under `freedom_ls/deployment/`** yet (glob of
`freedom_ls/deployment/**` confirms) — `apps.py`'s `ready()` currently only calls `init_sentry()`.
A new `freedom_ls/deployment/checks.py`, wired the same way `course_access` wires its `ready()`,
is the natural home.

### Comparing the three options

| Option | Runs when | Blocks a working deploy? | Fits "see it quickly, don't break Sentry" |
|---|---|---|---|
| **Django system check** (`Warning`, no `deploy=True`) | Every `manage.py check`/`migrate`/`runserver`/`test` — including the already-established one-off `manage.py migrate` deploy step (per `research_deployment_scaffolding_references.md`'s "no migrate in entrypoint" pattern) and the existing CI job `django-check-deploy` (`.github/workflows/security.yml:85-86`, `check --deploy --fail-level WARNING`) | **No** — `Warning`-level messages print but do not stop `migrate`/`runserver` (confirmed: Django docs — Errors "prevent Django commands... from running at all"; Warnings do not) | **Best fit.** Self-gating (only fires when `SENTRY_DSN` is set, mirroring `course_access`'s `DEBUG=False` guard), visible at the exact moment a real deploy applies migrations with real prod env vars, silenceable per-deployment via `SILENCED_SYSTEM_CHECKS` |
| **Logged warning inside `init_sentry()`** | Every process boot (web + `db_worker`), always | No — pure logging | Works, but weaker: only visible in log aggregation/stdout, not in a CI/deploy-pipeline exit code or `manage.py check` output; and `CLAUDE.md`/project convention is "don't add logging unless asked" — this idea didn't ask for logging, it asked to "see the problem quickly," which the check framework already gives without a new logging call |
| **Fail-fast (`raise ImproperlyConfigured`)**, matching `freedom_ls/deployment/settings_defaults.py`'s `require_secret_key()` | At settings-module import / `AppConfig.ready()`, before the process can serve a single request | **Yes** — crash-loops the container | **Wrong altitude.** `require_secret_key()`'s crash-loop is justified because a blank `SECRET_KEY` silently disables the session/CSRF security boundary — the app is *broken*, not just less observable. A blank `SENTRY_RELEASE` degrades one feature of an already-optional, already-degradable third-party integration (Sentry works fine without it; you just lose release-based regression grouping). Raising over a missing telemetry tag would take down a deploy for a strictly less severe problem than the one `require_secret_key()` guards — disproportionate, and directly against this idea's explicit non-scope-creep, "efficiency and ease" framing (`idea.md`) |

### Recommendation

Add a **Django system check**, `Warning`-level, in `freedom_ls/deployment/checks.py`, registered
in `freedom_ls/deployment/apps.py`'s `ready()` (same shape as `course_access`'s wiring):

- **Do not** tag `deploy=True`. Per the in-repo research already done for this exact question
  (`spec_dd/2. in progress/fls-test-portability-part-2/research_django_system_checks.md` §3):
  `deploy=True` checks are excluded from the default run and only fire under
  `manage.py check --deploy` — but the actual value here comes from firing automatically during
  the deploy pipeline's one-off `manage.py migrate` step (which always runs the default check set,
  regardless of `--deploy`), not from a separate audit invocation. A default (untagged, or
  `Tags.compatibility`) registration also means the existing CI `django-check-deploy` job
  (`check --deploy --fail-level WARNING`) picks it up for free — though that CI job's env doesn't
  set `SENTRY_DSN`, so it stays silent there (no false positive); it earns its keep on a *real*
  deploy env's `migrate` invocation.
- **`Warning`, not `Error`.** Consistent with `course_access.W001`'s precedent for
  "environment-conditional misconfiguration that doesn't break the running app."
- **Condition:** `config.SENTRY_DSN` is set (truthy) **and** `config.SENTRY_RELEASE` is falsy.
  Mirrors `course_access.W001`'s `if settings.DEBUG: return []` early-exit shape.
- **ID:** `freedom_ls_deployment.W001` (app label `freedom_ls_deployment` — verify against
  `freedom_ls/deployment/apps.py`'s actual `AppConfig.label`/`name`; it currently has no explicit
  `label` attribute so Django defaults the label to `deployment` — the plan/spec phase should
  decide whether to add an explicit `label = "freedom_ls_deployment"` for ID-namespacing
  consistency with `course_access`/`student_interface`, per the in-repo checks research §2).
- Document the ID in `SILENCED_SYSTEM_CHECKS` guidance (already the pattern
  `docs/deployment-security-checklist.md` and the checks research doc both reference) so a
  deployment that deliberately doesn't want release tracking can silence it explicitly rather
  than the check being a permanent unfixable nag.
- **Skip the separate logged warning in `init_sentry()`.** The system check already delivers "see
  it quickly" at the deploy-pipeline checkpoint; adding a second, differently-mechanised warning
  (an ad-hoc `logger.warning(...)` nobody asked for) is duplicate signal for the same fact and
  against the "don't add logging unless asked" convention. Flag as a documented **non-goal for V1**,
  not a rejected idea — if operators later want a boot-time stdout signal for `docker compose up`
  without an explicit `check`/`migrate` step in front of it, that is an easy, well-scoped follow-up.

Sources: Django docs — System check framework (`Tags`, `CheckMessage`, `Warning`/`Error` blocking
semantics): https://docs.djangoproject.com/en/6.0/topics/checks/ ·
`SILENCED_SYSTEM_CHECKS`: https://docs.djangoproject.com/en/6.0/ref/settings/#std-setting-SILENCED_SYSTEM_CHECKS
· in-repo precedent: `freedom_ls/course_access/checks.py`, `freedom_ls/base/app_settings.py`,
`spec_dd/2. in progress/fls-test-portability-part-2/research_django_system_checks.md` · CI
precedent: `.github/workflows/security.yml:61-86` · deploy-pipeline precedent (one-off `migrate`,
not in entrypoint): `spec_dd/2. in progress/support-concrete-project-deployment/research_deployment_scaffolding_references.md`
("One-off migrations vs migrate-on-entrypoint" section).

---

## 2. Build-time release injection in Docker

### Pattern

Standard, low-risk shape (this is the idiomatic pattern across every current Docker/Sentry
reference found — nothing bespoke needed):

```dockerfile
# in the FINAL (python-run) stage only — SENTRY_RELEASE is a runtime env value baked at
# build time, it is not needed by any earlier build-only stage (uv sync, collectstatic, etc.)
ARG SENTRY_RELEASE
ENV SENTRY_RELEASE=${SENTRY_RELEASE}
```

```yaml
# GitHub Actions, docker/build-push-action
- uses: docker/build-push-action@v6
  with:
    push: true
    tags: ${{ steps.meta.outputs.tags }}
    build-args: |
      SENTRY_RELEASE=${{ github.sha }}
```

Gotcha worth calling out for the plan/spec phase: **`ARG` must be (re-)declared inside the stage
that consumes it.** A Dockerfile `ARG` declared before the first `FROM` is only visible to `FROM`
lines; an `ARG` used *inside* a build stage (including one referenced by a later `ENV`) must be
declared again with `ARG NAME` inside that stage, even if an identically-named `ARG` already
exists earlier in the file. Declare it in the final runtime stage, not the `python-build`/`node`
build-only stages (those don't need it — matches the existing "each stage only has what it needs"
discipline already established in `research_deployment_scaffolding_references.md`).

### Value convention: raw commit SHA vs `name@version+sha`

Sentry's own docs give two supported shapes, and either is valid: **Semantic/Calendar Versioning**
(`package@version`, optionally `+build`, e.g. `my.project.name@2.3.12+1234`) or the **VCS commit
SHA** directly — Sentry's naming-releases doc explicitly calls out "the identifying hash, such as
the commit SHA" as an accepted, common convention, and `sentry-cli`/the Python SDK's own
auto-detection will fall back to the git SHA when nothing else is configured.
(https://docs.sentry.io/product/releases/naming-releases/,
https://docs.sentry.io/platforms/python/configuration/releases/)

**Recommendation for V1: use the raw full git SHA** (`${{ github.sha }}`, 40 hex chars), not a
`name@version` scheme:

- FLS/the concrete template doesn't currently version-tag releases with semver — inventing one
  just to satisfy Sentry's `package@version` convention would be new process the idea's own
  "efficiency and ease, don't scope creep" framing argues against.
  A plain SHA needs no additional bookkeeping and is exactly what
  `research_deployment_scaffolding_references.md` already established as "the deploy/rollback
  unit" for the GHCR image itself — reusing the same value for Sentry keeps one source of truth.
- Restrictions to respect either way: release names cannot contain newlines, tabs, `/`, `\`, and
  cannot be entirely `.`, `..`, or whitespace, and are capped at 200 chars — a raw git SHA trivially
  satisfies all of these. (https://docs.sentry.io/product/releases/naming-releases/)

**Should it match the GHCR image tag?** Conceptually yes — they should be **derived from the same
commit**, so an operator can go from "which release is throwing this error in Sentry" straight to
"which image is that" without a lookup table. But watch a **byte-identity gotcha**:
`docker/metadata-action`'s `type=sha` tag defaults to a **short, prefixed** form —
`sha-<7-char-short-sha>` (`prefix=sha-`, `format=short` by default) — not the full 40-char SHA
(https://github.com/docker/metadata-action). If the GHCR tag is left at that default and
`SENTRY_RELEASE` is set to the full `github.sha`, the two strings will not be byte-identical (`sha-a1b2c3d`
vs `a1b2c3d4e5f6...`), even though both trace to the same commit. Two ways to resolve, either
acceptable for V1 — pick one and record it in the CI workflow / `third-party-services.md`:
1. **Loose correspondence (recommended, less config):** keep the GHCR tag at its metadata-action
   default (`sha-<short>`) and set `SENTRY_RELEASE` to the full `github.sha` independently. They
   aren't string-identical, but both are one `git show <commit>` away from each other, and this is
   the value Sentry itself will recognize as a genuine commit hash for any future commit-association
   work (§3). No metadata-action config change needed.
2. **Exact match:** configure `docker/metadata-action` with `type=sha,format=long,prefix=` (or
   simply tag the image with `${{ github.sha }}` directly via `type=raw,value=${{ github.sha }}`)
   so the GHCR tag and `SENTRY_RELEASE` are byte-identical strings.

Since this is a documentation/config-convention decision, not an architectural one, defer the final
choice to the plan/spec phase rather than pre-deciding it here — flag both options.

Sources: Sentry — Naming Releases: https://docs.sentry.io/product/releases/naming-releases/ ·
Sentry Python SDK — Releases config: https://docs.sentry.io/platforms/python/configuration/releases/
· `docker/metadata-action` (`type=sha` default `prefix=sha-`, `format=short`):
https://github.com/docker/metadata-action · existing in-repo GHCR CI research:
`spec_dd/2. in progress/support-concrete-project-deployment/research_deployment_scaffolding_references.md`
("GHCR SHA-tagged build-and-push CI" section).

Note: baking `SENTRY_RELEASE` as an `ENV` means it's visible in `docker inspect`/`docker history`
of the pushed image — this is fine, it's a git SHA, not a secret (contrast with `SENTRY_AUTH_TOKEN`,
which is a real secret and must never be baked as an `ENV`/`ARG` in a pushed image layer — only
consumed transiently as a CI job secret if/when `sentry-cli`/`action-release` is adopted, §3).

---

## 3. Should V1 also use `sentry-cli` to associate/finalize the release?

**No — not for V1.** What `sentry-cli releases new/set-commits/finalize` and the
`getsentry/action-release` GitHub Action add, beyond simply passing `release=` to `sentry_sdk.init()`:

- **Explicit release object creation + `finalize`** (records a release start/end timestamp on
  Sentry's release timeline) — cosmetic; Sentry already auto-creates a release record the first
  time an event carrying a new `release` tag arrives, which is all problem statement #1 needs
  (events tagged with a release, regressions tied to a deploy).
- **`set-commits` / commit association** — enables the "suspect commits"/"resolved in next release"
  workflow the idea's problem statement mentions, but requires (a) a Sentry↔GitHub repository
  integration configured in the Sentry org, and (b) a `SENTRY_AUTH_TOKEN` org-auth-token wired into
  CI as a real secret (distinct from the DSN). That's new infra surface (a secret, an integration
  to configure once per Sentry org) for a nice-to-have on top of what the release *tag* already
  buys.
- **Source-map upload** — irrelevant to FLS: this matters for minified JS stack-trace symbolication,
  and FLS is a server-rendered Django+HTMX app with no bundled/minified JS build step needing source
  maps.
- **Deploy markers** — a visual annotation on Sentry's release timeline; purely cosmetic/observability
  polish, no functional gain over the release tag alone.

Given the idea's explicit framing ("Dont go overboard... The goal is not to be fancy or to scope
creep, we want efficiency and ease"): **setting the `release` string via `sentry_sdk.init()` (already
implemented) fed by a build-time-baked `SENTRY_RELEASE` env var is sufficient for V1.** It already
solves the stated problem — "regressions can't be tied to a deploy" — because every event from that
image carries the same release tag, letting Sentry's UI group/filter/regress by release without any
`sentry-cli` step. `sentry-cli`/`action-release` (commit association specifically) should be
**documented as a future step**, not implemented now — a one- or two-line note in
`spec_dd/2. in progress/support-concrete-project-deployment/third-party-services.md`'s §3 Sentry
section (or wherever the eventual spec lands) is enough; do not add a `SENTRY_AUTH_TOKEN` var,
CI step, or Sentry-GitHub-integration setup instructions in this V1.

Sources: `getsentry/action-release` (auth-token requirement, what it automates):
https://github.com/getsentry/action-release · Sentry — GitHub Actions release automation:
https://docs.sentry.io/product/releases/setup/release-automation/github-actions/ · Sentry —
Associate Commits: https://docs.sentry.io/product/releases/associate-commits/ · Sentry CLI
Releases reference: https://docs.sentry.io/cli/releases/

---

## 4. Gotchas

- **Must be identical across all processes of one deploy (web + `db_worker`).** Both the Gunicorn
  web process and the `python manage.py db_worker` process go through the same
  `DeploymentAppConfig.ready() → init_sentry()` path (`freedom_ls/deployment/apps.py`), and both
  read `config.SENTRY_RELEASE` from the process environment. **This is exactly why baking the value
  into the built image at build time (this idea's premise) is strictly better than a per-service
  runtime env var**: if `web` and `db_worker` are two Compose services each configuring
  `environment:`/`env_file:` independently, nothing stops one of them drifting (typo, stale `.env`
  copy, forgotten update) — mismatched releases mean Sentry sees the same deploy's events split
  across two release tags, breaking exactly the "tie a regression to a deploy" grouping this idea
  exists to fix. Since both `web` and `db_worker` in FLS's Compose topology run **the same image**
  (per `research_deployment_scaffolding_references.md`'s stack), a build-time-baked `ENV` is
  automatically identical for every container started from that image — no per-service
  configuration to keep in sync, no drift possible short of running containers from two different
  image builds side by side (already a bigger problem than release tagging).
- **Per-restart / rebuild consistency.** Because the value is a Docker image `ENV` (baked at build
  time), a plain `docker compose restart` (same image, no rebuild) is always correct — the release
  string can't silently drift on a restart the way a runtime-computed value (e.g., a start script
  shelling out to `git rev-parse HEAD`) could if the container has no `.git` directory or is
  restarted against a stale checkout. This is a further argument for build-time baking over any
  runtime-computed alternative, beyond just "it belongs to the image" (the idea's own framing).
- **Consequences of a wrong/missing release value are contained, not catastrophic** — reinforces
  the Warning-not-Error call in §1: a wrong or blank release only degrades Sentry's release-based
  features (regression-to-deploy attribution, "resolved in next release," future suspect-commit
  association); it does not stop Sentry from capturing and grouping errors by fingerprint, and does
  not affect any non-Sentry functionality. There is no scenario where a bad `SENTRY_RELEASE` value
  should be allowed to fail a deploy outright.
- **`AppSettings` already normalizes blank-vs-unset**, so `config.SENTRY_RELEASE` is `None` for both
  a genuinely unset env var and an explicitly blank one (`SENTRY_RELEASE=`) — the new check (§1)
  can test plain falsiness and does not need its own stripping/blank-check logic.
  (`freedom_ls/base/app_settings.py:36-39`)
- **`SENTRY_ENVIRONMENT` has an analogous "must be set whenever `SENTRY_DSN` is set" comment already
  in `.env.example`** (`"the SDK otherwise silently tags events \"production\""`,
  `.env.example:57-58`) but is **out of scope** for this idea, which is specifically framed around
  `SENTRY_RELEASE` — flagging only so the eventual spec/plan phase doesn't accidentally conflate the
  two or silently expand scope to also add an `ENVIRONMENT` check without that being asked for.

---

status: ok
