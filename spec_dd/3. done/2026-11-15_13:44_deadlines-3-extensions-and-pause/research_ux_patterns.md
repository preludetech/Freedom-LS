# Research: UX patterns for extensions and pause

Scope: Django admin pause/resume/extend, learner paused state, in-app notifications, staff history.
Learner self-pause is out of scope (spec 4).

## 1. What FLS already shows learners (spec 2, as built)

Source: `3. done/2026-11-01_23:53_deadlines-2-consequence-policy/3. frontend_qa.md`, and the templates under
`freedom_ls/learner_interface/templates/learner_interface/`.

- **Vocabulary is fixed by spec 2 QA.** Learner pages say "Deadline", "Missed deadline", "Closes", "Closed",
  "Access ends", "Access ended", "Next deadline:". "Due", "Overdue", "Expired", "Locked" (for a closed item)
  are bugs. A closed item never reads "Locked". Chips carry text, never colour alone; the "Closed" chip also
  carries an icon.
- **Row-level labels:** `partials/deadline_labels.html` renders `<c-chip variant="error" size="xs" icon="deadline"
  class="forced-colors:border">Closed {date}</c-chip>`, else a "Missed deadline" chip, else plain muted text
  "Deadline {date}." Dates come from the `local_time` tag in `deadline_tags`. The minimal TOC
  (`course_minimal_toc.html`) shows a bare "Closed" chip even with `hide_deadlines`, so state is not colour-only.
- **Course-level state on cards and rows:** `partials/course_status_eyebrow.html` and `course_status_label.html`
  take a `status` of `not_registered | registered | in_progress | complete | coming_soon | access_ended`. The
  `access_ended` branch renders the deadline icon plus "Access ended {date}" (`with_icon`, `as_chip` on the
  compact row). `course_card.html` and `course_row.html` switch on `course.access_ended_at`. The registration
  stays on the dashboard and links to course detail. `partials/course_deadline_line.html` shows a missed or next
  deadline on the dashboard.
- **Course detail:** `course_detail.html` (line 190) shows, in the CTA slot, a `<c-callout level="warning">`:
  "Your access to this course ended on {date}. Your progress is saved. Ask your educator to restore it." In
  place of the "Start" button. The TOC (`course_minimal_toc.html`) stays visible when `children or not access_ended_at`.
- **Player:** a closed item opens `course_item_closed.html`: a warning callout "Closed on {date}. Ask your
  educator if you need more time.", then "Submit your answers" if there is an open attempt, "See your results",
  and the normal player footer. This is the closest template to what a paused item needs.
- **Design brief:** `spec_dd/2. in progress/design_learner-interface-deadlines/idea.md` is a single line
  ("windows showed to the learner don't look very good"), with a todo only. No design.md exists, so a paused
  state must reuse the existing parts (chip, callout, eyebrow) and will inherit whatever that restyle does.
- **Brand voice** (`.claude/skills/brand-guidelines/voice.md`): direct, brief, human; name the problem and
  the fix, leave blame out; routine messages end on a full stop; no SaaS words; "learners", not "students". Dates
  are `3 Nov 2026` / `3 Nov 2026, 07:37` (`|date:"j M Y"`), never locale default. Confirm dialogs state what is
  true now and what the action changes. A disabled action shows its reason beside it. Two buttons in a row never
  share a bare verb.

Implication: the paused state is a sibling of "Access ended". Same three slots (eyebrow/chip on the card and row,
callout on detail, callout in the player), same icon family, same `local_time` formatting.

## 2. Paused-state patterns

Wider practice (gym and subscription freezes, Netflix/Spotify-style "paused until" states): a paused account is
shown as a persistent **status**, not a transient message. The date it ends is the most useful fact, and the
action to resume is secondary to the learner when staff did the pausing. These are my synthesis, not sourced
from a single page; see Sources for the references checked.

