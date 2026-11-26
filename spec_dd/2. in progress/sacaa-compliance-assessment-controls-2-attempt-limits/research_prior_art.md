# Prior art: attempt limits and waits (spec 2 of the SACAA assessment controls)

Scope: what has already been tried here and elsewhere. The regulation text and the cross-LMS survey
live in `spec_dd/1. next/sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`
(especially its "re-write limit" and course-redo/recompletion notes); not repeated. The attempt
lifecycle and start gate are in `.../research_attempts_and_scoring.md` section 1.

Method note: this was a targeted search (spec folders under `spec_dd/3. done/`, `2. in progress/`,
`1. next/`, plus `views.py`), not a read of every file. Where a point is from a skim it says so.

## 1. Here: no earlier attempt at attempt counting or waits

- No spec in `spec_dd/3. done/` implemented a max-attempts cap, a retake wait or a cooldown. The only
  hits for "Try Again" are the start-page restyle and QA passes that assert the button always shows
  after a failed attempt (below). Today's behaviour is "Try Again" unconditional while the item is open.
- The closest precedent for a *refusal that is a policy, not an error* is the deadlines work
  (`spec_dd/3. done/2026-11-01_23:53_deadlines-2-consequence-policy/`). Its decisions that carry over:
  - A refused CLOSED item redirects to `view_course_item`, which shows a closed notice, not to the course
    detail page. QA first expected course detail; the spec was right and the plan was "stale"
    (qa_report, deviations (b)).
  - A closed quiz or ended-access results page shows no "Try Again"/"Retry" and gives the reason in the
    result text ("This quiz has closed, so it can't be retaken."; "Your access to this course has ended.").
    QA flagged the plan's "Try again" as stale (deviation (d), spec rule 13). Precedent for "button
    becomes unavailable, with the reason" on `course_form_complete`.
  - Refusal writes nothing: QA 3.3 checked that no `FormProgress` was created for a refused start.
  - Its prior-art note (research_prior_art.md): enforce on read, and "submit is never gated" so an
    already open attempt is not stranded. Matches this idea's "continue is never blocked".
  - Open QA bug B1 (the dashboard "Closed" line dropped the item name) is a reminder: every new
    refusal wording must be checked on all surfaces that render the state (dashboard, TOC, header,
    results), not just the start page. Status in that report was UNRESOLVED; check whether it was
    since fixed before relying on the copy.
- The start page restyle (`spec_dd/3. done/2026-09-08_17:31_better-form-start-page/`): CTA reads
  "Start Form" / "Continue Form" / "Try Again"; the page lists the last five attempts with date and
  score; its QA asserts "Failed quiz -> Try Again, following topic still locked". Any wait or cap UI
  has to coexist with that attempts list and the CTA states. Also that spec noted preview/direct-reload
  behaviour (start page must render fully on reload and back-button): a server-rendered state with
  a client countdown must still render correct on reload.

## 2. Here: gotchas from the SACAA specs that touched the same code

Source files: the done spec folders for served-paper-record, shuffle, question-pools, attempt-review and
quiz-declaration; skimmed by search, so cross-check the folder's `1. spec.md` before relying on a detail.

1. **The start gate is shared, and a new gate step must run before anything that writes.** Quiz
   declaration (spec at `spec_dd/3. done/2026-11-25_11:00_sacaa-complianc-deletion-and-declaration-2-quiz-declaration/1. spec.md`)
   made `form_declaration` run "the same access, blocked and closed checks as `form_start`, and the same
   `course_progress is None` redirect, before reading or writing anything"; the gate comment in
   `_form_start_gate` (`freedom_ls/learner_interface/views.py:1978`) says the gate must come before minting
   the attempt and before `finalise_stale_incomplete`, because both write. Consequence for this spec: the
   cap/wait check goes in the gate (so `form_declaration` is covered) *and* is re-checked inside
   `start_attempt` under the lock; and the idea's "existing stale-attempt handling runs first, then the
   count is read" has to be reconciled with the gate's "before `finalise_stale_incomplete`" comment: a
   stale open attempt completes (and so counts) only inside `start_attempt`, after the gate has run. The
   gate may therefore read a count that is one too low. This ordering needs a decision in the spec.
