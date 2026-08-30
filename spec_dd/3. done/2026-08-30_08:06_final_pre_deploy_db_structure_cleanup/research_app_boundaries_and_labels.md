# Research: app boundaries, labels and table namespacing

## 1. The label inventory

25 Django apps live under `freedom_ls/` (`Glob freedom_ls/*/apps.py`). No model in the tree sets `Meta.db_table`, so every table name is Django's default: `<app_label>_<model_name_lowercase>`.

| App | `label` | Owns tables | Table prefix | In `INSTALLED_APPS` |
|---|---|---|---|---|
| `accounts` | `freedom_ls_accounts` | Yes | `freedom_ls_accounts_` | base |
| `app_authentication` | `freedom_ls_app_authentication` | No tables exist (no `migrations/` dir) | n/a | no, commented out at `settings_base.py:99` |
| `base` | `freedom_ls_base` | No models | n/a | base |
| `content_base` | `freedom_ls_content_base` | No, 3 abstract bases only, no `migrations/` dir | n/a | base |
| `content_engine` | `freedom_ls_content_engine` | Yes | `freedom_ls_content_engine_` | base |
| `course_access` | `freedom_ls_course_access` | No models | n/a | base |
| `course_applications` | `freedom_ls_course_applications` | Yes | `freedom_ls_course_applications_` | base |
| `course_interest` | `freedom_ls_course_interest` | Yes | `freedom_ls_course_interest_` | base |
| `deployment` | `freedom_ls_deployment` | No models | n/a | base |
| `educator_interface` | `freedom_ls_educator_interface` | No, `migrations/` has only `__init__.py` | n/a | base |
| `form_engine` | `freedom_ls_form_engine` | Yes | `freedom_ls_form_engine_` | base |
| `health` | none set, defaults to `health` | No models | n/a | base |
| `icons` | none set, defaults to `icons` | No models | n/a | base |
| `learner_interface` | `freedom_ls_learner_interface` | No models | n/a | base |
| `learner_management` | `freedom_ls_learner_management` | Yes | `freedom_ls_learner_management_` | base |
| `learner_progress` | `freedom_ls_learner_progress` | Yes | `freedom_ls_learner_progress_` | base |
| `markdown_rendering` | `freedom_ls_markdown_rendering` | No models | n/a | base |
| `organisations` | `freedom_ls_organisations` | Yes | `freedom_ls_organisations_` | base |
| `panel_framework` | `freedom_ls_panel_framework` | No models | n/a | base |
| `qa_helpers` | `freedom_ls_qa_helpers` | No, `migrations/` has only `__init__.py` | n/a | dev only, `settings_dev.py:50` |
| `reports` | `freedom_ls_reports` | Yes | `freedom_ls_reports_` | base |
| `role_based_permissions` | `freedom_ls_role_based_permissions` | Yes | `freedom_ls_role_based_permissions_` | base |
| `site_aware_models` | `freedom_ls_site_aware_models` | No, `SiteAwareModelBase`/`SiteAwareModel` are both `abstract = True`, no `migrations/` dir | n/a | base |
| `webhooks` | none set, defaults to `webhooks` | Yes, 4 models | `webhooks_` | base |
| `xapi_learning_record_store` | `freedom_ls_xapi` | No, `models.py` fully commented out, no `migrations/` dir | n/a | no, never listed (`settings_base.py:100` comment only) |

Three apps declare no `label` at all: `freedom_ls/webhooks/apps.py:4-6`, `freedom_ls/health/apps.py:4-5`, `freedom_ls/icons/apps.py:4-5,7-8`. Each sets only `name = "freedom_ls.<app>"`, so Django's default rule (`label = name.rpartition(".")[2]`) gives them the bare names `webhooks`, `health`, `icons`. Every other app sets an explicit `freedom_ls_<app>` label.

