---
name: second-site-form-engine-fixture
description: qa_create_site_scoping_form — a form_engine + learner_progress tree on a second Site so Django-admin per-site filtering is observable; plus the FORCE_SITE_NAME gotcha
metadata:
  type: reference
---

`uv run python manage.py qa_create_site_scoping_form [SITE_NAME]` (positional, **default `Demo`**).
Idempotent on `(site, slug)` / user email; a re-run prints `kept` for every row and writes nothing.

Command file: `freedom_ls/qa_helpers/management/commands/qa_create_site_scoping_form.py`.

## What it builds (all on the target site)

    Form "ZZ OTHER SITE Site Scoping Form" -> FormPage -> FormQuestion -> 2 QuestionOptions
    Course "ZZ OTHER SITE Site Scoping Course" -> ContentCollectionItem placing the Form
    User zz_other_site_<sitename>@email.com / testpass123 -> Learner (site's DEFAULT org)
      -> LearnerCourseRegistration -> CourseProgress (minted by the signal)
      -> CourseFormAttempt -> FormProgress (left in progress on purpose)

The `ZZ ` prefix sorts the rows to the end of any changelist. Titles are site-independent, but the
email folds in the site name because `User.email` is **globally** unique (not per-site) — seeding a
second site would otherwise reuse the first site's user and hang the tree on the wrong site.

The command ends by asserting every created row's `site_id` matches, and raises if not.

## Creating site-aware data on a NON-default site from a command

- Pass `site=site` to EVERY factory call **and** pass real parent objects. Since **2c2b5e35**
  `CourseFormAttemptFactory` / `TopicProgressFactory` DO forward the parent's `site` to their
  `form_progress` / `collection_item` sub-factories (`site=factory.SelfAttribute("..site")`), so the
  old `form_progress__site=site` workaround is no longer needed on this branch — verified: the
  nested `FormProgress` and `ContentCollectionItem` both came out on site 2.
- Look rows up with `Model._base_manager`, never `Model.objects`.
- `Learner` takes its site from `organisation.site` (`ensure_learner`), so use the target site's
  **default** Organisation (`Organisation._base_manager.get(site=site, is_default=True)`), which
  exists for every Site in this DB. Passing `site=` to `LearnerFactory` alone is not enough.
- Never hand-create `CourseProgress`: create the `LearnerCourseRegistration` and read the record
  back with `CourseProgress._base_manager.get(learner=..., learner_registration=...)`. Under
  autocommit the `on_commit` mint has already run when the factory call returns.

## Where the admin site filtering actually happens

`SiteAwareModelAdmin` only sets `exclude = ["site"]`. The filtering is done by the model's default
manager `SiteAwareManager` (admin uses `_default_manager`), fed by the thread-local request.
Simulate a changelist without touching the tester's server:

```python
with override_settings(FORCE_SITE_NAME="Demo"):
    request = RequestFactory().get("/admin/"); request.user = <staff>
    _thread_locals.request = request
    admin.site._registry[Form].get_queryset(request)
```

## GOTCHA: `FORCE_SITE_NAME=DemoDev` is hardcoded in `config/settings_dev.py`

`SITE_ID` is None and `config/settings_dev.py:107` sets `FORCE_SITE_NAME = "DemoDev"`, so **every**
browser request (any port, any host) resolves to DemoDev regardless of Site.domain. Consequence: a
second-site fixture proves scoping only in the NEGATIVE direction — the other site's rows stay
invisible in the DemoDev admin, which is exactly what "the check is vacuous" asks for. Seeing the
other site's changelist requires restarting the server with `FORCE_SITE_NAME=<name>`. Say this in
the report; don't restart the tester's server.

## Proving "nothing pre-existing changed"

Snapshot `sorted(json.dumps(row) for row in Model._base_manager.filter(site__name=X).values())`
and sha256 it, before and after, **back-to-back in one run**. The tester is browsing live and
DemoDev `FormProgress` / `CourseFormAttempt` counts churn on their own — on the Aug 2026 run they
moved 18 -> 20 during the seeding purely from tester quiz activity. Attribute deltas by comparing
`FormProgress.start_time` against the fixture row's own timestamp before claiming or denying blame.