| Surface | Recommendation | Why |
| --- | --- | --- |
| Dashboard card and row | Eyebrow or chip, same slot as "Access ended": pause icon + "Paused until 12 Dec 2026" or "Paused" when no planned resume. No deadline line, no CTA to continue. | A badge fits a list; a banner per card is noisy. Matches `status="access_ended"` plumbing: add `status="paused"` with `paused_until`. |
| Course detail | `<c-callout level="info">` (not warning: nothing the learner did wrong) in the CTA slot, replacing "Start/Continue". Past results remain linked. | Mirrors the access-ended callout. Info level separates "paused by staff" from the warning used for ended access. |
| TOC rows while paused | Keep the outline. Rows that cannot be opened show a muted state with a text chip "Paused" (icon, not colour alone), not "Locked". Completed rows keep their results link. | Spec 2 forbids "Locked" for closed items; the same reasoning applies (locked implies a prerequisite). Past results and quiz scores stay visible per the idea. |
| Deadline labels while paused | Hide "Deadline {date}" and "Closes" on unmet items, since they will move by the paused time. Show only "Deadlines move when you resume." once, on detail. Met deadlines unchanged. | Showing a date that is about to change misleads. Reminders are already off for paused learners. |
| Player | `course_item_paused.html` modelled on `course_item_closed.html`: callout, "See your results" if any, back-to-course button. Guessed URLs hit the same page, never a 404. | Same shape as the closed page, same footer. |

Frozen attempt: the player page for a form with an open attempt says the answers are kept ("Your answers are
saved. You can continue after {date}"), with no "Submit your answers" button (unlike closed items, where submit
is offered).

### Copy suggestions (brand voice; dates via `local_time`)

- Card/row chip: `Paused until 12 Dec 2026` / `Paused`
- Detail callout, planned resume: `Your educator paused this course. It resumes on 12 Dec 2026. Your progress is saved.`
- Detail callout, open-ended: `Your educator paused this course. Your progress is saved. You will be able to continue when they resume it.`
- With reason shown (decide in spec; see section 3): append `Reason: {reason}`.
- Deadlines note: `Your deadlines move by the time paused.`
- Player: `This course is paused, so this item can't be opened right now. Your results are still here.`
- Words to avoid: "Locked", "Suspended", "Frozen" (in learner copy), "Expired", "Overdue".
- Open decision: whether a staff-written reason is learner-visible. Staff reasons in an admin can be internal
  ("medical, per email"). Safest pattern: one free-text `reason` that is staff-only, and learner copy that
  is generic. If the learner should see a message, add a separate optional learner-visible note field.
  Flag this to the spec.
- A planned resume date reached: evaluated when read, so the card flips from "Paused until 12 Dec 2026" to
  normal with no sweep. The page has no stale state to explain.

## 3. Notification copy ("someone acted on your account")

`fls-dev:notifications` rules that bear on this spec:
- Pause, resume and extension by staff pass the test: someone else caused it (test 1) and the actor is not the
  recipient. The spec must still answer the five-question checklist (actor, what they would see otherwise,
  what they do with it, frequency, email urgency).
