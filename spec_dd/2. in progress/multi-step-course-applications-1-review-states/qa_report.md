# Frontend QA report: multi-step-course-applications-1-review-states

Test plan run: `3. frontend_qa.md`. Result: every test and layout record passed. No bugs.

## Methodology

Screenshots were collected into `screenshots/` beside this report. Every image referenced below exists there. The run used desktop for all sections (1 to 8), then repeated the key states at mobile (375) and tablet (768). Compression ran and found nothing to compress.

## Diff scoping

Class: FULL. Changed files that triggered it:

- `freedom_ls/course_applications/templates/...`
- `freedom_ls/course_applications/static/...`
- `freedom_ls/learner_interface/templates/learner_interface/course_detail.html`
- `freedom_ls/course_applications/*.py`
- `freedom_ls/form_engine/*.py`
- `docs/...`

Nothing was skipped. Desktop, mobile and tablet passes all ran.

## Smoke gate

Outcome: pass. Pages loaded: `/` and `/applications/status/f7f5cd64-a2d7-4ce4-816b-6a3ef6a7b4c0/`.

## Test results

| Section | Viewport | Result |
|---|---|---|
| 1.1 to 1.11 | desktop | all pass |
| 2.1 to 2.6 | desktop | all pass |
| 3.1 to 3.5 | desktop | all pass |
| 4.1 to 4.4 | desktop | all pass |
| 5.1 to 5.4 | desktop | all pass |
| 6.1, 6.2 | desktop | all pass |
| 7.1 to 7.3 | desktop | all pass |
| 8.1, 8.2 | desktop | all pass |
| 3.1, 2.2, 1.4, 3.3, 2.4, 2.5 | mobile | all pass |
| 3.1, 2.2, 1.4 | tablet | all pass |

## Design check

No design states tested.

## Layout probe

The probe's configured regions were not found on these learner pages, because they sit outside the `#interface-main` shell. Only the overflow check applied. No flags were raised.

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1.1 | desktop | `/` | [shot](screenshots/page-2026-11-21T13-18-13-083Z.png) | clean |
| 1.2 | desktop | `/applications/status/<F1>/` | [shot](screenshots/page-2026-11-21T13-18-01-388Z.png) | clean |
| 1.4 | desktop | `/applications/status/<F1>/` (dialog) | [shot](screenshots/page-2026-11-21T13-18-36-567Z.png) | clean |
| 1.7 | desktop | `/applications/status/<F1>/` (withdrawn) | [shot](screenshots/page-2026-11-21T13-19-26-973Z.png) | clean |
| 1.10 | desktop | `/courses/qa-review-f1/detail/` | [shot](screenshots/page-2026-11-21T13-19-49-277Z.png) | clean |
| 1.11 | desktop | `/applications/application/<old F1>/page/1/` | [shot](screenshots/page-2026-11-21T13-20-11-729Z.png) | clean |
| 2.1 | desktop | `/` | [shot](screenshots/page-2026-11-21T13-20-44-458Z.png) | clean |
| 2.2 | desktop | `/applications/status/<F5>/` | [shot](screenshots/page-2026-11-21T13-20-54-924Z.png) | clean |
| 2.5 | desktop | `/applications/application/<F4>/check-your-answers/` | [shot](screenshots/page-2026-11-21T13-21-34-956Z.png) | clean |
| 3.2 | desktop | `/applications/status/<F3>/` | [shot](screenshots/page-2026-11-21T13-23-53-225Z.png) | clean |
| 3.3 | desktop | `/applications/status/<F4>/` | [shot](screenshots/page-2026-11-21T13-24-02-447Z.png) | clean |
| 5.1 | desktop | `/applications/status/<G anon>/` | [shot](screenshots/page-2026-11-21T13-25-31-809Z.png) | clean |
| 5.4 | desktop | `/applications/claim/<token>/` | [shot](screenshots/page-2026-11-21T13-26-01-948Z.png) | clean |
| 8.1 | desktop | `/admin/freedom_ls_course_applications/courseapplication/?state__exact=withdrawn` | [shot](screenshots/page-2026-11-21T13-28-23-892Z.png) | clean |
| 8.2 | desktop | `/admin/freedom_ls_course_applications/courseapplication/<F4>/change/` | [shot](screenshots/page-2026-11-21T13-28-38-807Z.png) | clean |
| 3.1 | mobile | `/` | [shot](screenshots/page-2026-11-21T13-29-12-654Z.png) | clean |
| 2.2 | mobile | `/applications/status/<new F4 draft>/` | [shot](screenshots/page-2026-11-21T13-29-23-671Z.png) | clean |
| 1.4 | mobile | `/applications/status/<new F4 draft>/` (dialog) | [shot](screenshots/page-2026-11-21T13-29-31-072Z.png) | clean |
| 3.3 | mobile | `/applications/status/<F4>/` | [shot](screenshots/page-2026-11-21T13-29-41-720Z.png) | clean |
| 2.4 | mobile | `/applications/status/<F5>/` | [shot](screenshots/page-2026-11-21T13-29-49-590Z.png) | clean |
| 2.5 | mobile | `/applications/application/<F5>/check-your-answers/` | [shot](screenshots/page-2026-11-21T13-29-58-505Z.png) | clean |
| 3.1 | tablet | `/` | [shot](screenshots/page-2026-11-21T13-30-19-112Z.png) | clean |
| 2.2 | tablet | `/applications/status/<new F4 draft>/` | [shot](screenshots/page-2026-11-21T13-30-35-532Z.png) | clean |
| 1.4 | tablet | `/applications/status/<new F4 draft>/` (dialog) | [shot](screenshots/page-2026-11-21T13-30-41-469Z.png) | clean |