2. **Declaration is created inside the same `atomic()` and `CourseProgress` lock as the attempt**
   (spec rule near line 120-155: declaration created after `get_or_create_incomplete` in the existing
   `atomic()` block; "the lock serialises two POSTs for one record, so the insert needs no
   `IntegrityError` handling"). A refusal in `start_attempt` must therefore raise before the declaration
   insert and roll back cleanly; and `form_declaration` redirects to `form_start` when a signed open
   sitting exists, so a refused start must not leave an unsigned open sitting. "Try Again" asks for a
   fresh declaration per attempt, so a cap refusal on Try Again should land before the declaration
   page, not after the learner has signed.
3. **Other callers mint sittings and bypass the gate.** The declaration spec records that
   `course_applications` mints sittings itself, including for anonymous applicants, so "no gate would
   run" there. Attempt limits are QUIZ-only, so applications (a different strategy) are unaffected; say
   so explicitly in the spec rather than leave it implicit. `form_submit_and_exit` and
   `finalise_stale_incomplete` also complete sittings with no gate; those are completions, not starts,
   and are what the count reads.
4. **None-default trap in `content_save`.** `content_save.py:330` dumps with `exclude_none=True`, so a
   field defaulting to `None` (the existing `quiz_show_incorrect` / `quiz_pass_percentage` are the cases)
   drops out and removing a key from front matter later does not reset the stored value. The shuffle spec
   avoided this for its three knobs by defaulting to `False` (shuffle `research_codebase.md` section 1:
   "a non-QUIZ check must test `True`, not 'is not None'"). Options for `max_attempts` and the wait list:
   a non-`None` sentinel (for example `0` = no limit, `[]` = no waits) that survives `exclude_none` and
   resets on removal, with the QUIZ-only `knobs` check testing for "not the default" rather than "not
   None". This is an inference from the code, not something an earlier spec tried for a nullable.
   Also check how a list field (JSON list) is dumped and compared; no earlier knob is a list.
5. **QUIZ-only knob pattern.** Shuffle added `validate_quiz_fields` style checks in
   `freedom_ls/form_engine/schema.py` and a cross-file pass in `content_engine/validate.py`
   (`validate()` appends passes; the shuffle one was added there). New knobs need: schema field, `Form`
   model field plus migration (latest was `form_engine/0010`; there will be later ones now), the
   bundled `claude_plugins/fls-content/validate/schema.py` copy, `form-files.md`, educator preview rows,
   demo content, and a check of `form_engine/admin.py` for explicit `fields`/`fieldsets` lists.
6. **Page-level QA bugs that recurred.** Shuffle QA B1 (long form pages scrolled the whole document
   as well as the player region) and B2 (placeholder demo picture caption "Landscape 800x450") were fixed.
   Question-pools QA B1 (demo intro mentioned the pool and draw on the learner start screen) stayed
   UNRESOLVED as a product decision, a warning that demo copy leaking mechanism details gets flagged.
   For this spec: demo quiz copy on `3. quiz/form.md` should not explain the limit mechanics beyond what
   the new start-page lines say. Attempt-review QA B1 (mobile fail, since fixed) shows the new pages need
   a mobile pass at 375px: the wait line plus countdown must not overflow.
7. **Dev DB clash in QA.** Question-pools QA noted a plain `content_save demo_content DemoDev` fails
   on a dev DB with stray same-UUID example.com copies. A QA plan for this spec that needs a time-
   dependent state (wait running) will need seeded `completed_time` values via the qa-data-helper rather
   than waiting real time; deadlines QA did the same ("extra attempts seeded through the qa-data-helper").

## 3. Here: countdown/timer UI

- No spec in the done folders built a live countdown. `spec_dd/2. in progress/sacaa-compliance-assessment-controls-3-test-time-limit/idea.md` is the sibling that will need a timer; not read in
  detail. Worth checking before writing this spec so that the two do not invent two countdown
  components. The stack is HTMX + Cotton components (`claude_plugins/fls-dev/resources/templates_and_cotton.md`),
  not read for this report.
- `answers.md` decides: live countdown, button becomes active in place without reload, server re-checks
  on click. The unresolved design edge is clock skew: the browser countdown is computed from a server
  time or from the client clock. Best practice (my inference): send the remaining seconds or the
  absolute `opens_at` ISO timestamp plus server "now" at render, and treat the click-time server check
  as the only authority; if the server still refuses on click (skew, or a later failed attempt), render
  the refusal with 422 per the project's HTMX convention (CLAUDE.md), updating the countdown.
- I found no `.claude/` or `claude_plugins/fls-dev` rule file about refusal, start-page or results-page
  look beyond the templates/Cotton doc and `sdd:capture-feedback`; a `Glob` for feedback or rules files
  under `claude_plugins/fls-dev` returned nothing. The per-spec `3. frontend_qa.md` files are the only
  behaviour record.

## 4. Elsewhere: known problems with retake limits and cooldowns

Brief, all from Moodle (core "Attempts allowed" plus "Delay between attempts"/"Time between attempts").

- **Which timestamp the delay counts from, and abandoned attempts.** Moodle developer page
  https://docs.moodle.org/dev/States_of_a_quiz_attempt (marked obsolete, so a design discussion, not
  current behaviour) lists tracker issue MDL-20956, "Student can't start new attempt if a quiz has time
  limit between attempts": a student who closes the browser instead of submitting leaves an
  overdue attempt; neither student nor teacher can submit it; if the student returns and continues, the
  attempt is submitted then, so a delay measured from that moment can leave the student stuck. The page
  proposes counting the end as submission for untimed quizzes and `min(time expiration, submission)` for
  timed ones. Lesson for this spec: a wait measured from `completed_time` is fine only if expiry and
  disturbance set `completed_time` at the moment of expiry/disturbance, not at the later cleanup. This
  is the boundary with specs 3 and 5, so record the requirement there. The idea's "stale-attempt handling
  runs first" choice is the same risk: an attempt completed late by `finalise_stale_incomplete` gets a
  late `completed_time` and so a late-starting wait.
  Tracker entry itself not opened (page gives the ID only); see also https://tracker-old.moodle.org/browse/MDL-55815 as another quiz-attempt delay
  result in the search, not read.