- "Write the message for someone who wasn't there": name the course, name what happened, say what it means.
- "One event, one notification": a whole-course extension is one notification, not one per item. A staff
  resume that follows an automatic one must not double up (the planned resume is system-caused and spec 5
  owns that webhook; this spec's idea has no notification for a planned resume, so decide and state it).
- Don't notify on a learner's own action (spec 4). Page-visible state is not a reason to skip it here: the
  learner is not on the page when staff act.
- Link target: the course detail page, which shows the paused state or the new dates.
- Rollup: `rollup=True` exists but no category uses it. Pause/extend are rare per learner, so no rollup.

Suggested copy (title / body), voice rules apply (full stop, no exclamation, no "Oops"):

| Event | Title | Body |
| --- | --- | --- |
| Pause | `Your course was paused` | `Your educator paused {course}. It resumes on 12 Dec 2026. Your progress is saved.` (no date: `...Your progress is saved. You can continue when it is resumed.`) |
| Resume (staff) | `Your course was resumed` | `Your educator resumed {course}. Your deadlines moved by 4 days.` |
| Extension, one item | `Your deadline was extended` | `Your educator extended the deadline for {item} in {course} to 20 Dec 2026.` |
| Extension, time limit | `Your course time limit was extended` | `Your educator extended your time limit for {course} to 20 Jan 2027.` |
| Extension, whole course | `Your deadlines were extended` | `Your educator moved your deadlines in {course} by 7 days.` |

Include the reason? The Atlassian/Material guidance the skill cites is about not repeating on-screen
information and giving context; a reason is context, but staff reasons are internal (see section 2). Default:
leave the reason out of the notification and include the effect (date, days). Link: the course detail URL.
Use "Your educator" consistently with spec 2 ("Ask your educator") and avoid naming the person: the staff member
may be an admin, not an educator.

## 4. Django admin UX

**What the project uses.** `django-unfold` is installed (`pyproject.toml`, `config/settings_base.py`);
`ModelAdmin` and `TabularInline` come from `unfold.admin` (e.g. `freedom_ls/deadlines/admin.py`).

**Existing FLS patterns:**
- List-page actions: `actions = [...]` with `@admin.action(description=..., permissions=["change"])`
  (`api_admin`, `webhooks`, `hr_attributes`, `referral_tracking`).
- Detail-page buttons (Unfold): `actions_detail = ["send_test_action"]` with
  `@unfold_action(description="Send Test", url_path="send-test-action")` (webhooks); `get_actions_detail`
  is overridden in `api_admin/admin.py` to hide the button when the key is not active. Reuse that to show
  "Pause course" only when not paused, "Resume course" only when paused.
- **Intermediate form with a reason:** `api_admin/admin.py` redirects both the list action (`revoke_selected`)
  and the detail action (`revoke_key`) to one custom URL registered in `get_urls`
  (`revoke_view`, wrapped in `admin_site.admin_view`). This is the stock Django "action then confirmation page"
  pattern (action returns an `HttpResponseRedirect`/`TemplateResponse`, a second view renders the form and
  does the work on POST) with the shared view reused for single and bulk entry. It is the in-repo precedent to
  copy for pause and extend.
- Change-page extras on `CourseProgress`: spec 2 already added an inline, two read-only panels ("Effective
  deadlines", "Effective deadline policy") and a "Deadlines" fieldset onto `CourseProgressAdmin` from the
  `deadlines` app by assignment (`CourseProgressAdmin.inlines = [...]`, `setattr(...)`), because the app sits
  above `learner_progress`. Pause and extension controls fall in the same seam if the models live in `deadlines`.
- Existing overrides: `LearnerDeadlineOverrideInline` already carries `reason`, `set_by` and the effective
  value on the CourseProgress change page. An extension is an override with a "N more days" delta, so staff
  find extension next to overrides.

**Where the controls should live (recommendation).**
1. Primary entry: **detail-page action buttons on the CourseProgress change page** ("Pause course",
   "Resume course", "Extend deadline"), each going to a small intermediate form page (fields below). The learner's
   record is where staff already see effective deadlines and policy, so staff read the before-state next to
   the button. Matches `revoke_key`'s precedent.
2. A **list action** on the CourseProgress changelist ("Pause selected" with a reason form) is cheap with the
   revoke precedent, but the idea limits bulk across learners to spec 6. Leave it out; do not build unrequested.
3. Not on the registration admin: a registration may be a cohort or individual one, and pause belongs to the
   learner's course record (the one spec 2 uses for learner-level overrides).
4. A dedicated Pause/Extension admin with an add form is still needed as a **read-mostly record list**
   (view history, filter), but should not be where staff start, since a bare add form lets staff create
   a record without the side effects (shift maths, webhook, notification). Make the model admin
   `has_add_permission=False` and route creation through the action view; or keep the add form and have
   `save_model` do the side effects. The former is safer and fits the "one action leaves no half state" rule.

**Intermediate form fields and copy** (confirm dialog rule: state what is true now and what the action changes):
- Pause: header `Pause {learner} on {course}`; before-line `{learner} can open this course now. After pausing,
  nothing in it can be opened; past results stay visible.` Fields: `Reason` (required textarea), `Planned
  resume date` (optional date, help `Leave empty to pause until you resume it. Deadlines move by the whole days
  paused, rounded up.`). Buttons: `Pause course`, `Cancel`.
- Resume: before-line `Paused since 3 Nov 2026. Resuming moves the time limit and every unmet deadline forward
  by 4 days.` Reason optional or required (spec decision). Buttons: `Resume course`, `Cancel`.
- Extend: radio of target (`One item`, `Course time limit`, `Whole course`), an item picker (reuse
  `CollectionItemChoiceField`), `Add N days` or `Move to date` (matches the answers: "N more days or to this
  date"), `Reason` (required). Show current effective date and resulting date side by side; for the whole-course
  case list the unmet deadlines that will move. Buttons: `Extend deadline`, `Cancel`. Success flash:
  `Extended {item} for {learner} by 5 days. It now closes on 20 Dec 2026.` (full stop, specifics, per voice).
- Hide or disable invalid actions with a reason beside them (voice rule): e.g. "Extend" on a paused course
  reads `Resume the course first, or the extension is overwritten by the pause shift` only if the spec rules
  that; otherwise allow it (stack semantics were settled in answers).
- Admin audit: stamp `set_by`/actor from `request.user` as the override formset does.

## 5. History for staff

- **Inline on the CourseProgress change page** is the right default: a read-only `TabularInline` listing
  start, planned resume, ended at, status, reason, actor (the same fields spec 2's override inline shows:
  reason, set_by). Staff open one learner and see every pause and extension without leaving. Order newest first.
  Read-only avoids editing history; actions create rows.
- **A changelist with list filters** (status paused/ended, course, date range, actor; `list_filter_submit = True`
  is already the project convention in `learner_progress/admin.py`) answers the cross-learner question
  ("who is paused now?"). It is cheap and useful for staff, but is not bulk action, so it stays in scope as a
  read-only list. Add the paused state as a filter or column on `CourseProgressAdmin` too.
- If pause and extension are two models, each gets its own inline (or a combined read-only panel built like
  `effective_deadlines`). A single "Pauses and extensions" panel mixing both, newest first, reads best to staff
  ("what happened to this learner's dates"); that is a display choice independent of the one-model-or-two
  decision.
- Show on the panel the applied shift (e.g. `Moved 4 days`) so a resume's effect is auditable; rounding up is
  a surprise to staff otherwise.

## Sources

Checked in-repo (all read in this run): the files listed in section 1 and 4, plus
`claude_plugins/fls-dev/skills/notifications/SKILL.md`, `.claude/skills/brand-guidelines/voice.md`.
External references (not fetched in this run; named in the in-repo notifications skill or standard docs):
- Django admin actions, intermediate pages: https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/
- Unfold actions (list, detail, row, with intermediate forms): https://unfoldadmin.com/docs/actions/
- NN/g, Indicators, Validations, and Notifications: https://www.nngroup.com/articles/indicators-validations-notifications/
- Material Design notifications pattern: https://m1.material.io/patterns/notifications.html
- Primer accessible notifications: https://primer.style/accessibility/patterns/accessible-notifications-and-messages/
- Atlassian email notification own-change exclusion: https://support.atlassian.com/jira-cloud-administration/docs/configure-email-notifications/

The paused-state patterns in section 2 and the copy in sections 2 to 4 are my synthesis from the repo's own
conventions, not quotes from a source.

status: ok
