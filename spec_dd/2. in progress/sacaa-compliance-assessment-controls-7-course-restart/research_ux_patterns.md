# Research: UX patterns for a staff course restart with a required reason

Scope: the restart dialog, irreversibility, showing earlier runs, labelling earlier vs current run,
notifying the learner, and the learner's experience. Web findings are cited by URL; project
findings by file path. Web evidence here is thin on this exact job (the searches found no source
that covers a "required reason" field on a destructive action, and nothing on collapsed attempt
history in Canvas or Blackboard), so the project's own conventions carry most of the weight.

Settled by `answers.md`: option C (registration chain, new individual registration, old one
"superseded"), restart only on an active registration whatever the run's state, no undo, one
`registration.restarted` webhook. Findings below are fitted to those.

## 1. The restart confirm dialog

### What the web says

- NN/g: confirm only serious or irreversible actions, restate the specific request and its effect
  (name the thing, give counts), use buttons that name the outcome rather than Yes/No, do not
  pre-select the destructive choice, and reserve non-routine steps such as typing a word for rare,
  severe cases or they become automatic.
  https://www.nngroup.com/articles/confirmation-dialog/
- Typed confirmation (type the resource name) is a "speed bump" for highly destructive actions.
  Supabase and Vercel both use it for deleting projects or accounts; SaaSFrame cautions it makes
  people look at the name but does not prove they understand the result.
  https://supabase.com/design-system/docs/fragments/text-confirm-dialog ,
  https://vercel.com/geist/destructive-confirmation-input ,
  https://www.saasframe.io/patterns/confirmation-dialog
- Wider guidance: make irreversibility explicit, keep safe option as default focus.
  https://www.smashingmagazine.com/2024/09/how-manage-dangerous-actions-user-interfaces ,
  https://primer.style/product/components/confirmation-dialog/guidelines
- Undo/soft-delete beats confirmation for reversible actions; confirmation is for the small set of
  severe ones. https://dev.to/137foundry/how-to-choose-between-confirmation-dialogs-undo-windows-and-soft-delete-patterns-1opj

### What this project does

- The shared confirm dialog is `ConfirmAction` + `ReasonMixin` in `freedom_ls/panel_framework/actions.py`
  (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, "actions.py"). `ReasonMixin` with
  `reason_required = True` refuses an empty reason, which is the "record needs a why" case. The
  reason text arrives as `ctx.reason` in `handle_submit`. `reason_max_length` must match the audit
  store's length.
- No FLS dialog uses typed confirmation. The existing registration dialogs
  (`freedom_ls/educator_interface/panels/common/registration_actions.py`:
  `LearnerRegistrationDeactivation`, `LearnerRegistrationReactivation`,
  `CohortRegistrationDeactivation`) are plain confirms with a reason field. Their body templates
  (e.g. `freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_registration_confirmation.html`)
  are short one-line statements: "They lose access to {{ course }}.", "Progress is kept.", "You can
  reactivate the registration later."
- Title pattern: "Deactivate <learner>'s registration for <course>?" Confirm button is named by
  `confirm_label`; loading text ends in "…" (`panel-framework` SKILL.md, Dialogs).
- Tone rule: a confirm that deletes a row is `error`; one that flips `is_active` is `primary`.
  A restart sits between the two: nothing is deleted, but it cannot be undone. See the open
  decision below.
- The shape to copy for a row-scoped action: `row_param = "registration"`, `registration_scope(ctx)`
  abstract, `get_row_queryset` filtered to active rows, `get_confirm_context`, `handle_submit`
  calling a service function with `actor=ctx.request.user, reason=ctx.reason`, then
  `registration_changed_response(learner)` (both `REGISTRATION_CHANGED` and `LEARNER_CHANGED`
  events). A `LearnerRestart` action fits `CHANGE_LEARNER_REGISTRATION`, as the idea recommends,
  and would live in this file so any page listing registrations reuses it.
- Cohort-granted learner: the dialog must say what differs. Today's deactivate dialog already
  computes "keeping cohorts" via `other_grants_for` and `cohorts_visible_to`; a cohort learner's
  restart needs an equivalent "this affects only <learner>; <cohort> and its other learners are
  unchanged" sentence.

### Recommended dialog

