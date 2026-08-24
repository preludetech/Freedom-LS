---
name: second-site-form-engine-fixture
description: qa_create_site_scoping_form — a tiny form_engine tree on a second Site so Django-admin per-site filtering is observable; plus the FORCE_SITE_NAME gotcha
metadata:
  type: reference
---

`uv run python manage.py qa_create_site_scoping_form [SITE_NAME]` (positional, default `Bloom`)
creates, idempotently on `(site, slug)`, one Form (`QA Bloom Site Scoping Form` /
`qa-bloom-site-scoping-form`, QUIZ) + 1 FormPage + 1 multiple_choice FormQuestion + 2
QuestionOptions, all on the named site. Re-running prints "Already present" and writes nothing.

Command file: `freedom_ls/qa_helpers/management/commands/qa_create_site_scoping_form.py`.

## Creating site-aware data on a NON-default site from a command

- Pass `site=site` to EVERY factory call **and** pass real parent objects, so no `SubFactory`
  fires. A `SubFactory` would call `SiteAwareFactory`, whose `site` default reads the
  thread-local request — absent in a command — and would insert `site=None` (IntegrityError)
  or, with a `_site_context` in place, silently land the parent on the wrong site.
- Look rows up with `Model._base_manager`, never `Model.objects`: `SiteAwareManager.get_queryset`
  narrows to the thread-local request's site, which a command doesn't have (so it happens to
  return everything — but under a `_site_context` it would hide the row you are checking for).
- The `_site_context` / `_thread_locals.request` dance (copied in `qa_create_organisation_scenarios`)
  is only needed when something writes rows you cannot pass `site=` to (e.g. `assign_object_role`).

## Where the admin site filtering actually happens

`SiteAwareModelAdmin` only sets `exclude = ["site"]`. The filtering is done by the model's
default manager `SiteAwareManager` (admin uses `_default_manager`), fed by the thread-local
request from `CurrentSiteMiddleware`. Verified per-site counts by faking a request with
`request._cached_site = site` and `_thread_locals.request = request`.

## GOTCHA: `FORCE_SITE_NAME=DemoDev` is set in this dev environment

`freedom_ls.site_aware_models.config.config.FORCE_SITE_NAME` is `"DemoDev"` and `SITE_ID` is
`None`, so **every** browser request (any port, any host) resolves to DemoDev regardless of the
Site.domain values (DemoDev 127.0.0.1:8000, Bloom :8001, Prelude :8002, Wrend :8003). Consequence
for QA: a second-site fixture proves scoping only in the negative direction — the Bloom rows stay
invisible in admin. Seeing the Bloom changelist requires restarting the server with
`FORCE_SITE_NAME=Bloom`. Say this in the report; don't restart the tester's server.

## Proving "nothing pre-existing changed"

Snapshot `sorted(json.dumps(row) for row in Model._base_manager.filter(site__name=X).values())`
and sha256 it, before and after. **Take before/after in one back-to-back run**: the tester is
using the browser live, and `FormProgress` rows churn on their own (retake = GET start_form drops
the in-progress attempt). A first attempt showed FormProgress 20 -> 14 purely from tester
activity, not from the command.
