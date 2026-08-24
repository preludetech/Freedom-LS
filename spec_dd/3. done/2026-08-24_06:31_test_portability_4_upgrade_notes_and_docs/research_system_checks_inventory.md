# Research: system checks inventory

## Summary

- **The idea file's Layer-4 claim is correct but incomplete framing.** `freedom_ls_course_access.E003`
  and `freedom_ls_learner_interface.W001` are indeed the only **new** checks the just-shipped
  `test_portability_3_system_checks` slice added, and `freedom_ls_course_access.E001` -> `.E002` is a
  real, confirmed re-ID (`freedom_ls/course_access/checks.py:1-13`,
  `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md:18-27`). But the
  repo has **17 pre-existing checks across 8 apps** that `manage.py check` also runs — the idea file's
  "the checks to reference" language is only true for "what changed in Layer 4," not "what a downstream
  will see." `update_upgrade_notes.md`'s new guidance needs to be written generally (any future spec that
  adds a hard-requirement check follows the pattern), not hardcoded to just these two IDs.
- **All 17 checks run on every plain `manage.py check`** — none use `deploy=True`
  (`grep deploy=True` returned zero hits in `freedom_ls/`). `Tags.security` /
  `Tags.compatibility` registrations (`freedom_ls/course_access/checks.py:107`,
  `freedom_ls/accounts/checks.py:12,63`) are tag labels for `--tag` filtering only, not deploy-gating —
  they still run without `--deploy`. So `uv run python manage.py check` (no flags) in `update_fls.md`
  will surface all Errors and Warnings; `--deploy` (used separately in
  `docs/deployment-security-checklist.md:114`) adds Django's *own* extra deploy-only checks on top, it
  does not gate any FLS check.
- **Errors abort with non-zero exit; Warnings do not.** Standard Django `check` behaviour — confirmed by
  usage pattern throughout (e.g. `freedom_ls/course_access/checks.py:97-103` returns `Error`s that "stop
  `check`, `runserver` and `migrate`" per the shipped upgrade notes,
  `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md:35-36`). No
  project-specific override of this behaviour was found.