`webhooks` is the one app with real tables that breaks the universal `freedom_ls_<app>` table-namespacing convention. `WebhookEndpoint`, `WebhookEvent`, `WebhookDelivery`, `WebhookSecret` (`freedom_ls/webhooks/models.py`) sit in tables `webhooks_webhookendpoint`, `webhooks_webhookevent`, `webhooks_webhookdelivery`, `webhooks_webhooksecret`, the only table prefix in the whole schema that does not start `freedom_ls_`. `health` and `icons` have no models, so their missing label is a pure boot-time collision risk with no table-rename cost attached.

**The collision.** FLS installs into a downstream project's `INSTALLED_APPS` alongside that project's own apps (`docs/product/configuration-and-extension.md:81-89`). `webhooks`, `health`, and `icons` are exactly the generic app names a downstream project is likely to pick for its own app. Two apps sharing a label crashes `Apps.populate()` before any view or command runs. `django/apps/registry.py:92-96` (`.venv/lib/python3.13/site-packages/django/apps/registry.py`) raises `ImproperlyConfigured("Application labels aren't unique, duplicates: %s" % app_config.label)`. That failure is loud and immediate, not silent data corruption, but it stops the downstream project's process from starting until one side relabels.

**What a label change costs once migrations exist.** Django's own docs (`docs.djangoproject.com/en/6.0/ref/applications/`) state: "Changing this attribute after migrations have been applied for an application will result in breaking changes to a project or, in the case of a reusable app, any existing installs of that app. This is because `AppConfig.label` is used in database tables and migration files when referencing an app in the dependencies list." For `webhooks`: 9 of its 10 migration files (`0002` through `0010`) reference the label `'webhooks'`, either in `dependencies = [('webhooks', '000N_...')]` or as an FK target string `to='webhooks.webhookendpoint'` / `to='webhooks.webhookevent'` (`freedom_ls/webhooks/migrations/0001_initial.py:62-63`). No `GenericForeignKey` in the codebase targets a webhook model. The only three `GenericForeignKey` users are the deadline models in `learner_management/models.py:173,220,268`, all pointing at `Topic`/`Form`, so there is no stale `ContentType.app_label` row to reconcile beyond the migration-string rewrite itself. `health` and `icons` cost only a one-line `label = "freedom_ls_health"` / `label = "freedom_ls_icons"` addition; no migrations exist to touch.

FLS has not shipped a deploy yet. This is the last point at which any of these three relabels is a same-app, no-coordination change rather than a downstream-breaking one.

## 2. The extractable-app exemption

**The convention.** An app is extractable when a spec has committed it to leaving `freedom_ls/` for its own installable package, with its own repository, versioning, and consumers beyond FLS. An extractable app is exempt from two FLS-wide conventions that only make sense for code staying inside the FLS tree permanently:

