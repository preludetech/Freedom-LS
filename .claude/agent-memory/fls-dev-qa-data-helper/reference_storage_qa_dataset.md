---
name: reference-storage-qa-dataset
description: The full dev-DB dataset the prod_bucket_setup (object-storage alias) browser QA needs, plus how to repair a GeneratedReport row and why --num-flagged undercounts on a quiz-less course
metadata:
  type: reference
---

Set up twice now (Aug 2026). Everything below is on site **DemoDev**.

## The recipe

```
uv run python manage.py content_save demo_content/functionality_demo_content_widgets DemoDev
uv run python manage.py content_save demo_content/functionality_demo_end_with_topic DemoDev
uv run python manage.py qa_create_organisations DemoDev          # RPAS Training (logo) + Northside (no logo)
uv run python manage.py qa_register_org_course --learner-email demodev@email.com \
    --organisation "RPAS Training" --course-slug content-widgets-demo-reference
uv run python manage.py qa_register_org_course --learner-email demodev@email.com \
    --organisation "Northside" --course-slug functionality-demo-show-end-with-topic
uv run python manage.py qa_create_report_cohort --cohort-name "QA Storage Cohort" \
    --num-learners 9 --course-slug functionality-demo-show-end-with-topic \
    --num-flagged 3 --educator-email qa-educator@email.com
uv run python manage.py qa_create_report_cohort --cohort-name "QA Other Cohort" \
    --num-learners 5 --course-slug functionality-demo-show-end-with-topic \
    --email-prefix qa-other-learner        # NO --educator-email: this is the forbidden cohort
```

`content_save` prints NOTHING on success (exit 0). Silence is not failure.

`qa_create_report_cohort` does **not** set `is_staff` on `--educator-email`; it grants only a
guardian `view_cohort` on the one cohort and `view_generatedreport`. Set `is_staff=True` yourself.
Password is `== email`.

## GOTCHA: `--num-flagged 2` yields only ONE flag on a quiz-less course

`_learner_states` cycles flavours `[no_activity, failing, stale]`. The `failing` flavour needs a
**pass-marked QUIZ** in the course to produce `failed_latest_quiz`; if the course has none, that
learner silently gets ordinary progress and no flag.

`functionality-demo-show-end-with-topic` has 7 items and its only Form is a
`CATEGORY_VALUE_SUM` survey with `quiz_pass_percentage=None`.
`content-widgets-demo-reference` has 5 topics and zero forms.

So on either demo course, pass **`--num-flagged 3`** to actually get 2 flags
(`no_activity` + `inactive`). Verify with `gather_cohort_report_data(...).learners[i].flags`.

Re-running the command will NOT retro-fit a flag: `_has_existing_progress` short-circuits any
learner who already has rows. To change a learner's flavour, delete that learner's
`TopicProgress` / `FormProgress` / `CourseProgress` for the course first, then re-run — do not
hand-edit timestamps.

## Repairing a GeneratedReport row instead of hand-copying files

`freedom_ls.reports.tasks.generate_cohort_report(report_id, site_id)` is a plain function
(the `@task()` wrapper `_generate_cohort_report_task` just delegates). Calling it in the shell
re-renders an **existing** row in place: same pk, same filename, and `file.save()` re-runs
`report_upload_path` so the key is rewritten to the CURRENT prefix. That is the clean way to
un-stage a legacy `reports/` row or to heal a `ready` row whose PDF was deleted.

To add an extra ready report:
```python
r = GeneratedReport.objects.create(cohort=cohort, site_id=cohort.site_id, requested_by=superuser)
generate_cohort_report(str(r.pk), site.pk)
```
The `one_inflight_report_per_cohort` unique index only covers `pending`/`running`, so a cohort
may hold any number of `ready` rows. Rendering resolves CSS through the staticfiles **finders**,
so no `collectstatic` and no `staticfiles/` dir appears. Reports are ~400-500 KB.

## Where each thing is visible

- org logo / monogram: **player sidebar only**, `/courses/<slug>/1/` — see [[reference_org_course_registration]]
- report download: `/admin/freedom_ls_reports/generatedreport/<pk>/download/`
- the download's gate is `can_view_cohort` -> `all_cohorts_visible_to`, which ORs
  guardian `view_cohort` on the Cohort with guardian `view_organisation` on its Organisation.
  Both QA cohorts sit in the **DemoDev** org, so a `view_organisation` grant there would silently
  defeat the per-cohort boundary. Grant neither that nor the global model-level
  `learner_management.view_cohort` (guardian returns everything to a global-perm holder).
