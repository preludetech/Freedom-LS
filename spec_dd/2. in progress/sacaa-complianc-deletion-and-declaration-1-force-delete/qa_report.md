# QA report: force delete and last active

## Methodology

Screenshots were collected into `screenshots/` beside this report. Every image referenced below exists there. The plan is `3. frontend_qa.md`. Tests 1 to 10 ran on desktop. Test 2 and Test 10 also ran at mobile (375px) and tablet (768px). The run did not abort.

## Diff scoping

Class: **FULL**. Skipped: nothing. Everything ran.

The changed files that triggered it span accounts (admin, middleware, models, migration 0006), api_admin, audit_log, course_applications, deadlines, educator_interface learner panels and templates, form_engine and revision admin, learner_progress (force delete, its admin, its confirm template, migration 0004), site_aware_models admin, config settings and test organisation files. The full list is in the `scoping` record in `.sdd-work/qa_scratch.jsonl`.

## Smoke gate

Outcome: **pass**. Pages loaded: `/` and `/admin/freedom_ls_accounts/user/`.

## Design check

no design states tested

## Test results

| Test | Viewport | Result | Screenshot |
|---|---|---|---|
| 1 User admin has no ordinary delete | desktop | pass | ![](screenshots/page-2026-11-26T05-04-51-976Z.png) |
| 2 Force delete a bare user | desktop | pass overall; see B1, B2, B4 | ![](screenshots/page-2026-11-26T05-05-05-556Z.png) |
| 2 Force delete a bare user | mobile | pass | ![](screenshots/page-2026-11-26T05-13-32-856Z.png) |
| 2 Force delete a bare user | tablet | pass | ![](screenshots/page-2026-11-26T05-13-49-092Z.png) |
| 3 Two-organisation user | desktop | pass on counts and audit; see B2, B3 | ![](screenshots/page-2026-11-26T05-08-28-547Z.png) |
| 4 Applications found by email | desktop | pass (claimed-applicant line skipped) | ![](screenshots/page-2026-11-26T05-09-17-606Z.png) |
| 5 Several users at once | desktop | pass | ![](screenshots/page-2026-11-26T05-09-59-200Z.png) |
| 6 Staff non-superuser | desktop | pass | none |
| 7 Read-only Learner admin | desktop | pass | ![](screenshots/page-2026-11-26T05-11-06-762Z.png) |
| 8 Superuser deletes own account | desktop | pass | ![](screenshots/page-2026-11-26T05-11-55-090Z.png) |
| 9 Last active in user admin | desktop | pass | ![](screenshots/page-2026-11-26T05-04-51-976Z.png) |
| 10 Last active in educator pages | desktop | pass | ![](screenshots/page-2026-11-26T05-12-53-244Z.png) |
| 10 Last active in educator pages | mobile | pass | ![](screenshots/page-2026-11-26T05-13-41-657Z.png) |
| 10 Last active in educator pages | tablet | pass | ![](screenshots/page-2026-11-26T05-13-51-615Z.png) |

## Bugs

### B1: Force delete page: Reason label sits beside the textarea at desktop width

Manifestations: `2-reason-label` (desktop).

![](screenshots/page-2026-11-26T05-05-05-556Z.png)
![](screenshots/page-2026-11-26T05-05-23-739Z.png)

- Expected: the "Reason" label sits above the textarea, as it does at mobile and tablet widths.
- Actual: at 1920px the label renders inline to the left of the textarea, aligned to its bottom edge.

### B2: Force delete page: model row names are lower case and sorted case-sensitively

Manifestations: `2-model-names` (desktop), `3-model-names` (desktop).

![](screenshots/page-2026-11-26T05-05-05-556Z.png)
![](screenshots/page-2026-11-26T05-09-59-200Z.png)

- Expected: each row reads as a sentence-case name with its count (e.g. "Learners (2)", "Course progress records (2)"), sorted alphabetically regardless of case.
- Actual: rows use the raw `verbose_name_plural` ("email addresses (1)", "users (1)"). "Form progress records", which is capitalised in its model, sorts first and the rest are lower case.

### B3: Force delete page lists Django's auto-created many-to-many join rows as "questionanswer-questionoption relationships"

Manifestations: `3-model-names` (desktop).

![](screenshots/page-2026-11-26T05-09-59-200Z.png)

- Expected: every listed row is a record an operator can recognise.
- Actual: a row "questionanswer-questionoption relationships (5)" shows the internal join table of QuestionAnswer's selected options.

### B4: Force delete page: disclosure chevron does not turn up when a row opens

Manifestations: `2-chevron` (desktop).

![](screenshots/page-2026-11-26T05-05-30-725Z.png)

- Expected: opening a model row turns its chevron up (`group-open:rotate-180`).
- Actual: the icon carries `group-open:rotate-180` inside `details.group`, but no stylesheet loaded on the admin page defines that utility, so the computed transform stays none.

## Layout probe