- **`E001` -> `E002` is confirmed, with a live test asserting the new split.**
  `freedom_ls/course_access/tests/test_checks.py:78` still asserts `freedom_ls_course_access.E001` for
  the "unset `COURSE_ACCESS_BACKEND`" case (E001's *new*, narrowed meaning), and line 55/69 assert
  `.E002` for the "invalid `Course.access_config`" case (E001's *old* meaning, now moved). This matches
  the shipped upgrade notes exactly.
- **`SILENCED_SYSTEM_CHECKS` is a real, documented escape hatch, not hypothetical** — it appears in
  `docs/deployment-security-checklist.md:125-126` (for `freedom_ls_deployment.W001`), inline in
  `freedom_ls/deployment/checks.py:27`, and is the explicit subject of the shipped
  `test_portability_3_system_checks` upgrade notes' "Manual steps" §2 (re-point silenced `.E001` entries
  at `.E002`) — `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md:57-59`.
  The "changed check ID breaks a downstream's silencing" argument is a documented, worked hazard with a
  precedent commit, not a hypothetical.
- **Only two checks currently enforce a hard *required* setting**: `freedom_ls_course_access.E001`
  (`COURSE_ACCESS_BACKEND`) and `freedom_ls_content_engine.E001` (`ADMONITION_TYPES`) — both produced by
  the same shared helper, `required_settings_errors()`
  (`freedom_ls/base/app_settings.py:62-75`). `freedom_ls_reports.E001` uses the same helper but currently
  has zero required settings declared, so it always returns `[]` (`freedom_ls/reports/checks.py:1-4,29-34`
  doc-comment says so explicitly). These (plus the new `.E003`) are the worked examples for the new
  `update_upgrade_notes.md` guidance — `COURSE_ACCESS_BACKEND` is the one the idea/spec already name
  (`spec_dd/2. in progress/test_portability_4_upgrade_notes_and_docs/1. spec.md:27`).
- **No dedicated `docs/product/` page on boot-time system checks exists.** The only product-doc mention
  is a short paragraph in `docs/product/configuration-and-extension.md:78` about the preview-override
  warning (course_access W001); the deploy-checklist doc (`docs/deployment-security-checklist.md`) covers
  `--deploy` and `freedom_ls_deployment.W001` only. There is **no** single inventory doc a downstream can
  read for "what checks exist" — each app's `checks.py` module docstring is the closest thing
  (all 8 files carry one, e.g. `freedom_ls/icons/checks.py:1-15`).
- Every check-owning app registers its `checks` module import inside `AppConfig.ready()` — confirmed for
  all 8 apps (`freedom_ls/{accounts,base,content_engine,course_access,deployment,icons,learner_interface,
  reports}/apps.py`) — so checks load correctly under Django's app-loading contract; none are registered
  at import time outside `ready()`.
- **Correction to the idea file:** treat "the checks to reference" as scoped strictly to *this slice's
  own* `upgrade_notes.md` (Layer 5's worked example in its own notes file), not as an exhaustive list the
  new `update_upgrade_notes.md` **guidance text** should hardcode. The guidance itself must be written to
  generalize to any future check a spec adds (see §5 worked examples below for what to cite there).

## 1. Full inventory

All 17 registered checks, one `checks.py` per app, all imported from `AppConfig.ready()`:

| ID | Level | App (`apps.py` ready()?) | Enforces / checks | Registration | Deploy-only? |
|---|---|---|---|---|---|
| `freedom_ls_course_access.E001` | Error | course_access (yes, `checks.py:9`) | `COURSE_ACCESS_BACKEND` required setting unset (`freedom_ls/course_access/checks.py:41-45`, via `required_settings_errors`) | `@register()` `course_access/checks.py:25` | No |
| `freedom_ls_course_access.E002` | Error | course_access | A `Course.access_config` the active backend rejects (`course_access/checks.py:56-70`) | `@register()` `course_access/checks.py:25` | No |
| `freedom_ls_course_access.E003` | Error | course_access | `COURSE_ACCESS_BACKEND` names an FLS-namespaced (`freedom_ls.`) app not in `INSTALLED_APPS` (`course_access/checks.py:96-103`) | `@register()` `course_access/checks.py:75` | No |
| `freedom_ls_course_access.W001` | Warning | course_access | `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` / `OVERRIDE_COURSE_ACCESS_TO_FREE` on while `DEBUG=False` (`course_access/checks.py:119-136`) | `@register(Tags.security)` `course_access/checks.py:107` | No (tag only) |
| `freedom_ls_accounts.E002` | Error | accounts (yes, `apps.py:11`) | An email-theme colour/font/radius token cannot be resolved (`accounts/checks.py:38-60`) | `@register(Tags.compatibility)` `accounts/checks.py:12` | No |
| `freedom_ls_accounts.W001` | Warning | accounts | A `Site` effectively requires terms acceptance but has no resolvable `terms.md`/`privacy.md` (`accounts/checks.py:93-110`) | `@register(Tags.security)` `accounts/checks.py:63` | No |
| `freedom_ls_base.E001` | Error | base (yes, `apps.py:11`) | `HtmxMessagesMiddleware` missing from `MIDDLEWARE` (`base/checks.py:21-32`) | `@register()` `base/checks.py:16` | No |
| `freedom_ls_base.E002` | Error | base | `HtmxMessagesMiddleware` registered at/before `MessageMiddleware` (`base/checks.py:38-51`) | `@register()` `base/checks.py:16` | No |
| `freedom_ls_content_engine.E001` | Error | content_engine (yes, `apps.py:10`) | `ADMONITION_TYPES` required setting unset (`content_engine/checks.py:16-20`, via `required_settings_errors`) | `@register()` `content_engine/checks.py:15` | No |
| `freedom_ls_deployment.W001` | Warning | deployment (yes, `apps.py:9`) | `SENTRY_DSN` set but `SENTRY_RELEASE` blank (`deployment/checks.py:20-46`) | `@register()` `deployment/checks.py:19` | No |
| `freedom_ls.E001` | Error | icons (yes, `apps.py:8`) | Unknown `FREEDOM_LS_ICON_SET` name (`icons/checks.py:29-39`) | `@register()` `icons/checks.py:25` | No |
| `freedom_ls.E002` | Error | icons | Iconify JSON file missing on disk for the configured set (`icons/checks.py:41-49`) | `@register()` `icons/checks.py:25` | No |
| `freedom_ls.E003` | Error | icons | Mapping value (base icon name) not found in Iconify JSON (`icons/checks.py:70-78`) | `@register()` `icons/checks.py:53` | No |
| `freedom_ls.E004` | Error | icons | Variant-suffixed icon name not found in Iconify JSON (`icons/checks.py:80-90`) | `@register()` `icons/checks.py:53` | No |
| `freedom_ls.E005` | Error | icons | Override key not a valid semantic icon name (`icons/checks.py:112-118`) | `@register()` `icons/checks.py:94` | No |
| `freedom_ls.E006` | Error | icons | Override icon name not found in Iconify JSON (`icons/checks.py:119-126`) | `@register()` `icons/checks.py:94` | No |
| `freedom_ls.E007` | Error | icons | Mapping keys don't match `SEMANTIC_ICON_NAMES` (`icons/checks.py:134-145`) | `@register()` `icons/checks.py:130` | No |
| `freedom_ls.W001` | Warning | icons | Commonly-used variants (outline, solid) unsupported by the active icon set (`icons/checks.py:157-167`) | `@register()` `icons/checks.py:149` | No |
| `freedom_ls_learner_interface.W001` | Warning | learner_interface (yes, `apps.py:10`, **new AppConfig.ready() added by Layer 4**) | A `sitemap` URL is wired but `django.contrib.sitemaps` not installed (`learner_interface/checks.py:26-48`) | `@register()` `learner_interface/checks.py:18` | No |
| `freedom_ls_reports.E001` | Error (dormant) | reports (yes, `apps.py:10`) | Required reports settings unset — currently none are declared required, so always `[]` (`reports/checks.py:29-34` + docstring `reports/checks.py:3-6`) | `@register()` `reports/checks.py:29` | No |
| `freedom_ls_reports.W001` | Warning | reports | `REPORTS_STORAGE_ALIAS` names no key in `settings.STORAGES` (`reports/checks.py:38-55`) | `@register()` `reports/checks.py:37` | No |
| `freedom_ls_reports.W002` | Warning | reports | Compiled Tailwind bundle not resolvable via staticfiles finders (`reports/checks.py:59-71`) | `@register()` `reports/checks.py:58` | No |
| `freedom_ls_reports.W003` | *retired* | reports | Retired — "Do not reuse the id: a project may still be silencing it" (`reports/checks.py:14`) | n/a | n/a |
| `freedom_ls_reports.W004` | Warning | reports | A `REPORTS_FONT_FACES` entry's static path not resolvable (`reports/checks.py:75-92`) | `@register()` `reports/checks.py:74` | No |

That is **17 live checks + 1 retired ID** (`freedom_ls_reports.W003`) across 8 apps
(`freedom_ls/{accounts,base,content_engine,course_access,deployment,icons,learner_interface,reports}/
checks.py`). The `icons` app uses a flat `freedom_ls.` namespace (not `freedom_ls_icons.`) — noted as a
deliberate non-fix in the sibling spec's idea file: "renumbering `icons/checks.py`'s flat IDs (deliberate
non-fix per D3)" (`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/idea.md:60-61`).

All checks are registered plain `@register()` or `@register(Tags.security)` /
`@register(Tags.compatibility)` — **none** use `@register(Tags.security, deploy=True)` or any
`deploy=True` (confirmed by a zero-hit grep for `deploy=True` across `freedom_ls/`). This means every one
of them runs on a bare `manage.py check`, `runserver`, `migrate`, and `test` — the `Tags.*` argument is
only a grouping label for `--tag` filtering, not a deploy gate.

## 2. New from Layer 4 vs pre-existing

Cross-referencing the sibling spec's own idea/spec/upgrade-notes files
(`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/{idea.md,upgrade_notes.md}`):

- **New in Layer 4 (this slice, shipped):**
  - `freedom_ls_course_access.E003` — brand new check function
    `check_course_access_backend_app_installed` (`course_access/checks.py:75-104`).
  - `freedom_ls_learner_interface.W001` — brand new module `learner_interface/checks.py` **and** a new
    `LearnerInterfaceConfig.ready()` (`learner_interface/apps.py:9-10`) — this app had no checks before.
  - `freedom_ls_course_access.E002` — not literally "new," but re-IDed out of the old `.E001` (see §3).
- **Pre-existing (unchanged by Layer 4), confirmed by the sibling idea.md's explicit "Not in scope" list**
  (`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/idea.md:59-61`: "a second
  required-setting check (already covered by E001)... and renumbering `icons/checks.py`'s flat IDs
  (deliberate non-fix per D3)"): `freedom_ls_course_access.E001` (renamed meaning but same ID slot,
  pre-existing from Layer 0), `freedom_ls_course_access.W001`, all `accounts.*`, all `base.*`,
  `content_engine.E001`, `deployment.W001`, all `icons.*` (`freedom_ls.E001`-`E007`, `W001`), and all
  `reports.*`.
- **Confirms/refutes the idea file:** CONFIRMED for what changed — `.E003` and `.W001` (learner_interface)
  are the only two genuinely new check IDs from Layer 4, and the `.E001`->`.E002` re-ID is real. REFUTED
  as a complete inventory — 15 other check IDs pre-date this slice and will also fire on the
  `manage.py check` call the new `update_fls.md` step adds. The idea file is accurate about "what Layer 4
  changed" but a reader could mistake the phrasing "the checks to reference" for "the only checks that
  exist" — worth tightening in `1. spec.md`/`2. plan.md` wording if it becomes ambiguous in the
  implementation (this slice's own `upgrade_notes.md`, not the general `update_upgrade_notes.md`
  guidance, is the right place to name exactly these three items).

## 3. The E001 -> E002 re-ID

Confirmed real, with before/after evidence:

- **Module docstring today** (`freedom_ls/course_access/checks.py:7-12`):
  `E001` — "A required setting is unset"; `E002` — "A Course has an access_config the active backend
  rejects, typically after a COURSE_ACCESS_BACKEND swap."
- **Shipped upgrade notes describe the split explicitly**
  (`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md:18-27`):
  > "`freedom_ls_course_access.E001` has been split. It previously covered two unrelated conditions; the
  > 'a `Course` has an `access_config` the active backend rejects' error is now reported as
  > `freedom_ls_course_access.E002`. `E001` now means only 'a required setting is unset'..."
- **`freedom_ls_course_access.E001` still exists** — it was never removed, only narrowed. It is emitted
  by `check_course_access_configs` when `config.missing_required()` is truthy
  (`course_access/checks.py:41-45`, via `required_settings_errors`, which always emits
  `<app_label>.E001` — `freedom_ls/base/app_settings.py:68-75`).
  Confirmed live in the test suite:
  `freedom_ls/course_access/tests/test_checks.py:72-79` — `test_unset_backend_reports_required_setting_error`
  asserts `errors[0].id == "freedom_ls_course_access.E001"` when `COURSE_ACCESS_BACKEND=""`.
  `freedom_ls/course_access/tests/test_checks.py:55,69` assert `.E002` for the bad-`access_config` cases.
- **The sibling idea.md names the motivation directly**
  (`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/idea.md:54-57`):
  > "Split the overloaded `freedom_ls_course_access.E001` — it currently means both 'required setting
  > unset' and 'invalid `Course.access_config`', so `SILENCED_SYSTEM_CHECKS` cannot target either
  > precisely. Re-ID the second to `.E002`. This is a fix to already-merged code and is
  > downstream-visible."

## 4. `SILENCED_SYSTEM_CHECKS`

Real and documented, not hypothetical — three independent, concrete uses found by repo-wide grep:

1. **Escape hatch for a currently-shipping check:** `docs/deployment-security-checklist.md:125-126` —
   "`freedom_ls_deployment.W001` (`SENTRY_DSN` set but `SENTRY_RELEASE` blank) can be silenced via
   `SILENCED_SYSTEM_CHECKS` if release tracking is intentionally disabled for an environment." Also
   documented inline in the check's own docstring: `freedom_ls/deployment/checks.py:27`.
2. **The precise, already-shipped hazard this slice's guidance is about:** the sibling spec's own
   upgrade notes instruct exactly the "audit `SILENCED_SYSTEM_CHECKS`, replace the old ID" maneuver —
   `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md:23-27,57-59`, and its
   frontmatter sets `changed_settings: ["SILENCED_SYSTEM_CHECKS"]`
   (`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md:6`) — i.e. an
   already-shipped spec used exactly this schema field for exactly this hazard. This is the strongest
   available precedent for the new `update_upgrade_notes.md` guidance to point at.
3. **Design-time rationale recorded in the sibling spec's own spec/plan:** "so
   `SILENCED_SYSTEM_CHECKS` can target it unambiguously"
   (`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/1. spec.md:82,236,240,254,285`) and
   `spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/2. plan.md:287` — "a project silencing
   [the old ID]..." — the split-check design was driven specifically by wanting precise
   `SILENCED_SYSTEM_CHECKS` targeting.
4. Also referenced (deploy-checklist context) at
   `spec_dd/3. done/2026-07-19_07:52_more-deploy-preparation/upgrade_notes.md:64` — an earlier slice
   (`more-deploy-preparation`, shipped 2026-07-19) already used the same "silence via
   `SILENCED_SYSTEM_CHECKS`" pattern for `freedom_ls_deployment.W001` when it was first introduced, and
   its own `2. plan.md:80,113,248` show the same self-consistency concern the new guidance should
   generalize.

**Verdict:** "a changed check ID breaks a downstream's silencing" is a real, already-realized hazard with
one shipped precedent commit (`test_portability_3_system_checks` / `.E001`->`.E002`), not a hypothetical
edge case. The new `update_upgrade_notes.md` guidance can cite this exact precedent as its worked example.

## 5. Hard-requirement checks (worked examples for the new guidance)

Checks that enforce a settings value a downstream **must** set, all built on the shared
`required_settings_errors()` helper (`freedom_ls/base/app_settings.py:62-75`), which reads
`AppSettings.declared_settings` entries marked `Setting(required=True)`:

| Check | Setting enforced | What a downstream must do | Evidence |
|---|---|---|---|
| `freedom_ls_course_access.E001` | `COURSE_ACCESS_BACKEND` | Set it to a dotted path of an installed course-access backend class | `freedom_ls/course_access/config.py:14` declares `required=True`; check at `freedom_ls/course_access/checks.py:41-45` |
| `freedom_ls_content_engine.E001` | `ADMONITION_TYPES` | Set a non-empty registry with a `"default"` key (consumer reads `registry["default"]` and would `KeyError` at render time otherwise) | `freedom_ls/content_engine/config.py:15` declares `required=True`; check docstring `freedom_ls/content_engine/checks.py:3-6` |
| `freedom_ls_reports.E001` | *(none currently declared required)* | Nothing today — dormant; the check exists "to keep the app honest if a required setting is added later" | `freedom_ls/reports/checks.py:3-6` |

`COURSE_ACCESS_BACKEND` is the example the idea/spec already cite by name — "as `home_page` did with
`COURSE_ACCESS_BACKEND`" (`spec_dd/2. in progress/test_portability_4_upgrade_notes_and_docs/1. spec.md:27`)
— and it is the only one of the three with a **second**, separate hard-requirement check layered on top
(`.E003`, checking the *value* names an installed app, not just that it's set) — a good second worked
example of "a spec adds a Layer-4 check enforcing [a] requirement" per the spec's own Layer-5 language
(`1. spec.md:29-30`).

Two Warning-level checks are also settings-adjacent but are not "hard requirements" (they have safe
defaults, just imperfect ones): `freedom_ls_reports.W001` (`REPORTS_STORAGE_ALIAS`, defaults to Django's
default storage) and `freedom_ls_deployment.W001` (`SENTRY_RELEASE`, only degrades Sentry tagging). These
are useful as the *contrast* case in the new guidance — "optional/informational" per
`1. spec.md:26-30`'s own framing — since they warn but never block `check`/`runserver`/`migrate`.

## 6. `manage.py check` behaviour

- **No `--deploy` gating for any FLS check.** Confirmed by the zero-hit `deploy=True` grep across
  `freedom_ls/`. `--deploy` only adds *Django's own* built-in deployment checks (HSTS, SSL redirect,
  cookie-secure flags, `DEBUG`) — these are listed separately in
  `docs/deployment-security-checklist.md:109-123` as the reason to run `manage.py check --deploy` before
  every release. `manage.py check` with no flags already runs all 17 FLS checks.
- **Errors vs Warnings:** Django's standard `check` semantics apply — an `Error` causes `check` (and
  `runserver`/`migrate`/`test`, since checks run automatically at those points too, per the module
  docstrings e.g. `freedom_ls/course_access/checks.py:4-5`, `freedom_ls/icons/checks.py:4-5`) to fail with
  a non-zero exit and abort; a `Warning` is printed but does not abort. This is explicitly stated for the
  new `.E003` check in the shipped upgrade notes: "Because it is an `Error`, it will stop `check`,
  `runserver` and `migrate`"
  (`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/upgrade_notes.md:35-36`).
- **No dedicated product doc for boot-time system checks.** Searched `docs/product/**` for "system
  check"/"manage.py check"/"boot-time" — the only hit is one paragraph in
  `docs/product/configuration-and-extension.md:78` describing the preview-override Warning
  (`freedom_ls_course_access.W001`) in prose, without naming the check ID or the general mechanism. There
  is **no** "here is the full list of FLS system checks" page anywhere in `docs/product/`. Each
  `checks.py` module's docstring is the closest thing to a per-app inventory (all 8 files have one,
  e.g. `freedom_ls/icons/checks.py:1-15`, `freedom_ls/course_access/checks.py:1-13`).