- The `freedom_ls_<app>` label convention. The label gets renamed again at extraction time to whatever the published package calls itself (the icons app's decided module name is `django_semantic_iconify`, not `freedom_ls_icons`, per `spec_dd/1. next/extract-icons-app/idea.md:76`), so forcing the FLS-prefixed label onto it first is a rename that gets thrown away a second time.
- The `SiteAwareModel` convention. A package with outside consumers cannot depend on FLS's multi-tenancy base class. It resolves tenancy, if it wants any at all, through Django's own `django.contrib.sites`, optionally and nullably.

An extractable app is not exempt from anything else: normal test coverage, normal system-check hygiene, normal `docs/app_structure.md` participation while it still lives in-tree, and, critically, the direction of its dependency edges. Every extractable-app spec states the same constraint independently. Dependencies point host to app, never app to FLS. `referral-link-tracker`'s idea document is the most explicit: "It must not import from FLS-specific apps (`content_engine`, `course_interest`, `course_applications`, `student_management`, `accounts`) or subclass FLS base classes (`SiteAwareModel`). Dependency direction is strictly host to app, never app to host" (`spec_dd/1. next/referral-link-tracker/idea.md:29-33`). Its own data-model research is flagged for translation for exactly this reason: "its sketch subclasses FLS's `SiteAwareModel` and hooks FLS models directly, for the extractable app, translate that to plain models (optional `contrib.sites` FK)" (`idea.md:196-199`).

**Named members, today.**

| App | Where it lives now | Extraction spec | Current label | Current base class |
|---|---|---|---|---|
| `icons` | `freedom_ls/icons/` | `spec_dd/1. next/extract-icons-app/idea.md` | none set, bare `icons` | no models |
| `markdown_rendering` | `freedom_ls/markdown_rendering/` | `spec_dd/1. next/debt_markdown_rendering_package_isolation/idea.md` | `freedom_ls_markdown_rendering` | no models |
| `referral-link-tracker` | does not exist yet. `spec_dd/1. next/referral-link-tracker/` is an idea, not code | same idea document | n/a | n/a, will never be `SiteAwareModel` by design |

`icons` and `markdown_rendering` have no models, so the `SiteAwareModel` half of the exemption is moot for both today; neither currently has anything to be exempt from. `icons`' bare `icons` label already matches what the exemption would prescribe, but nothing in the codebase documents that as the reason. It reads as an app that simply never had a label added, and its own extraction idea never mentions the label at all; the actual post-extraction identity is the unrelated name `django_semantic_iconify`. `markdown_rendering` sits in the opposite state: it already carries the `freedom_ls_` label the exemption says it need not have, and its own extraction-adjacent idea (`debt_markdown_rendering_package_isolation`) is scoped to test-dependency cleanup, not a label rename. Today, neither app's actual label reflects a deliberate application of this exemption. Only `referral-link-tracker`'s not-yet-written idea document states the rule in so many words.

**Where the convention should live.** Nothing in `docs/` names `SiteAwareModel` at all (`Glob docs/**/*.md`, `Grep "SiteAwareModel"` across `docs/`, zero hits). `docs/product/multi-tenancy-and-isolation.md` documents the site-isolation behaviour in product terms, "every database read during a request is scoped to the site" (`:10`), without ever naming the base class that implements it. `docs/product/configuration-and-extension.md` covers extension points (theming, icons, course-access backends) without a general statement of when a model must or must not subclass `SiteAwareModel`. There is no home today for "here is when `SiteAwareModel` applies, and here is who is exempt." It needs a new document, or a new section in `multi-tenancy-and-isolation.md`, stating: every concrete model in an app that stays in `freedom_ls/` subclasses `SiteAwareModel`, unless the app is on the named extractable-app list, in which case it uses plain models with an optional `contrib.sites` FK instead.

**`health` under the rule.** `health` (`freedom_ls/health/`) has no models and no extraction plan anywhere in `spec_dd/`. It fails the exemption test on both grounds: not extractable, so it gets no exemption, and its missing label (§1) is a plain omission to fix, not a case for the allowlist. It should carry `label = "freedom_ls_health"` like every other permanently-in-tree app.

## 3. The guardrail

**Where it belongs.** `freedom_ls/contrib/conformance/` (`test_migrations.py`, `test_urls.py`, `test_settings.py`, `test_theme.py`) is the downstream-facing conformance surface, an importable module a downstream project brings into its own test suite to check its own wiring of FLS (`docs/product/configuration-and-extension.md:93-99`), proven green against FLS's own reference configuration first (same doc, `:97`). A label-namespacing guardrail is a different kind of check. It asserts something about FLS's own apps' internal naming hygiene, not about how a downstream project wired FLS up. It does not belong in the downstream-exported probe set: a downstream project's own apps are not this guardrail's business, and nothing about correct downstream wiring depends on FLS's labels being tidy.

The nearest existing precedent for the mechanism is `freedom_ls/contrib/conformance/test_migrations.py::test_migration_state_consistent()`, a no-database, disk-only probe that iterates the app registry (`apps.get_app_configs()` via `ProjectState.from_apps(apps)`) and asserts a property of the whole installed set. A namespacing guardrail should follow the same idiom, no DB, no fixtures, cheap enough for every test run, but scoped only to apps whose `AppConfig.name` starts with `freedom_ls.`, so a downstream project's own apps, however they are labelled, are never touched by it. It belongs as an FLS-repo-internal test, marked `pytest.mark.fls_internal` (the marker `freedom_ls/contrib/conformance/tests/test_conformance_meta.py:49` already uses for probes proven only against FLS itself), not as an exported conformance probe.

**How it encodes the exemption.** Not a blanket "every label starts with `freedom_ls_`" assertion; that would immediately and permanently fail `icons` by design. The check should assert: for every installed app whose `name` starts with `freedom_ls.`, either its `label` starts with `freedom_ls_`, or its bare module name appears in a short, named allowlist matching §2's extractable-app list. Today that allowlist is `{"icons"}`. `markdown_rendering` already carries the prefixed label, so it needs no allowlist entry to pass, and `referral-link-tracker` isn't code yet, so it gets added the day its app directory is created. The allowlist is the guardrail's only configuration surface, and it should cite this research file, or its successor doc, as the source of truth for what belongs on it.

**What it should say when it fires.** Name the offending app, its resolved bare label, and either "add `label = \"freedom_ls_<app>\"` to its `AppConfig`" or, if the app is a deliberate extraction candidate not yet on the allowlist, "add `<app>` to the guardrail's exemption list and cite the extraction spec." Adding this guardrail today would immediately flag `health` and `webhooks` (§1), correctly, since neither is on the extractable-app list.

**What `test_migration_state_consistent()` covers and does not.** It diffs `ProjectState.from_apps(apps)` (models as Python currently defines them) against `MigrationLoader(None, ignore_no_migrations=True).project_state()` (models as the migration graph on disk would produce), and asserts no `MigrationAutodetector` changes remain: no model field, model, or index has been added, removed, or altered without a matching migration file (`freedom_ls/contrib/conformance/test_migrations.py:19-26`). It does not check app labels, table name prefixes, or anything about `INSTALLED_APPS` composition. A label collision, a missing label, or two apps racing for the same table prefix all pass this check silently, because none of them is a model/migration drift. The two checks are complementary, and neither substitutes for the other.

## 4. Namespacing defects beyond the label

Django's convention for a system-check id is `<app_label>.<severity><NNN>` (`E` for Error, `W` for Warning). The label segment must equal the app's own registered `AppConfig.label`, not a fixed literal. Of the nine `checks.py` files:

| App | Check-id prefix used | Matches its own `AppConfig.label`? |
|---|---|---|
| `base` | `freedom_ls_base` (`freedom_ls/base/checks.py:29,49`) | Yes |
| `content_engine` | `freedom_ls_content_engine` (`freedom_ls/content_engine/checks.py:20`) | Yes |
| `accounts` | `freedom_ls_accounts` (`freedom_ls/accounts/checks.py:53,58,112`) | Yes |
| `course_access` | `freedom_ls_course_access` (`freedom_ls/course_access/checks.py:45,68,101,134`) | Yes |
| `deployment` | `freedom_ls_deployment` (`freedom_ls/deployment/checks.py:70,147,161,175,220,267,311`) | Yes |
| `learner_interface` | `freedom_ls_learner_interface` (`freedom_ls/learner_interface/checks.py:46`) | Yes |
| `organisations` | `freedom_ls_organisations` (`freedom_ls/organisations/checks.py:21`) | Yes |
| `reports` | `freedom_ls_reports` (`freedom_ls/reports/checks.py:45,64`) | Yes |
| `icons` | `freedom_ls` (`freedom_ls/icons/checks.py:36,47,76,88,116,124,144,165`) | No |

`icons`' own label is bare `icons` (§1). `freedom_ls` is not any app's registered label, so these ids are not merely inconsistent with the convention, they are inconsistent with themselves: they namespace under a label nothing in `INSTALLED_APPS` holds.

**House rule.** A check id's app-label segment must equal that app's own currently-registered `AppConfig.label`, whatever it is, not a hardcoded assumption about what the label ought to be. This formulation is deliberately compatible with §2's exemption: if `icons` keeps its bare `icons` label, its check ids should read `icons.E001` and so on, matching what's actually registered, not `freedom_ls_icons.E001`. Fixing `icons/checks.py` is a one-file, mechanical rename to whichever label `icons` ends up carrying, cheap now, and worth doing before any downstream project has a reason to reference `freedom_ls.E00x` in its own `SILENCED_SYSTEM_CHECKS`.

## 5. Dormant and misconfigured apps

**`app_authentication`.** Not in `INSTALLED_APPS` (`config/settings_base.py:99`, commented out), no `migrations/` directory (`Glob freedom_ls/app_authentication/*.py` returns only `__init__.py`, `apps.py`, `factories.py`, `admin.py`, `models.py`). `Client(SiteAwareModel)` (`freedom_ls/app_authentication/models.py:8`) stores `api_key = models.CharField(max_length=64, unique=True, editable=False, ...)` (`:15-20`), generated by `secrets.token_urlsafe(48)` (`:41-43`), plaintext, queryable, and exposed by a working `ClientAdmin` (`freedom_ls/app_authentication/admin.py:8-35`) the moment the app is ever installed. `webhooks.WebhookSecret.encrypted_value` (`freedom_ls/webhooks/models.py:421`) already uses `encrypted_fields.fields.EncryptedTextField` (`:9`) for exactly this kind of value, so the repo already has the tool this model should have used and didn't.

Verdict: delete. Nothing installs it, nothing imports it outside its own `factories.py`, and keeping a plaintext-credential model dormant is a live trap for whoever re-enables it later without re-reading `models.py` closely. If API-client auth is wanted, the fix is a fresh model built on `EncryptedTextField` (or a hashed-key scheme), not a resurrection of this one.

**`xapi_learning_record_store`.** `apps.py` sets `name = "freedom_ls.xapi"` (`freedom_ls/xapi_learning_record_store/apps.py:6`), not the module's real dotted path (`freedom_ls.xapi_learning_record_store`). Adding `"freedom_ls.xapi_learning_record_store"` to `INSTALLED_APPS` as written would resolve `apps.py` correctly, but `name = "freedom_ls.xapi"` would then point Django at a non-existent `freedom_ls.xapi` package path for the app's module, raising `ImportError` at `Apps.populate()`. `label` is already `freedom_ls_xapi` (`:7`), ahead of the directory and `name`, not behind them. `models.py` is fully commented out (`freedom_ls/xapi_learning_record_store/models.py:1-37`, every line prefixed `#`), so there is nothing to migrate and nothing at risk. `spec_dd/1. next/xapi_implementation/0. idea.md:7-9` already states the fix: "Rename the existing `xapi_learning_record_store` directory to `xapi` (the app config already uses `freedom_ls.xapi`)."

Verdict: leave dormant, exactly as-is. The rename this idea would otherwise flag is already scoped in a live, detailed sibling spec. Doing it here would only create merge friction against that spec for no benefit.

## 6. Misplaced code across app boundaries

`calculate_course_progress_percentage` (`freedom_ls/learner_management/utils.py:17-42`) is defined in `learner_management` but has no dependency on any `learner_management` model or import. It takes a `Course` (from `content_engine`, imported only under `TYPE_CHECKING`, `utils.py:10`) and a `set[UUID]`, and walks `course.viewable_collection_items()`. Every real caller is in `learner_progress`: `freedom_ls/learner_progress/signals.py:29,54`, `freedom_ls/learner_progress/management/commands/recalculate_progress_percentages.py:6,58`, plus its own app's tests (`freedom_ls/learner_management/tests/test_course_progress_calculation.py`, 9 call sites) and two `qa_helpers` commands that already depend on both apps directly regardless of where the function lives (`qa_create_rich_dashboard_learner.py:39,215`, `qa_create_paginated_progress_matrix.py:61,354`).

**Moving it does not delete the `learner_progress → learner_management` edge in `docs/app_structure.md:100`.** `learner_progress` imports from `learner_management` at runtime in four other files, independent of this function: `models.py:10` (`CohortCourseRegistration`, `Learner`, `LearnerCourseRegistration`), `utils.py:10` (the same three, for `ensure_course_progress_record`), `queries.py:11,175` (`learner_for_course`, and the same model trio), and `signals.py:23` (the same trio again, for the registration-created signal handlers). The edge is structural to what `learner_progress` is: a `CourseProgress` record is keyed on a `Learner` and one of two `learner_management` registration models. It is not an artifact of one misplaced utility function.

**What the move actually buys.** It relocates a function with zero `learner_management` dependency to the one app that genuinely owns progress-percentage math, leaving `learner_management/utils.py` scoped to what its name promises: registration and access checks (`is_registered_for_course`, `ensure_learner`), rather than a progress calculation that happens to have landed there. It removes one cross-app import statement (`learner_progress/signals.py:29` and `recalculate_progress_percentages.py:6` would import from their own app instead), and the `qa_helpers` commands' existing imports are unaffected either way, since both apps are already declared dependencies in that app's `docs/app_structure.md` row. It buys tidiness and correct ownership. It does not buy a smaller dependency graph.

**Survey for any other module whose move would delete an edge.** Every other app's cross-app-facing utility module was checked against `docs/app_structure.md`'s dependency table for a function whose only cross-app import exists solely to serve callers in one other specific app. `accounts/utils.py` imports only `site_aware_models.get_cached_site`, an edge accounts needs directly (`:8`); correctly scoped. `organisations/utils.py` (`get_default_organisation`) is self-contained, no cross-app import; correctly scoped. `learner_management/utils.py`'s other two functions, `is_registered_for_course` and `ensure_learner`, both operate on `learner_management`'s own models and are called from `course_access`/`learner_interface`, which are already declared runtime dependents of `learner_management` regardless; correctly scoped. `learner_progress/utils.py` (`ensure_course_progress_record` and its neighbours) imports `learner_management` models directly for the same structural reason as the models/queries/signals files above; correctly scoped. `learner_interface/utils.py` imports only from `site_aware_models` (`get_cached_site`); correctly scoped. `form_engine` (`submissions.py`, `scoring.py`, `queries.py`) has no cross-app `freedom_ls` imports at all outside tests, matching its declared dependency row. No other misplaced module was found that would remove an edge if moved.

The one known dependency-graph distortion still on record is `SiteFactory` living in `accounts`, while `webhooks`, `site_aware_models`, and others import it only for tests (`spec_dd/1. next/debt_markdown_rendering_package_isolation/idea.md:95-103`). That spec already owns assessing and possibly relocating it; not duplicated here.

## `course_access` / `course_applications` / `course_interest`

Still three separate apps, and the split is still current in the code, not just precedent. `course_access` has no `models.py` at all; it is a pluggable backend seam only, selected by `COURSE_ACCESS_BACKEND` (`config/settings_base.py:464-466`) and resolved via `import_string`, never a direct import of `course_applications`. `course_applications/models.py:1-7,23-29` and `course_interest/models.py:1-6,23-25` each carry an explicit note committing to a specific future shape ("Application review will later add a state machine..."; "when notify-on-launch lands, this model gains a `notified_at` DateTimeField..."), and both say, in the code itself, "Do not architect these away." Nothing in the four specs that landed since the stale draft touched this boundary. No further action.

status: ok
