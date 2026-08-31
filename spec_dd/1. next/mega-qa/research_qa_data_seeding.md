# Research: what a single `setup_qa_data` has to do, and what stands in its way

Scope: this is codebase research only. No implementation plan — see `/sdd:spec_from_idea` for that.

---

## 1. Inventory of the existing seeding machinery

**35** `qa_*` management commands live in `freedom_ls/qa_helpers/management/commands/` (not ~45 — an
overcount in the idea brief). They fall into clear groups by scenario, not by app:

- **Users / login-ready personas** — `qa_create_header_bar_users`, `qa_create_password_reset_learner`,
  `qa_create_rich_dashboard_learner`, `qa_create_course_player_learner`,
  `qa_create_incomplete_registration_learner`. Each builds one or two named users who can log in and
  land on a specific surface.
- **Cohorts and membership shapes** — `qa_create_empty_learner_cohort` (registrations, no members),
  `qa_create_large_cohort` (row-pagination volume), `qa_create_cohort_progress`,
  `qa_create_educator_modal_target`.
- **Course-progress reporting/pagination matrices** — `qa_create_report_cohort`,
  `qa_create_report_course`, `qa_create_report_fixtures`, `qa_create_report_brand_organisations`,
  `qa_create_column_pagination_scenario`, `qa_create_paginated_progress_matrix`,
  `qa_add_course_items_for_pagination`. The largest and most inter-dependent group — several of these
  exist purely to make the cohort progress report's two independent paginators (`COLUMN_PAGE_SIZE`,
  `LEARNER_PAGE_SIZE`) both fire at once.
- **Organisations** — `qa_create_organisations`, `qa_create_organisation_scenarios`,
  `qa_register_org_course`.
- **Forms / quizzes / scoring** — `qa_create_form_question_types`, `qa_create_checkbox_scoring_quiz`,
  `qa_create_multiselect_quiz_scoring`, `qa_create_legacy_checkbox_score`, `qa_create_free_text_survey`,
  `qa_create_site_scoping_form`, `qa_create_quiz_progression_block`, `qa_complete_form`.
- **Deadlines** — `qa_create_soft_deadline`, `qa_create_deadline_overrides`,
  `qa_create_learner_deadlines`.
- **Course access / visibility / detail-page variants** — `qa_create_course_visibility`,
  `qa_create_course_access_types`, `qa_create_course_detail_variants`,
  `qa_create_application_docs_scenario`.
- **Progress reset / repair (destructive or corrective)** — `qa_reset_learner_progress`,
  `qa_repair_form_engine_content_types` (see §3).