- **`docs/deployment-security-checklist.md`** is the one doc that names specific check IDs today, but
  only `freedom_ls_deployment.W001` (§9, lines 109-126) and a generic "no legal-doc system-check [failures]"
  checkbox at line 221 (implicitly `freedom_ls_accounts.W001`, not named by ID). Neither `.E003` nor
  `learner_interface.W001` is mentioned there — that doc predates the Layer-4 slice and was not part of
  its scope (not flagged as a gap by the sibling idea/spec, so likely out of scope for this slice too,
  but worth flagging to the user in case `update_fls.md`/`update_upgrade_notes.md` guidance should
  cross-reference it).

## Open questions for the user

- Should `docs/deployment-security-checklist.md` (or a new `docs/product/` page) be updated to list all
  17 check IDs as a downstream-facing inventory, or is that explicitly out of scope for this slice (per
  `1. spec.md`'s "Not in scope" section, which only excludes the `configuration-and-extension.md`
  settings-convention note, not a full check inventory)? This research did not find such a doc gap called
  out anywhere in this slice's own idea/spec/plan, so it may be worth a deliberate non-goal note if the
  plan doesn't already have one.
- The dormant `freedom_ls_reports.E001` (always returns `[]` today) and the retired
  `freedom_ls_reports.W003` (id never reused) are good illustrative examples if `update_upgrade_notes.md`
  wants to also document the "never reuse a retired check ID" convention alongside the "changed check ID
  breaks silencing" one — worth considering as a second worked example, since it's the mirror-image
  hazard (reusing vs. changing an ID) and is already precedented in-repo.

status: ok