| Test id | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1 | desktop | /admin/freedom_ls_accounts/user/ | ![](screenshots/page-2026-11-26T05-04-44-716Z.png) | clean |
| 1 | desktop | /admin/freedom_ls_accounts/user/81/change/ | ![](screenshots/page-2026-11-26T05-04-51-976Z.png) | clean |
| 3 | desktop | /admin/freedom_ls_accounts/user/force-delete/ | ![](screenshots/page-2026-11-26T05-08-28-547Z.png) | clean |
| 3 | desktop | /educator/organisations/demodev/audit-log | ![](screenshots/page-2026-11-26T05-09-06-102Z.png) | clean |
| 4 | desktop | /admin/freedom_ls_accounts/user/force-delete/ | ![](screenshots/page-2026-11-26T05-09-17-606Z.png) | clean |
| 5 | desktop | /admin/freedom_ls_accounts/user/force-delete/ | ![](screenshots/page-2026-11-26T05-09-59-200Z.png) | clean |
| 7 | desktop | /admin/freedom_ls_learner_management/learner/ | ![](screenshots/page-2026-11-26T05-10-46-386Z.png) | clean |
| 7 | desktop | /admin/freedom_ls_learner_management/learner/<id>/change/ | ![](screenshots/page-2026-11-26T05-11-06-762Z.png) | clean |
| 7 | desktop | /admin/freedom_ls_learner_management/learner/force-delete/ | ![](screenshots/page-2026-11-26T05-11-13-370Z.png) | clean |
| 8 | desktop | /admin/freedom_ls_accounts/user/force-delete/ | ![](screenshots/page-2026-11-26T05-11-55-090Z.png) | clean |
| 10 | desktop | /educator/organisations/demodev/learners | ![](screenshots/page-2026-11-26T05-12-53-244Z.png) | clean |
| 10 | desktop | /educator/organisations/demodev/learners (quick view) | ![](screenshots/page-2026-11-26T05-13-01-511Z.png) | clean |
| 10 | desktop | /educator/organisations/demodev/learners/<id> | ![](screenshots/page-2026-11-26T05-13-08-406Z.png) | clean |
| 2 | mobile | /admin/freedom_ls_accounts/user/force-delete/ | ![](screenshots/page-2026-11-26T05-13-32-856Z.png) | clean |
| 10 | mobile | /educator/organisations/demodev/learners | ![](screenshots/page-2026-11-26T05-13-41-657Z.png) | clean |
| 10 | mobile | /educator/organisations/demodev/learners/<id> | ![](screenshots/page-2026-11-26T05-13-38-790Z.png) | clean |
| 2 | tablet | /admin/freedom_ls_accounts/user/force-delete/ | ![](screenshots/page-2026-11-26T05-13-49-092Z.png) | clean |
| 10 | tablet | /educator/organisations/demodev/learners | ![](screenshots/page-2026-11-26T05-13-51-615Z.png) | clean |

The layout probe's flags are empty for every record. B1 to B4 were found by the functional tests, not by the probe.

## Data changes

| What changed | Made by | Files written |
|---|---|---|
| Dev DB was empty. Ran `create_demo_data --yes` and `content_save ./demo_content DemoDev`, then the three QA seed commands | management commands | none |
| Added the seed command `qa_create_force_delete_users` (two-org users, applicant, second superuser, stale and never-active learners) and ran it | QA data helper | `freedom_ls/qa_helpers/management/commands/qa_create_force_delete_users.py` |
| Re-ran `qa_create_force_delete_users` to recreate `qa_fd_super` (deleted in Test 5) for Test 8 | `qa_create_force_delete_users` | none |

The tests themselves force deleted users and learners in the dev DB, as the plan intends.

## Bug status

| Bug | Title | Status |
|---|---|---|
| B1 | Reason label sits beside the textarea at desktop width | **FIXED** (commit: e450ff3eb) |
| B2 | Model row names are lower case and sorted case-sensitively | **FIXED** (commit: f0c08de6e; test expectation follow-up b15b60632) |
| B3 | Auto-created many-to-many join rows listed as "questionanswer-questionoption relationships" | **UNRESOLVED** (reason: hiding the join rows or naming them is a product decision about what the page should count) |
| B4 | Disclosure chevron does not turn up when a row opens | **FIXED** (commit: e8aeea5f2) |

## General notes

- Test 4: the claimed-applicant wording line was skipped. The dev data has no claimed anonymous applicant, and the plan makes this line conditional. Automated tests cover it.
- Test 5: a blocked delete cannot be produced from the dev data, per the plan. It was not run here.
- Test 6 has no screenshot, because the pages answer 403.
- Test 2: the audit admin shows raw action codes (`user.deleted`) for every action. The scratch notes call this pre-existing. The plan expects "User force deleted" there, so the wording differs from the plan's checklist.
- Test 9: sorting by Last active descending puts nulls first, which is the PostgreSQL default.
- Untracked files at start: the seed command and the `screenshots/` directory.
- Screenshots `page-2026-11-26T05-04-37-943Z.png`, `05-05-56-713Z`, `05-09-51-835Z`, `05-10-52-510Z` and `05-11-58-947Z` are in the folder but no record references them.

status: ok · reason: 4 bugs — 3 fixed, 1 unresolved; report rendered, screenshots verified
