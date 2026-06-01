# Multi-step Application Forms — Research

Companion to `0. idea.md`. Focuses on multi-step ("wizard") UX, common complaints, and concrete Django/HTMX implementation patterns for the FLS course-application feature.

Key requirements re-stated:
- Application can have multiple steps (no wall-of-text single form)
- User can edit/correct after submission errors
- Different courses configure different steps/questions
- FLS stack: Django 6.x, HTMX 2.x, TailwindCSS

## 1. UX best practices

### 1.1 When wizards beat one-pagers
- **NN/G** ("Wizards"): wizards win for novice/infrequent users and complex configurations; lose for repeated/expert tasks. (https://www.nngroup.com/articles/wizards/)
- **GOV.UK Service Manual** is more opinionated: start with **one thing per page** (one question/decision/piece of info). Easier comprehension, easier mobile, easier error recovery, enables per-page auto-save. (https://www.gov.uk/service-manual/design/form-structure, https://design-system.service.gov.uk/patterns/question-pages/)
- **Baymard** (25+ rounds, 4,400+ checkout sessions): multi-step is *not* the source of usability problems; what's asked at each step is. ~26% abandon checkouts that "feel too long/complex"; cure is fewer fields per step, not fewer steps. (https://baymard.com/research/checkout-usability)
- For an LMS application with mixed content (questions, locations, document uploads), multi-step is the right default — uploads especially need their own visual room.

### 1.2 Progress indicators that work
- Show **all steps from the start**, current highlighted, future greyed; numbered + descriptive labels. Mystery dots are an anti-pattern. (NN/G; https://www.growform.co/must-follow-ux-best-practices-when-designing-a-multi-step-form/)
- Replace generic "Next/Previous" with action-labelled buttons ("Continue to documents", "Review your answers"). NN/G specifically calls these out as having weak information scent.
- GOV.UK insists button is literally labelled "Continue" (not "Next"), left-aligned. (https://design-system.service.gov.uk/patterns/question-pages/)

### 1.3 Save & continue later
- >67% will abandon on any complication; ~24% abandon multi-step specifically due to unclear completion status. (https://www.formassembly.com/blog/multi-step-form-best-practices/, https://www.reform.app/blog/10-best-practices-for-multi-step-form-navigation)
- Auto-save **per step** on advance is the minimum bar.
- Drafts must survive logout / device switch — store on the user account.
- Fixing back-button data clobber alone gives "up to 10%" conversion uplift. (https://www.zuko.io/blog/single-page-or-multi-step-form)

### 1.4 Back navigation and edit-after-submit
- NN/G heuristic #3 (User Control and Freedom): back/undo/exit are expectations. (https://www.nngroup.com/articles/user-control-and-freedom/)
- Baymard: 59% of sites violate back-button expectations; the most damaging pattern is breaking the browser back button. Each step should be a real URL. (https://baymard.com/blog/back-button-expectations)
- Dominant edit-after-submit pattern is **GOV.UK "Check your answers"**: summary cards per section, "Change" link per card pre-populates that step, "Continue" returns directly to check-answers (NOT through later steps). Optional answers shown as "Not provided". Submit button action-labelled. If a change invalidates later answers (branching), walk the user through the now-relevant later questions before returning to check-answers. Carer's Allowance Service evidenced reduced error rates. (https://design-system.service.gov.uk/patterns/check-answers/, https://service-manual.ons.gov.uk/design-system/patterns/check-answers)

### 1.5 Validation timing
- Per-field on blur for high-friction fields (email, file size/type), per-step before advance, no re-validation of completed steps unless their inputs changed. (Baymard)

### 1.6 Mobile
- One-thing-per-page is GOV.UK's mobile-justified default. Each step should fit a mobile viewport with the action button visible. Use native `<input type="file">` (invokes camera/gallery). Collapse the indicator to "Step 2 of 5: Documents".

### 1.7 Real-world references
- **GOV.UK**: Check Answers pattern, sectioned, change-link per section.
- **Common App**: persistent left-rail with green ticks per section; "Review & Submit" lists every answer with edit links; per-field server-side autosave.
- **UCAS**: sectioned with preview before send; centre/adviser can return-for-edit — direct analogue for FLS's admin "needs changes". (https://www.ucas.com/applying/after-you-apply/making-changes-to-your-application-after-you-apply, https://www.ucas.com/advisers/help-and-training/guides-resources-and-training/application-overview/our-adviser-portal/managing-applications-in-the-adviser-portal)

## 2. Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Browser back loses field values | Persist server-side; pre-populate from draft. |
| Mystery dots / "Step 3 of ?" | Numbered + labelled, all visible, current highlighted. |
| Forced linear flow to fix step 1 | Check Answers with per-section Change links returning directly to review. |
| Re-validating completed steps | Only re-validate steps whose inputs changed. |
| File upload with no preview/replace | Filename, size, thumbnail, Replace, Remove. (https://uploadcare.com/blog/file-uploader-ux-best-practices/, https://designsystem.digital.gov/components/file-input/) |
| Opaque upload progress | Progress bar + success state. |
| Session timeout discards everything | DB-backed drafts tied to user. |
| Hidden inputs carrying earlier-step data forward | Brittle, breaks on files. Use server-side draft. |
| Generic "Next" buttons | Action-labelled. |
| Submit hidden at end of long check-answers | Action-labelled, clear placement. |
| No "save & exit" affordance | Visible link on every step. |
| Cookie wizard state | 4 KB silent failure; SECRET_KEY rotation breaks all in-flight. (https://github.com/jazzband/django-formtools/issues/45, https://code.djangoproject.com/ticket/22638) |

## 3. Django implementation patterns

### 3.1 django-formtools `WizardView` family
Strengths: out-of-the-box step ordering, validation, navigation; pluggable storage; file-upload adapter. (https://django-formtools.readthedocs.io/en/latest/wizard.html)

Limitations:
- Single endpoint for all steps — each step doesn't get its own URL → poor browser back/forward and bookmarkability.
- Default storages: Session (lost on logout) and Cookie (4 KB silent failure; SECRET_KEY rotation = 500 error).
- "Edit step N from review then return to review" is not first-class; `render_goto_step()` exists but the round-trip is awkward.
- Dynamic per-course form lists require `get_form_list()` overrides — workable but fiddly. (https://code.djangoproject.com/ticket/17850)
- File handling needs `file_storage` + temporary-file dance.

### 3.2 Persisted-draft pattern (recommended)
- A `CourseApplication` model with status field; per-step responses stored as `{question_id: value}` in JSONField (or a related `ApplicationResponse` table) plus `FileField`s for uploads.
- Each step is a real GET URL pre-populated from the model. Auto-save on advance is just `application.save()`. Edit-from-review is a normal GET/POST + redirect-to-review. Browser back, refresh, device switch all just work. Multi-tenancy/permissions become normal ORM concerns.
- Mid-flight schema changes are absorbed by `{question_id: value}` storage — no migrations needed when courses change their question set.
- This is essentially what Common App, UCAS, and GOV.UK Forms (https://www.forms.service.gov.uk/features) do.

### 3.3 Per-step views with HTMX — URL design
Two viable options:

A. **One URL per step** (recommended)
- `GET/POST /applications/<id>/step/<slug>/`. POST validates, saves, 303-redirects to next step or review.
- HTMX used *inside* the step (inline validation → 422 partials per FLS conventions, file upload progress, conditional question reveal), not for whole-step swaps.
- Browser back, refresh, bookmarks all work.

B. **Single URL, hx-swap whole steps** — fragile, no real benefit. Reject.

### 3.4 Edit-from-review without losing later steps
- "Change" link → `GET .../step/<slug>/?return=review`. POST handler honours `?return=review` and redirects there instead of advancing. Steps 3+ untouched in DB.
- Branching exception per GOV.UK: if change invalidates later answers, walk the user through newly-relevant questions before returning to review; do not silently drop now-irrelevant answers.

### 3.5 Per-course step configuration
- **Question-bank model** (recommended): `Course → ApplicationStep[] → ApplicationQuestion[]` with question types; responses in `ApplicationResponse(application, question, value, file)`. Mirrors content_engine.
- Form-class registry — fast but requires deploys to add courses. Reject.

### 3.6 File upload UX
- Native `<input type="file">`. On change, hx-post to a sub-endpoint that saves to FileField and returns a partial showing filename + size + thumbnail + Replace/Remove. `accept=` for client-side filtering, server-side re-validation. Progress via `htmx:xhr:progress`.

### 3.7 Status / admin loop
- `draft → submitted → under_review → (needs_changes ↔ submitted) → approved | rejected`.
- `needs_changes` re-opens edits; admin notes attach to specific steps (render on relevant step page, not just at the top).
- Approval does NOT auto-enrol (per idea); admin manually adds approved learners to a cohort.

## 4. Submission / review pattern

GOV.UK "Check your answers" as the final step:
- Summary card per step with question + answer; uploaded files show filename + thumbnail + "View".
- "Change" link per card → returns to step → "Save and return to review".
- Optional answers show "Not provided".
- Submit: "Submit application for {{ course.name }}".
- Confirmation sentence above submit.

Post-submit:
- Read-only review (no Change links) but user can still see what they sent.
- `needs_changes` re-enables Change links + top-of-page explanation + per-step admin notes.
- Approved/rejected = read-only with status badge.

## 5. Recommendations for FLS

1. **Use a persisted-draft model, not `SessionWizardView`/`CookieWizardView`.** Session/cookie storage doesn't survive logout/device switch; CookieWizardView fails silently >4 KB and breaks on SECRET_KEY rotation. The persisted model is also where the admin "needs_changes" round-trip naturally lives.
2. **One URL per step.** HTMX inside the step (FLS 422 inline-validation pattern, file uploads, conditional reveal); plain GET/POST + redirect between steps. Browser back/refresh/bookmarks work for free.
3. **Question-bank schema** (`Course → ApplicationStep → ApplicationQuestion → ApplicationResponse`) with JSON values so adding question types doesn't need migrations. Mirrors content_engine.
4. **Numbered + labelled progress indicator,** all steps visible, current highlighted, completed ticked; collapses to "Step 2 of 5: Documents" on mobile.
5. **GOV.UK Check Answers as the final step.** Summary cards, per-section "Change" links that round-trip to review (`?return=review`), optional answers as "Not provided", action-labelled submit ("Submit application for {{ course.name }}").
6. **Auto-save on each step advance + visible "Save and exit" link.** No magic-link emails (users are logged in; drafts live in their dashboard).
7. **File upload UX:** native picker → hx-post → partial with filename/size/thumbnail + Replace/Remove; client + server validation; HTMX progress events.
8. **Status model with admin round-trip:** `draft → submitted → under_review → (needs_changes ↔ submitted) → approved | rejected`. `needs_changes` reopens edits; per-step admin notes render on the relevant step. No auto-enrol.
9. **Branching invalidation rule:** if editing step N invalidates later steps, walk the user through them before returning to review; never silently drop their answers.
10. **Test the back button.** Add a Playwright test (per `fls:playwright-tests`) that completes 2 steps, hits browser back, refreshes, and asserts data is intact.

## Sources

- https://www.nngroup.com/articles/wizards/
- https://www.nngroup.com/articles/user-control-and-freedom/
- https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/
- https://baymard.com/research/checkout-usability
- https://baymard.com/blog/back-button-expectations
- https://design-system.service.gov.uk/patterns/check-answers/
- https://design-system.service.gov.uk/patterns/question-pages/
- https://www.gov.uk/service-manual/design/form-structure
- https://service-manual.ons.gov.uk/design-system/patterns/check-answers
- https://www.forms.service.gov.uk/features
- https://django-formtools.readthedocs.io/en/latest/wizard.html
- https://github.com/jazzband/django-formtools/issues/45
- https://code.djangoproject.com/ticket/22638
- https://code.djangoproject.com/ticket/17850
- https://minimalistdjango.com/TIL/2023-09-06-multi-step-form-with-django-and-htmx/
- https://github.com/spookylukey/django-htmx-patterns
- https://www.formassembly.com/blog/multi-step-form-best-practices/
- https://www.reform.app/blog/10-best-practices-for-multi-step-form-navigation
- https://www.zuko.io/blog/single-page-or-multi-step-form
- https://uploadcare.com/blog/file-uploader-ux-best-practices/
- https://designsystem.digital.gov/components/file-input/
- https://www.ucas.com/applying/after-you-apply/making-changes-to-your-application-after-you-apply
- https://www.ucas.com/advisers/help-and-training/guides-resources-and-training/application-overview/our-adviser-portal/managing-applications-in-the-adviser-portal
- https://www.growform.co/must-follow-ux-best-practices-when-designing-a-multi-step-form/
