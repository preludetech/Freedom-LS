# Idea: every FLS app section in the Django admin is titled with its raw app label

## The bug

Source: `system_qa/07_fls_recent_features/qa_report.md`, test P2-D1 — a high-level QA sweep of the
six most recent FLS features against this project.

The `extract_forms_into_seperate_app` QA plan, Section D, states the expected outcome plainly:

> **Expect a new "Form engine" section** containing: Forms, Form pages, Form contents, Form
> questions, Question options, Form progress records, Question answers.

The models are all in the right place — that half of the move landed correctly. But the section is
titled **`Freedom_Ls_Form_Engine`**, not "Form engine". The same applies to every FLS app, on both
the admin index and the sidebar:

```
Freedom_Ls_Accounts        Freedom_Ls_Course_Interest      Freedom_Ls_Organisations
Freedom_Ls_Content_Engine  Freedom_Ls_Form_Engine          Freedom_Ls_Reports
Freedom_Ls_Course_Applications  Freedom_Ls_Learner_Management   Freedom_Ls_Learner_Progress
```

The third-party sections on the same page render normally — "Accounts", "Axes", "Webhooks", "Tasks
Database Backend" — which is what makes the FLS ones look broken rather than merely verbose.

**Root cause:** no FLS `AppConfig` sets `verbose_name`. Django's `AppConfig.verbose_name` defaults
to `self.label.title()`, and FLS deliberately prefixes every label to avoid collisions downstream:

```python
class FormEngineConfig(AppConfig):
    name = "freedom_ls.form_engine"
    label = "freedom_ls_form_engine"     # -> "Freedom_Ls_Form_Engine".title()
```

So the label prefix that buys downstream safety is also what disfigures the admin, and nothing
compensates for it. `git grep 'verbose_name' -- 'freedom_ls/*/apps.py'` returns nothing.

This is cosmetic, not functional — no data is wrong and nothing 500s. But the admin is the
educator- and operator-facing surface, and "Freedom_Ls_Learner_Management" is not a label anyone
should be shown. It also means the `extract_forms` QA plan's Section D can never pass as written.

## Expected fix

Set `verbose_name` on each `AppConfig` in `freedom_ls/*/apps.py` — `"Form engine"`,
`"Content engine"`, `"Learner management"`, `"Learner progress"`, `"Organisations"`, `"Reports"`,
`"Accounts"`, `"Course applications"`, `"Course interest"`. Cheap, local, and independent per app.

Worth deciding at the same time whether these should carry a shared prefix (e.g. "FLS · Form
engine") so a downstream project can tell FLS's admin sections from its own at a glance — several
of the plain names ("Accounts", "Reports") would otherwise collide visually with third-party apps
already in the list. That is a product call, not a mechanical one.

## Sources

- `submodules/Freedom-LS/freedom_ls/form_engine/apps.py` — lines 1-10, no `verbose_name`; same
  shape in `content_engine/apps.py`, `learner_management/apps.py`, `learner_progress/apps.py`,
  `organisations/apps.py`, `reports/apps.py`, `accounts/apps.py`.
- `submodules/Freedom-LS/spec_dd/3. done/2026-08-24_20:56_extract_forms_into_seperate_app/3. frontend_qa.md`
  — Section D, step 2, which states the expected "Form engine" heading.