- Title (names learner and course, as the neighbours do): "Restart <learner>'s <course>?"
  The brand voice says a confirm "states what is true now and what the action changes", every
  sentence true after the action, plain words for outcomes (`.claude/skills/brand-guidelines/voice.md`,
  "Dialogs and list pages").
- Body, one `<p>` each, base text size (no `text-sm`), in this order:
  1. Now: "<Learner> is <N>% through <course>." (or "has completed", "has not started"; the restart
     applies whatever the state is, per `answers.md`).
  2. Change: "They start again from the beginning and must complete every item and pass every
     assessment again. Nothing from this run counts."
  3. Kept: "This run stays readable as an earlier run. Its progress, attempts and answers cannot
     be changed."
  4. Clock: "Attempt counts, learning time and the deadline clock start again." (the idea says
     the clock restarts because the deadline start is the new progress record's `created_at`).
  5. Cohort case only: "Only <learner> restarts. <Cohort> and its other learners are not changed."
  6. Final: "This cannot be undone." Say it once, plainly, as the last body line. Do not soften
     ("This action is permanent" is fine; "Are you sure?" is not, per NN/g and the voice file).
  7. Notice: "<Learner> is told their course was restarted." Matches the notification decision
     and means the staff member knows who hears.
- Reason field: required, labelled "Reason" (voice principle 6: label what the value is, not who
  typed it). Help text under the field, per the framework rule that a hint sits directly under the
  field: say it is kept in the audit log. Use plain `ReasonMixin`; no `reason_choices`, because the
  idea asks for a free-text reason. A fixed choice list ("Failed final exam", "Other") is a possible
  later addition: `reason_choices` is supported and would make restart reasons reportable, at the
  cost of a spec decision the idea does not ask for. Flag, do not build.
- Confirm button: names the change, per voice rule ("says 'Confirm', or names the change when the
  noun is always true"). "Restart course" is always true here. `loading_text = "Restarting…"`.
  Variant: this fork is for the spec writer. `primary` matches how FLS treats state flips that
  keep data; `error` matches NN/g's "destructive-looking" signal and the framework's rule that
  red goes on the dialog's confirm. Recommend `error`, because the action is irreversible and
  `confirm_variant` is a documented option; the table-row trigger stays `secondary` (rule:
  "never `primary` or `error`: the red goes on its dialog's confirm"). The framework skill's tone
  rule only names Delete/Remove and Deactivate/Reactivate, so this is a new case; record the choice.
- Typed confirmation: recommend not. Reasons: (a) NN/g and Supabase reserve it for rare, severe,
  data-destroying actions; a restart destroys nothing, because earlier-run rows are kept for 5
  years; (b) no FLS dialog uses it, so it would be a one-off needing new framework support and a
  new invariant; (c) the required reason is already a non-routine step that forces a deliberate
  act, and it also feeds the audit entry. The cost of a wrong restart is real (the learner redoes
  a course) but is bounded and audited. If the owner wants friction, the cheapest consistent
  option is the red confirm plus the required reason.
- Disabled confirm: the reason field is required, so the confirm is not disabled; an empty reason
  gets a field error under the field (422), as `ReasonMixin` already does.
- Refusals: a restart on an inactive or already-superseded registration is refused through
  `refusal_response` (a message dialog, 422), not a hidden button, because the row simply has no
  button when the viewer cannot act (panel-framework: "a row the viewer cannot act on ... leaves
  its buttons column empty"). A stale dialog (someone else restarted first) should answer with the
  refusal dialog, as `LearnerRegistrationReactivation._refused` does.

## 2. Irreversible actions with no undo

- Web: undo is preferred wherever possible (NN/g), but confirmation is the right tool where undo
  is impossible. https://www.nngroup.com/articles/confirmation-dialog/
- `answers.md`: a restart is final and audited. So the controls are: the dialog says "This cannot
  be undone"; the audit entry records actor, reason, the run closed and the run opened; and the
  earlier run is never touched, so nothing is lost even though the restart itself cannot be
  reversed. That is a real mitigation: a mistaken restart costs the learner time, not data.
- Say what to do after a mistake, in the dialog or docs, because there is no undo: the earlier run
  remains readable, and staff can contact the owner. Do not promise a path the system does not
  have (voice: "no sentence promises something the change takes away"). Do not say "You can
  restart again to fix this": it does not give the learner their earlier progress back.
- After success: a Django `messages` flash on the page ("Restarted <course> for <learner>."), not a
  notification, per the notifications skill ("Feedback for the user's own action": the result
  appearing is usually enough; otherwise a flash). The panel refresh events
  (`REGISTRATION_CHANGED`, `LEARNER_CHANGED`) redraw the Courses tab, which shows the new run.
- No cap, no cooldown: matches the idea's "no cap in code".

## 3. Earlier runs on a person's detail page (collapsed)

### What the web says

Little directly on point. The Moodle recompletion model archives, never deletes, and reports
read the archive: https://moodle.org/plugins/local_recompletion ,
https://github.com/danmarsden/moodle-local_recompletion . Reported pain: archive reports broke
across Moodle versions, so evidence became hard to produce, and per-participant manual reset was
unclear. (Support for keeping the earlier run first-class and readable in the product, not in a
side archive.) Core Moodle has no general reset for retakes:
https://docs.moodle.org/dev/Course_Reset_Proposal . Warwick's guide recommends archiving
completion data when recompletion is on:
https://warwick.ac.uk/services/digitallearning/support/guides/moodle-guides/mdl-119 .
In SCORM-style tools, the common admin workaround is delete-and-re-enrol, which destroys history
and is exactly what this spec avoids:
https://elearning.adobe.com/2025/03/how-to-force-a-new-student-record-after-a-failed-attempt

### Fit to FLS

- The learner's Courses tab is where the course's progress and quiz attempts table already sit
  (`educator-interface` SKILL.md, Placement table). The restart control belongs "beside the thing
  it changes": a row action on the Courses tab, next to each active course registration, labelled
  so two buttons in one row do not share a bare verb ("Restart <course>" or "Restart course" with
  an `aria_label` naming the course, as `test_every_entry_trigger_names_its_entry` expects for
  entry triggers). A trigger is `secondary` and `size="small"`, never red.
  Do not put it on the Settings tab ("holds only actions that have no home of their own") or in
  the page header ("no action sits in the header").
- Collapsed earlier runs: the panel framework already has the matching pieces.
  - Child rows: `has_child_rows` / `get_child_rows(row)` with `child_rows_collapsed = True`
    gives a group row with a chevron, children hidden until opened, and visible without
    JavaScript. A course row is the group and its earlier runs are the children. Limits: no bulk
    actions and no `row_detail_template_name` on that table. The worked example is
    `CourseOutlineTable` in `freedom_ls/educator_interface/panels/course/content_preview.py`.
  - Row detail: `row_detail_template_name` renders a template under each row behind a toggle
    (a disclosure below `md`), with `has_row_detail(row)` hiding it when there is nothing to show.
    This is the lighter fit for "this course has N earlier runs": the detail template lists them.
    Cannot combine with child rows.
  - Choose one; the spec should say which. Row detail is the smaller change if the Courses tab
    table is not already a child-rows table; child rows give each earlier run a full row that can
    carry its own quiz-attempts link. Either way a course with no earlier runs shows no chevron
    and no empty note (the `has_row_detail` hook).
- What an earlier-run row shows (same fields in the same places on every row, never dash-joined,
  per the panel-framework "list of records" rule): run label ("Run 1", "Earlier run"), how it
  started ("Staff restart"), started date, closed date, closing state ("Incomplete" or
  "Complete"), and the figure at the end (progress %). Dates through `<c-date>`, never a hand
  format (voice.md "Dates and times").
- Read-only means no action buttons on an earlier-run row except links that open the attempt
  review (the attempt number opens the quick view and the full attempt review page, per
  `educator-interface`). A row whose buttons the viewer cannot use leaves the buttons cell
  empty, with no note. So an earlier run has no Restart, no Deactivate and no edit controls. If a
  reviewer opens an earlier run's quiz attempt, the attempt page should still render through the
  answer templates in `form_engine/templates/form_engine/answers/` (never disabled inputs: "A
  disabled field looks editable"), which suits a frozen run.
- Reason visibility: the restart reason is on the restart only (idea). Show it on the earlier-run
  row's quick view or row detail under a "Reason" label (voice principle 6), not in the row. The
  skill rule is that detail not needed to scan a row lives in the quick view.
- Audit: the entry appears in the learner's History tab through the existing audit log table
  (`educator-interface` SKILL.md, "Audit log and History tables"), with its Who, What and When
  filters; the restart needs a new action label there (e.g. "Course restarted"). No extra UI.

## 4. "Earlier run" vs "current run" in tables and reports

- Chosen words, from the idea and answers: "run", "earlier run", "restart". Use "earlier run"
  for the closed one and "current run" only where both appear side by side; a lone current run
  needs no label (panel-framework page header rule: "shows a state badge only for a state that
  differs from the default"). So: an unlabelled row is current; an earlier run gets the chip.
- Chip, not a prose suffix: use `<c-panel-chip>` or `<c-panel-status-badge>` reading "Earlier
  run" (or "Restarted" if the spec prefers the cause). Plain outcome words per voice principle 5:
  say "Earlier run", not "Archived" or "Superseded" in the UI. Reserve "superseded" for the
  registration state in code/admin; "archived" suggests hidden or deletable, which contradicts
  "kept 5 years and readable".
- Number runs when more than one exists: "Run 1 of 3" is clearer than dates alone and fits
  "attempt, re-write 1, re-write 2". Show the start reason as detail text under the run name
  (`text-sm text-muted`, e.g. "Staff restart"), the project's name-then-muted-detail row shape.
  Avoid "re-write": that is the regulation's word for the exam, and FLS restarts the course, not
  the exam (the final exam is in person).
- Reports and exports: the idea says label, never mix. Pattern: an explicit "Run" column (number
  plus "Earlier run" / blank) and a "How it started" column, with the current run filtered in by
  default and earlier runs reachable by a toggle, in the panel framework's `ToggleFilter`
  ("Include earlier runs", which "widens the table's own queryset when set"). Export includes the
  run column always so a CSV row is unambiguous without the filter state. Cohort pages follow the
  chain to the current run and label it as a restart (`answers.md`), so a cohort learner row
  reads "Restarted" in a chip, with the detail "via <learner>'s own registration" using the
  project's one word for a relation, "via" (voice.md: "One word for a relation everywhere").
- Counts: a footer entry count states what the table holds; if earlier runs are included the count
  grows. Say what the filter does in the filter's label, not in prose above the table (list pages
  open with heading and toolbar).
- Compliance reading: a report that answers "was this learner certified on this date" must show
  earlier completed runs with their completion date even when the run is not current. Keep
  completion date and score on the earlier-run row and never blank them.

## 5. Telling the learner (notification copy)

Project rules, `claude_plugins/fls-dev/skills/notifications/SKILL.md`:

- A restart passes the test: someone else caused it (an educator acted) and the learner may not
  have been there. It is the same shape as "Admin or educator registers a learner for a course:
  Yes". The recipient is never the actor, since staff restart; if a staff member is also a
  learner and restarts their own course on their own page, the "user is not the actor" rule
  excludes the notification, and the spec must say how that is decided (record the actor on the
  restart, as the skill says "Decide at the source who the actor is").
- One event, one notification: the restart creates one registration and one closes. Existing
  `post_save` receivers for registrations (the `course.registered` receiver in
  `freedom_ls/learner_progress/signals.py`) could fire a "You've been registered" notification
  for the new individual registration. The spec must suppress that and send only the restart
  notification, or the learner hears twice. Likewise the webhook is `registration.restarted`
  only, not `registration.added` (`answers.md`).
- "A notification and a webhook are different things": keep the webhook; the notification is
  separate.
- Copy, written for someone who was not there ("carries its own context"): the notification
  names the course and says what changed and what to do. Draft, in the voice (direct, plain,
  full stop on routine text):
  - Title: "Your course <course> has been restarted"
  - Body: "<Staff member> restarted <course> for you. You start again from the beginning and
    complete every item and assessment again. Your earlier progress is kept on record."
  - Link: the course (the first item, where the learner will act).
  - Should the staff member's name show? The "who" is useful to a learner who was not there
    and matches `course.registered` precedent if that category names the actor; check its
    existing copy before fixing this. Should the reason show? The idea leaves the reason staff-
    facing. Showing it gives context ("failed the final exam") but exposes free text staff wrote
    for the audit trail and may include things not meant for the learner. Recommend the reason is
    not in the notification by default; flag as an owner decision.
  - Voice: no "Oops", no "journey", no "fresh start!" (SaaS phrasing the brand rules mark as
    off-voice); say what happened. "Restarted" is the plain word; do not use "reset", which sounds
    like losing data, and the earlier run is kept.
- Checklist answers for the spec (the notifications skill asks five):
  1. Actor: the staff member; the recipient is never the actor, excluded by comparing the
     restart's actor to the learner's user.
  2. Without it, the learner sees: nothing until they next open the course, then an empty course
     with no explanation. Possibly a long time.
  3. They will: open the course and start again. Link to it.
  4. Frequency: at most a few times per course (regulation allows two re-writes), so no rollup.
  5. Email: in-app is enough until email backends exist; arguably the one category where email
     would help, since the learner may not log in. State "in-app now, email when built".
- The "page is the feedback" rule: when the learner is looking at the course and the restart
  happens, nothing refreshes under them. The notification is the signal. If the learner has the
  old course page open, an action posted against the superseded run should be refused with a
  plain message pointing them to the current run (see section 6), not a 500.

## 6. How the learner experiences a restarted course

### Web

- Common LMS behaviour: relaunching resumes the saved attempt unless the LMS forces a new one;
  admins fix it by resetting or removing the learner and re-enrolling them. That experience is
  "the course looks the same, with old answers". The restart must not feel like that.
  https://community.articulate.com/discussions/articulate-storyline/using-a-final-exam-resetting-courses ,
  https://elearning.adobe.com/2025/03/how-to-force-a-new-student-record-after-a-failed-attempt
- NN/g and Primer on notifications: a notification must carry its own context for someone doing
  something else; page content already visible does not need one.
  https://www.nngroup.com/articles/indicators-validations-notifications/ ,
  https://primer.style/accessibility/patterns/accessible-notifications-and-messages/
  (both already cited by the notifications skill).

### Recommendation

- The course player, dashboard and progress bars resolve to the current run only (idea: "the
  learner player resolve to the current run"). On first open after a restart the course looks like
  a new course: 0% progress, no completed ticks, the first item the next action. That alone
  tells the learner the course is fresh.
- One-time banner: recommended, but small. A `<c-callout>` (the learner side is not panel
  framework, so `<c-callout>`, not `<c-panel-callout>`; the rule "`<c-callout>` is for the rest of
  the site") at the top of the course page: "Your course was restarted on 3 Nov 2026. You start
  again from the beginning." It exists because the notification may be unread or missed, and
  the learner who opens the course link directly gets the explanation in place. Without it, a
  learner who ignores the bell sees an empty course and may think progress was lost (the
  SCORM-forum experience above). It must not be a toast: a toast disappears. It can show for
  the whole life of the run's first visit and dismiss on read; whether a dismiss state is stored
  is a build decision (the idea says "don't build functionality that is not explicitly
  requested"), so the simplest honest version is: show while the new run has no progress at all,
  derived from state, with no dismiss field. Flag for the spec: the banner is a requirement the
  idea does not state; it is a recommendation, not settled.
- No learner-facing view of earlier runs (idea). The banner must therefore not link to one, and
  must not promise "your earlier results are available". It says earlier progress is kept on
  record, which is true (retention) without implying the learner can read it.
- Learner-side labels: "restarted", "start again". Not "retake" (that is the exam), not "fresh
  start" (brand voice marks marketing gloss as drift; the brand voice is "plain outcomes for
  adults").
- Deadlines: the clock restarts with the run, so the learner's deadline text (shown through
  `{% local_time %}`) changes. The banner or the notification should not hide this; a learner
  with a new deadline needs to know the date moved. State "Your deadline is now <date>" only if
  the course has one (deadlines specs own that wording; do not invent it here).
- Stale pages and in-flight requests: a learner mid-quiz when staff restart gets their next
  submit refused. Refuse with a plain 422 message: "This course was restarted. Open it again to
  continue." Not a silent failure and not a silent write to the closed run (the earlier run
  cannot change: idea). Worth a spec acceptance criterion because HTMX posts will hit this.
- Completion emails or certificates: none exist (out of scope). `course.completed` fires once per
  run (idea), so a learner who finishes the restarted run gets the completion page as normal; the
  earlier run's completion is not repeated or overwritten.

## 7. Decisions for the spec, with recommendations

| Decision | Recommendation | Why |
|---|---|---|
| Dialog type | `ConfirmAction` + `ReasonMixin`, `reason_required = True`, in `registration_actions.py` | The shared dialog; capability `CHANGE_LEARNER_REGISTRATION`. |
| Typed confirmation | No | Nothing is destroyed; NN/g reserves it for rare severe cases; no FLS precedent. |
| Confirm variant | `error`, label "Restart course", loading "Restarting…" | Irreversible; red goes on the dialog's confirm, trigger stays `secondary`. New tone case, note in the framework skill. |
| States what happens | Now, change, kept, clock, cohort-only note, "cannot be undone", learner is told | NN/g specificity; voice "before and after"; every sentence true after. |
| Trigger placement | Row action on the learner's Courses tab, per active registration | `educator-interface` Placement rule. |
| Earlier-run display | Collapsed row detail or child rows under the course row, read-only, "Earlier run" chip, reason under "Reason" | Framework primitives exist; pick one. |
| Report labelling | "Run" and "How it started" columns; "Include earlier runs" toggle; always in exports | Never mixed, always unambiguous. |
| Notification | Yes, one in-app category, copy "Your course X has been restarted", link to course, no reason in the text, no rollup | Notifications skill, actor never recipient; suppress the `course.registered` receiver. |
| Learner view | Current run only; small derived banner on the course page | Avoids the "looks like nothing changed / progress lost" confusion; flagged as beyond the idea. |
| Learner mid-quiz | Refuse the write with a plain 422 | Earlier run is immutable. |

## 8. Gaps and open questions

- The web research found no source on required-reason fields in destructive dialogs, or on
  collapsed run history in a person's record, so those rest on the project's conventions and
  the panel framework's primitives, not external evidence.
- Not checked: the existing `course.registered` notification copy and whether it names the actor
  (needed to fix the restart copy's "<Staff member> restarted ...").
- Not checked: whether the learner's Courses tab table is already a child-rows table, which
  decides child rows vs row detail for earlier runs.
- The `error` confirm variant for a restart is a new case against the framework's tone rule; the
  spec should record it and update `panel-framework` SKILL.md, as the project rule says
  documentation is the source of truth.

## Sources

- NN/g, Confirmation dialogs: https://www.nngroup.com/articles/confirmation-dialog/
- NN/g, Indicators, Validations, and Notifications: https://www.nngroup.com/articles/indicators-validations-notifications/
- Supabase Text Confirm Dialog: https://supabase.com/design-system/docs/fragments/text-confirm-dialog
- Vercel Destructive Confirmation Input: https://vercel.com/geist/destructive-confirmation-input
- SaaSFrame, Confirmation Dialog: https://www.saasframe.io/patterns/confirmation-dialog
- Smashing Magazine, Managing dangerous actions: https://www.smashingmagazine.com/2024/09/how-manage-dangerous-actions-user-interfaces
- Primer, Confirmation dialog guidelines: https://primer.style/product/components/confirmation-dialog/guidelines
- Primer, Accessible notifications: https://primer.style/accessibility/patterns/accessible-notifications-and-messages/
- DEV, Confirmation dialogs vs undo: https://dev.to/137foundry/how-to-choose-between-confirmation-dialogs-undo-windows-and-soft-delete-patterns-1opj
- Moodle local_recompletion: https://moodle.org/plugins/local_recompletion and https://github.com/danmarsden/moodle-local_recompletion
- Moodle Course Reset Proposal: https://docs.moodle.org/dev/Course_Reset_Proposal
- Warwick Moodle recompletion guide: https://warwick.ac.uk/services/digitallearning/support/guides/moodle-guides/mdl-119
- Adobe eLearning, force a new student record: https://elearning.adobe.com/2025/03/how-to-force-a-new-student-record-after-a-failed-attempt
- Articulate community, resetting courses: https://community.articulate.com/discussions/articulate-storyline/using-a-final-exam-resetting-courses
- Project: `freedom_ls/educator_interface/panels/common/registration_actions.py`,
  `freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_registration_confirmation.html`,
  `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`,
  `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`,
  `claude_plugins/fls-dev/skills/notifications/SKILL.md`,
  `.claude/skills/brand-guidelines/voice.md`

status: ok · reason: web evidence thin for required-reason and run-history patterns; project conventions fully read; two items flagged as unchecked