- **Teacher bypass without deleting attempts.** Same dev page says a per-student bypass of the delay was
  built in Moodle 2.0 so teachers need not delete the earlier attempt (deleting attempts is the
  workaround people reach for). This spec rules out per-learner overrides; course restart (spec 7) is the
  sanctioned reset. Expect support asks for "give one learner one more go" and note the restart path in
  educator docs.
- **Overrides stack leniently.** Moodle docs https://docs.moodle.org/502/en/Quiz_overrides: a user
  override beats group overrides, and with several group overrides the most lenient value applies per
  field, including attempts. Not applicable (no overrides here), but is why a per-cohort override is a
  deliberate non-goal worth keeping.
- **Plugin existence shows the gap.** Core only offers one delay or a two-step delay (`delay1` after the first
  attempt, `delay2` after later ones); a plugin, "Delayed attempts in quizzes"
  https://moodle.org/plugins/quizaccess_delayed (page returned 403 to the fetch tool, so its detail
  is unread), exists to extend it. The idea's list-of-waits with the last entry repeating is the
  generalisation of `delay1`/`delay2` and matches that shape.
- Search did not find forum threads specific to cooldown complaints; claims beyond the above are
  unverified.

## 5. Decisions already taken that the spec can lean on

From `answers.md`: a passed learner is refused a new attempt (latest completed attempt passed); wait list
is whole minutes, non-empty positive numbers, not required to be non-decreasing; live countdown, button
activates in place without reload, server re-checks on click; stale open attempt handled first by
`start_attempt`, then the completed count read.

## 6. Open points to resolve in the spec

1. Gate-versus-`start_attempt` ordering for stale open attempts (section 2.1).
2. Sentinel defaults for the new front matter fields that survive `exclude_none` (2.4).
3. `completed_time` for expiry/disturbance must be the event time (section 4); coordinate with specs 3 and 5.
4. Where the passed-refusal and cap-refusal land: a refusal outcome type from `_form_start_gate`, shown
   on the start page rather than a bare redirect (deadlines precedent: redirect to a notice page that
   states the reason).
5. Reuse of one countdown component with spec 3.

Sources:
- https://docs.moodle.org/dev/States_of_a_quiz_attempt
- https://docs.moodle.org/502/en/Quiz_overrides
- https://moodle.org/plugins/quizaccess_delayed
- https://tracker-old.moodle.org/browse/MDL-55815

status: ok
