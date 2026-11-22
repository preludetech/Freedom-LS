# Research: UX patterns (topic `ux_patterns`)

This is a pure code move. No UI, URL, URL name or template path changes. The patterns below are the regression surface for a QA pass, not new design.

## Affected user-facing surface (confirm unchanged)

Cohort pages:
- Cohort list (CohortDataTable) and create-cohort action (`CreateCohortAction`, "add and add another" flow).
- Cohort detail `CohortInstanceView` with its `CohortTabSet`: Overview stack and Settings stack.
- Panels: details, name (inline edit form), status, staff, course completion, learners table, courses table, history.
- Cohort report page: `CohortReportStack` with the downloads panel, needs-attention panel and report body panel.
- Cohort quick view (`CohortQuickView`, `quick_views/cohort.html`).

Single actions:
- Edit cohort (name), deactivate, reactivate, delete empty cohort.
- Register cohort for course, deactivate cohort registration.
- Add existing learners, add learner to cohort.
- Generate report (`GenerateReportAction`).
- Guards: `RequiresActiveCohortMixin` and `inactive_cohort_response` (inactive cohort refuses actions), `cohort_not_empty_sentence` (delete refusal text).

Bulk actions (the four `@register_bulk_action` classes): register cohort for course, deactivate cohort registration, deactivate cohorts, reactivate cohorts. They use the course picker modal, the progress and result display, and the run history.

Report download: `cohort_report_download` and `_scoped_cohort`. `_scoped_cohort` has users in `views.py`; the spec must check before moving it.

Existing Playwright coverage to rerun: `test_create_cohort_add_and_add_another.py`, `test_cohort_settings_staff_flow.py`, `test_cohort_report_layout.py`, `test_cohort_detail_mobile.py`, `test_cohort_management_flow.py`, `test_cohort_learner_counts.py`.

## UX risks of a pure move

1. Stored bulk action runs. `BulkActionRun.action_path` is written as `f"{__module__}.{__qualname__}"` (`panel_framework/bulk_actions.py:401`) and read back with `import_string` (`bulk_runs.py:35`). A run in progress, or a finished run on the history list, whose stored path points at `educator_interface.actions.<Class>` raises ImportError after the move, so the history or progress view breaks. The data migration fixes this. QA: start a cohort bulk action before migrating, migrate, and confirm the run still shows in history and its progress or result page loads. Also confirm the reverse mapping.
2. Registry keys. The bulk registry is populated on import. If the new `panels/cohort/bulk_actions.py` is not imported at startup (for example only reachable lazily), the bulk action buttons disappear from the cohort learners or cohorts table, or POSTs to the action path 404. QA: every bulk button still appears and works on the cohort list and cohort learners table.
3. Lazy-loaded panels. `CohortNeedsAttentionPanel` and `CohortReportBodyPanel` are `LazyBodyPanel` regions fetched by a URL or panel path. If the lazy region URL encodes a dotted panel path, the move could change it. The spec must confirm region URLs and `render_region` still resolve. QA: open the report page and watch both regions load, with no stuck placeholder.
4. Report download link. The URL name and path stay the same, but `urls.py` imports the view from the new module. QA: the download link in `CohortReportDownloadsPanel` still returns the file, and a cohort from another organisation still gives 404.
5. Modal and HTMX targets. Panel ids, action URLs and 422 error rendering come from class names or module paths in places. Check nothing derives a DOM id or a URL token from `__module__`. QA: edit-name inline form, deactivate and delete confirmation modals, and validation errors (422) still render in place.
6. Permissions. Each moved action keeps its permission check. QA: an educator without the permission still sees no button and gets a refusal on direct POST.
7. Silent mock.patch breakage (test-side, not UX) can hide a regression. Run the full tests, not grep.

## Verdict

No new UX. QA is a smoke pass over the list above, plus the in-flight bulk run check, which is the one real behavioural risk.

status: ok