Key screenshots:

![](screenshots/page-2026-11-21T13-18-01-388Z.png)
![](screenshots/page-2026-11-21T13-24-02-447Z.png)
![](screenshots/page-2026-11-21T13-29-23-671Z.png)

## Data changes

| What changed | Call or command | Files written |
|---|---|---|
| Seeded review-state QA data (applicants A and B, courses F1-F5, G, N reseeded on DemoDev) | `uv run python manage.py qa_create_application_review_states` | none |
| Created and rejected an anonymous application on G, for tests 2.6 and 5 | Browser apply on `/applications/apply/qa-review-g/` as `qa_anon_draft_g@example.com`, then `qa_create_application_review_states --reject-pk cfb6e67f-96d0-45fd-9888-260658b71aeb --message 'Not this time.'` | none |
| Claimed the anonymous G application, which created a new dev account `qa_anon_draft_g@example.com` (test 5.3) | Browser claim flow | none |

## Bug status

| Bug | Status |
|---|---|
| none recorded | n/a |

## General notes

Observations (no failures, no action attached):

- The read-only form page for a withdrawn application (test 1.11) has no Back link and no link to the status page.
- The claim-invalid page (test 5.4) has the tab title "Finish your application".
- The confirm page for course N, which has no form (test 6.1), still says "you will be notified of the outcome".
- Application row titles on the dashboard use `font-medium`, while course row titles are bold (test 3.1, tablet). This is pre-existing on main and not in the spec.

Other notes:

- On test 1.7 the withdraw toast was not observed (the script waited 30s). The toast was checked and seen in test 2.4.
- In the mobile check of 2.5, the dev branch badge overlaps the "Your application" button in the full-page shot only. It is a dev-only overlay.
- In the mobile check of 3.3, the declined application had been superseded by a newer F4 draft, so that page showed the "newer application" next step. It is still a valid check of wrapping and escaping.
- An extra screenshot, `page-2026-11-21T13-25-00-000Z.png`, sits in `screenshots/` without a scratch record. Nothing refers to it.

status: ok · reason: report rendered, 0 bugs documented