**One-off past-spec scaffolding vs. general-purpose:** most commands are named after the feature they
were built to prove (`qa_create_course_detail_variants.py:1`'s docstring literally says *"for the
'Override course access & details page' feature"*; `qa_create_legacy_checkbox_score.py` says *"QA 12.6
needs…"*). A handful are broadly reusable across any whole-system plan — `qa_create_organisations`,
`qa_create_large_cohort`, `qa_create_course_visibility`, `qa_create_password_reset_learner` — but the
majority encode one specific historical scenario's fixture shape, not a general building block.

**The commands are not a coherent CLI.** They disagree on how the site is passed — positional
`SITE_NAME` (required or defaulting to `DemoDev`) on some, a `--site-name` option (no positional
accepted) on others, and on required-option combinations that differ command to command
(`.claude/agent-memory/fls-dev-qa-data-helper/reference_qa_command_site_arg_styles.md` documents this
in detail, including commands that exit 2 on the "obvious" invocation). A `setup_qa_data` that shells
out to today's commands inherits this inconsistency; one that reimplements their logic in-process does
not have to.

---

## 2. Content loading

**`demo_content/` is shipped in the repo** — it is not in `.gitignore` (`.gitignore`) and it is only
excluded from the *Python package* built by setuptools
(`pyproject.toml`'s `[tool.setuptools.packages.find]` `exclude`), which is a packaging concern, not a
repo-presence one. It ships as five course directories:
`functionality_demo_course_parts`, `functionality_demo_end_with_quiz`,
`functionality_demo_end_with_topic`, `functionality_demo_content_widgets`,
`functionality_demo_standard_markdown` — roughly 22 Topics, 4 Forms (with `FormPage` / `FormQuestion` /
`FormContent` children), a handful of `CoursePart`s, and a dozen image/PDF files.

**Loading is `content_save`, filesystem-and-DB, single-process.** The command
(`freedom_ls/content_engine/management/commands/content_save.py`) validates then saves inside one
`@transaction.atomic` (`content_save.py:493`), reading files off the local disk and doing
`update_or_create` per item. It runs **server-side**, so filesystem access is not a staging blocker —
`demo_content/` is part of the deployed checkout, not something the remote QA agent needs to reach over
HTTP. Volume is small (dozens of DB rows), so a single course loads in low single digits of seconds;
today's workflow invokes `content_save` once **per course directory**
(`.claude/agent-memory/fls-dev-qa-data-helper/reference_demo_content_loader.md`), so loading all five
pays Django's process-startup cost five times over, not the content-parsing cost.

**`demo_content/` does not exercise every content type.** It has no `Activity` content at all — this
matches the domain glossary's own note that `Activity` (`content_engine/models.py:159`) is "not
currently used by FLS courses." Within `FormQuestion`, the shipped content only demonstrates
`multiple_choice` (see e.g. `demo_content/functionality_demo_end_with_quiz/5. quiz/1. page.yaml`); the
`short_text`/`long_text` free-text case and the checkbox/multi-select scoring case exist only as
factory-built fixtures inside `qa_create_form_question_types`, `qa_create_checkbox_scoring_quiz`,
`qa_create_multiselect_quiz_scoring` and `qa_create_free_text_survey` — none of that breadth comes from
`demo_content/` alone.

---

## 3. What "clears out the database" can mean without a `dropdb`

**The dev-only reset ladder in `.claude/fls-dev/config.md` is `DB drop` → `DB create` → `Migrate`**,
implemented as raw `DROP DATABASE` / `CREATE DATABASE` against a shared local Postgres container
(`.claude/fls-dev/scripts/dev_db_delete.sh`, `dev_db_init.sh`). That is unavailable on staging by the
idea's own premise (no DB access, and typically no superuser-level Postgres privileges over the
instance either). The realistic remaining options, in the same family as Django's own `flush`:

- **`manage.py flush`** — issues `TRUNCATE … CASCADE` (Postgres backend) across every table Django
  knows about, then re-runs the `post_migrate` signal (recreating `django_content_type` rows and
  default `Permission` rows). Because it is a raw SQL truncate, **it bypasses `on_delete=PROTECT` and
  `CASCADE` entirely** — those are Python-level `Collector` behaviours that only apply to ORM
  `.delete()` calls, not to `TRUNCATE`. Flush is "all or nothing": there is no way to flush "everything
  except the Sites table" with this command.
- **Targeted per-app/per-model truncation or ORM `.delete()` in dependency order** — the opposite
  trade-off: this *does* have to respect `PROTECT`. `Cohort.organisation` and `Learner.organisation`
  are both `on_delete=models.PROTECT` (`freedom_ls/learner_management/models.py:35`, `:67`), and
  `SiteAwareModelBase.site` is `on_delete=models.PROTECT` for every site-aware model
  (`freedom_ls/site_aware_models/models.py:54`) — so an ORM-driven wipe must delete children before
  parents (memberships/registrations before `Organisation`, everything site-aware before `Site`) or it
  raises `ProtectedError` mid-wipe, leaving the database in a worse state than before.
- **`danger_content_delete`** (`freedom_ls/content_engine/management/commands/danger_content_delete.py`)
  only ever touches content-engine and form-engine models plus the progress rows that `PROTECT` against
  them — it deliberately clears `QuestionAnswer`/`CourseFormAttempt`/`FormProgress`/`TopicProgress`/
  `CourseProgress` *first*, in that order, "same order as `danger_clear_all_course_progress`"
  (`danger_content_delete.py:78`-`90`), specifically because content is `PROTECT`ed against progress.
  It never touches users, organisations, cohorts, or role grants.

**Hazards common to any full wipe, concrete to this codebase:**

- **The `Site` the current request is being served on.** `flush` truncates `django_site` along with
  everything else; Django's `post_migrate` handler for `django.contrib.sites` only ever recreates the
  single default row (`example.com`, pk 1) — it does not know the staging host's real domain. If
  `setup_qa_data` runs as an HTTP view, the very request driving it is already bound to a `Site`
  (`CurrentSiteMiddleware` caches it on `request._cached_site` at the top of the request — see §4).
  Any `SiteAwareModel` write issued later in that same request using the now-stale cached `Site`
  Python object hits a live Postgres foreign-key violation, because the row it points to no longer
  exists. Whatever site row(s) the deployment needs must be the **first** thing re-created after a
  wipe, before any other write, and the request's own site resolution must be redone rather than
  trusted.
- **Stale `ContentType` rows after a schema change.** This is a documented incident, not a
  hypothetical: `qa_repair_form_engine_content_types.py` exists because moving the form models from
  `content_engine` into `form_engine` left `ContentCollectionItem.child_type` generic FKs pointing at
  `ContentType` rows whose `app_label` no longer resolves to a live model — "every course containing a
  quiz is broken in the browser and in every QA command that reads a course"
  (`qa_repair_form_engine_content_types.py:1`-`12`). A **partial** wipe strategy that clears rows but
  leaves `django_content_type` untouched (or vice versa) reproduces exactly this class of dangling
  generic-FK bug. A full `flush` sidesteps it (content types and everything referencing them by ID are
  wiped and regenerated together in the same operation) — this is an argument in flush's favour that a
  hand-rolled per-model delete does not automatically get.
- **`PROTECT` foreign keys**, enumerated above — `Cohort.organisation`, `Learner.organisation`,
  every `SiteAwareModelBase.site`, and the progress-vs-content chain `danger_content_delete` already
  orders around (`Topic`/`Form`/`Course` `PROTECT`ed by `TopicProgress`/`FormProgress`/`CourseProgress`,
  `learner_progress/models.py:85,110,113,123,130`). Only relevant to an ORM-driven wipe; irrelevant to
  `TRUNCATE`.
- **The superuser wiping their own account.** Whatever account is authenticated for the HTTP request
  that triggers `setup_qa_data` is itself a `User` row. A wipe that deletes all `User` rows deletes the
  one that called it. `AuthenticationMiddleware` has already resolved `request.user` at the start of
  the request, so the in-flight response can still complete, but there is then no account left to
  authenticate the *next* call to `setup_qa_data` (or anything else) — a chicken-and-egg problem unless
  a designated account survives every wipe, or is deterministically recreated with the same, known
  credentials as part of the same operation.

**What must survive a wipe, concretely:** the `Site` row(s) the deployment's `ALLOWED_HOSTS` /
incoming `Host` header need to resolve to (or an immediate, correctly-domained recreation of it before
any other write); and a way back in afterwards — either an account untouched by the wipe, or a
guaranteed recreation of one with known credentials before the response is returned.

---

## 4. Site-awareness and the domain problem

**There is no request-independent "current site" concept in this codebase, and staging has no way to
fake one.** `SiteAwareManager.get_queryset()` and `SiteAwareModelBase.save()`
(`freedom_ls/site_aware_models/models.py`) only filter/assign a site when a request is published on the
`_thread_locals` thread-local by `CurrentSiteMiddleware` — **outside a request (a bare management
command, a shell script) there is no ambient site at all**, so every write must pass `site=` explicitly
and every read that should be scoped must filter by `site` explicitly (this is exactly why every
`qa_*` command takes a site name/argument and does `Site.objects.get(name=...)` itself, rather than
relying on the manager).

**When there *is* a request, site resolution is domain-based, not ID-based, and that is deliberate.**
`get_cached_site()` (`site_aware_models/models.py:19`) checks `config.FORCE_SITE_NAME` first — but
`FORCE_SITE_NAME = "DemoDev"` is set **only** in `config/settings_dev.py:107`, not in
`settings_base.py` or `settings_prod.py`. Absent that override, it falls through to Django's own
`get_current_site(request)`, which (per `spec_dd/3. done/2026-03-12_09:95_worktree-dx/research_force_site.md`,
written when `FORCE_SITE_NAME` was designed) checks `SITE_ID` first and otherwise matches
`request.get_host()` against `Site.domain`. **`SITE_ID` is never set anywhere in this project's
settings** — that same research note rejected it explicitly, calling Site PKs "fragile" because they
are auto-incrementing and creation-order-dependent. So on a real staging deployment running
`settings_prod.py`, site resolution for every live HTTP request is **domain matching, full stop**.

**This is exactly what breaks with a hardcoded-domain seed.** `create_demo_data.py`
(`freedom_ls/learner_management/management/commands/create_demo_data.py:19`-`48`) is the concrete
example of the failure mode: it `get_or_create`s five `Site` rows keyed on literal domains —
`"127.0.0.1"`, `"127.0.0.1:8000"`, `"127.0.0.1:8001"`, etc. Point that same command at a staging host
and it creates a *sixth*, useless `Site` row whose domain never matches any real incoming `Host`
header; meanwhile every live request to the actual staging domain either matches no `Site` at all
(Django's `get_current_site` raises `Site.DoesNotExist` when nothing matches, in the no-`SITE_ID` path)
or matches an unrelated pre-existing `Site` row, depending on what else exists in that database.

**What a domain-agnostic seed needs instead:** since neither `SITE_ID` nor `FORCE_SITE_NAME` is a
staging-viable mechanism, the only reliable, already-present way to learn the real domain is the
incoming HTTP request itself — `request.get_host()` — which is only available to code running **inside
a view**, not a detached management command run blind. A `setup_qa_data` entry point that is a plain
`manage.py` command with a hardcoded or parameterised domain reproduces `create_demo_data`'s exact
mistake; one invoked as an HTTP endpoint can read the actual `Host` it was called on and key its `Site`
row(s) to that.

---

## 5. Login-ability of seeded users

Getting a fresh user to the point of actually reaching a logged-in surface needs **all** of the
following pieces to be true at once — the codebase has documented, specific failure modes for missing
each one:

1. **A verified, primary `allauth.account.models.EmailAddress`.** `ACCOUNT_EMAIL_VERIFICATION =
   "mandatory"` (`config/settings_base.py:383`) means allauth redirects an otherwise-valid login to
   `/accounts/confirm-email/` unless this row exists with `verified=True, primary=True`. This is not
   automatic from creating a `User` — `create_demo_data.py`'s `_ensure_verified_email` static method
   exists purely to patch this in by hand, and
   `.claude/agent-memory/fls-dev-qa-data-helper/reference_verified_learner_setup.md` records a real
   regression where a QA command's `_create_learner()` skipped this and nine seeded personas landed on
   the confirm-email page despite a correct password. **`update_or_create`, not `get_or_create`, is
   required** here too: a persona who previously attempted to log in may already own an
   `EmailAddress` row that allauth itself wrote as `verified=False`, and `get_or_create` leaves that
   broken row alone.
2. **`additional_registration_forms` completeness.** `RegistrationCompletionMiddleware`
   (`freedom_ls/accounts/middleware.py`) redirects any authenticated non-superuser to
   `accounts:complete_registration` until every form named in the effective
   `additional_registration_forms` list (per-`SiteSignupPolicy`, else the global
   `ADDITIONAL_REGISTRATION_FORMS` setting) reports `is_complete() == True` for that user. The global
   default is `[]` (`config/settings_base.py:404`), so a database with **no** `SiteSignupPolicy` rows
   at all is safe by default — this only bites a seed that (deliberately, for one specific scenario, as
   `qa_create_incomplete_registration_learner` does on purpose) leaves a policy configured with a
   non-empty list.
3. **`REQUIRE_TERMS_ACCEPTANCE` is a signup-form concern, not a login gate.** It controls whether the
   `/accounts/signup/` form shows a terms checkbox (`accounts/utils.py:66`-`69`,
   `accounts/forms.py:89`); it does not block an already-created, already-verified user from logging in
   or browsing. `REQUIRE_TERMS_ACCEPTANCE = True` is set only in `settings_dev.py:110` (base default is
   `False`) — this only matters if a whole-system plan exercises the signup flow itself, not for
   pre-seeded personas.
4. **`FREEDOMLS_PERMISSIONS_MODULES` and the `DemoDev` role module are dev-only extras, not a
   requirement.** `FREEDOMLS_PERMISSIONS_MODULES` defaults to `{}`
   (`freedom_ls/role_based_permissions/config.py:10`) and is set only in `settings_dev.py:103`-`105` to
   point `"DemoDev"` at `config.role_based_permissions.demodev` (`senior_ta`, `guest_reviewer` — extra
   roles layered onto `BASE_ROLES`). A site absent from this mapping simply uses `BASE_ROLES`
   (`freedom_ls/role_based_permissions/README.md:126`) — an educator surface reachable via
   `site_admin`/`instructor`/`ta` works with no per-site module at all. What **is** required, and is
   easy to skip when hand-rolling ORM inserts: an educator's cohort visibility is not just `is_staff`
   — it is a guardian object permission, granted by calling `assign_object_role` /
   `assign_site_role` (`freedom_ls/role_based_permissions/utils.py`, via
   `freedom_ls/role_based_permissions/README.md`). Several `qa_*` commands already do this explicitly
   (e.g. `qa_create_paginated_progress_matrix`'s `--educator` option grants object-level `view_cohort`).
   A wipe that clears guardian's permission tables removes these grants and they must be re-issued
   through this API, not recreated as raw rows.
5. **`django-axes` lockouts survive a login-only reset.** `AXES_FAILURE_LIMIT = 5`,
   `AXES_COOLOFF_TIME = 1` hour, keyed on `["ip_address", "username"]`
   (`config/settings_base.py:319`-`322`). A QA run that fails to log in a handful of times against the
   same seeded email from the same IP (a stale password from a previous run, a typo, a race before the
   seed committed) locks that `(ip, username)` pair out for an hour — this table is not part of any
   `qa_*` command's domain and is not cleared by `danger_content_delete` or by any of the wipe options
   in §3 unless axes' own tables are explicitly included.

---

## 6. The credentials problem

Today, credentials are a single fixed pair checked into `.claude/fls-dev/config.md`
(`demodev@email.com` / the same string as password) — safe **only** because the dev database is
per-branch and never internet-reachable. The project already has a sanctioned, gitignored per-environment
override file for exactly this shape of value (`.claude/fls-dev/config.local.md`, listed in
`.gitignore`, "whose values win" per the file's own convention), which is existing precedent for
keeping a real secret out of the checked-in default without inventing new plumbing.

The realistic options for how a staging run learns its credentials, and what each one costs:

- **Fixed, well-known QA password(s) baked into the seed** (mirroring today's dev convention, where
  several `qa_*` commands print or default to `testpass123` or "password equals the email address").
  Cheapest to implement, but a **known password on an internet-reachable host is a real account
  takeover surface** the moment that host is not perfectly firewalled — worse than the dev case because
  "disposable, local-only database" is exactly the property staging does not have.
- **Returned in the `setup_qa_data` HTTP response body**, generated fresh per wipe (a random password
  per seeded persona, handed back once). Avoids a fixed, guessable secret living in the codebase or in
  git, but means the response itself is now sensitive — whatever transport and logging touches that
  response (proxies, request logs, the QA agent's own transcript) becomes part of the credential's
  blast radius, and nothing currently in this codebase treats an HTTP response body as secret material.
- **Read from environment variables on the staging box.** Consistent with how `settings_prod.py`
  already sources every other secret (`SECRET_KEY`, `DB_PASSWORD`, `EMAIL_HOST_PASSWORD` all come from
  `os.environ`/`os.getenv` in `config/settings_prod.py`) and with the project's "never hardcode
  credentials" rule. Requires the concrete downstream project to provision that variable on its staging
  box specifically for QA, which is an operational step outside this repository's control — the value
  the codebase can offer here is the *shape* of the mechanism, not the deployment step itself.

Whichever mechanism is chosen inherits the axes lockout risk from §5 unless the reset also clears
lockout state for the account(s) the QA agent will exercise.

---

## 7. Factories vs. management commands — the load-bearing fact

**`factory-boy` is a dev/test-only dependency, not a production one.** In `pyproject.toml`, it appears
in `[project.optional-dependencies].dev` and `[dependency-groups].dev`:

```toml
[dependency-groups]
dev = [
    ...
    "factory-boy>=3.3.3",
    ...
]
```

It is **absent** from the top-level `[project].dependencies` list (`pyproject.toml:7`-`41`) that a
production install (`uv sync` without the dev group/extra) actually installs. **32 of the 35** `qa_*`
commands import factories from `freedom_ls/<app>/factories.py` (e.g.
`from freedom_ls.accounts.factories import UserFactory` in `qa_create_cohort_progress.py`) —
so on a deployment built without the `dev` dependency group, `import factory` fails before any of that
code can run at all.

This compounds with a second, independent gate: `freedom_ls.qa_helpers` itself is only added to
`INSTALLED_APPS` in `config/settings_dev.py:50` — it is **not** in `settings_base.py`'s
`INSTALLED_APPS` (`config/settings_base.py:72`-`134`) and is therefore absent under
`settings_prod.py` too. On a staging deployment running production-shaped settings, none of the
`qa_*` management commands are even registered with `manage.py`, independent of whether `factory-boy`
is installed.

The one place a factory *can* run outside pytest without `pytest-mock` is mechanical, not policy:
`SiteAwareFactory` (`freedom_ls/site_aware_models/factories.py`) reads the site from the same
`_thread_locals.request` thread-local that `CurrentSiteMiddleware` populates — the `mock_site_context`
pytest fixture (`freedom_ls/conftest.py:136`) is just one caller of that pattern, built on `pytest-mock`
(also dev-only), but the underlying trick (publish an object exposing `_cached_site` on
`_thread_locals.request`) has no pytest dependency in principle. No production code path currently does
this, though — every `qa_*` command that uses factories instead passes `site=` explicitly per call,
never relying on the thread-local at all.

---

## 8. Idempotency and runtime

**Nothing in the existing `qa_*` commands is algorithmically unbounded.** The volume-oriented commands
(`qa_create_large_cohort`, `qa_add_course_items_for_pagination`, `qa_create_paginated_progress_matrix`,
`qa_create_column_pagination_scenario`) all take an explicit, small count with a modest default: 25
learners (`qa_create_large_cohort.py:26`-`32`), 26-32 members and items
(`qa_create_paginated_progress_matrix.py:379,385`), 18-22 (`qa_create_column_pagination_scenario.py`).
These exist to exceed a pagination threshold (15 columns, 20 rows) by a small margin, not to model
production-scale data — there is no loop in this codebase that scales with an unbounded or
user-supplied-without-limit input. `content_save`'s cost is likewise bounded by the size of
`demo_content/` (§2), a few dozen rows total.

**The real time risk is cumulative and structural, not algorithmic.** Today's workflow runs each
scenario as a **separate `manage.py` process invocation** — five separate `content_save` calls, one per
course, each paying Django's app-loading cost independently; then, in principle, up to 35 more separate
process invocations for the `qa_*` commands, each with its own startup cost. None of that is
individually slow, but a synchronous HTTP request that has to do the equivalent of everything the
`qa_*` suite currently builds, sequentially, inside one request/response cycle, accumulates that
per-invocation overhead 30-40 times over before the response can return — the kind of total that a
reverse proxy's request timeout is realistically sized to catch.

**Whether pagination-volume data is needed for smoke testing at all is a real question, not a given.**
The row/column-pagination fixtures exist to test the paginators' *presence and correctness* — that a
26-item course actually produces a second column page — which is qualitatively different from a smoke
test's job of confirming the surface loads and the primary flows work. A whole-system smoke suite that
only needs "a cohort with a few members and a course with a few items" does not need the 25-32-row
fixtures at all; those matter only to a QA plan specifically targeting the pagination boundary itself.

---

status: ok
