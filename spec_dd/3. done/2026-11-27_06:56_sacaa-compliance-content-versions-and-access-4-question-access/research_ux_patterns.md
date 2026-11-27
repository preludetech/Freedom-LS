# Research: UX patterns for withheld content inside a visible page

Topic `ux_patterns`. Inputs: `idea.md`, `answers.md`, the `panel-framework` and `educator-interface` skills, the `brand-guidelines` skill and its `voice.md`, and two web searches.

## 1. What the web sources say

### Hide or disable an action

- Smashing Magazine's "Hidden vs. Disabled In UX": hide an action when the cause is permissions, access control or security. Disable it, with an explanation, when the cause is a state the user can change. Hiding costs discoverability. https://smashingmagazine.com/2024/05/hidden-vs-disabled-ux/
- Wix Design System: a disabled element says why in a tooltip on hover and on focus. Use `aria-disabled`, and keep the element focusable so it is announced. https://dev.wix.com/docs/wix-design-system/guidelines/interaction-behavior/disabled-states
- Red Hat OCM UI (an internal rule, not an empirical study): a control the user cannot use for permission reasons is disabled and shows a tooltip with the reason. In table rows, disable the menu items, not the menu trigger. https://issues.redhat.com/browse/OCMUI-3493
- A Django forum thread leans toward disabling with a tooltip: https://forum.djangoproject.com/t/disable-elements-based-on-permissions/13436
- UXtigers describes a third option: leave the control active and answer with an explanation. https://www.uxtigers.com/post/inactive-buttons

The sources disagree. The security guidance says to hide. The accessibility and discoverability guidance says to disable and explain. None of them is empirical research.

Caveat on the tooltip advice: hover tooltips fail on touch screens. The brand voice already asks for the reason to sit beside the control instead (section 3).

### A notice before opening confidential content

The nearest pattern is "break the glass" in health records. A flagged record opens only after a warning. The user states a reason or confirms, and each access is audited and reviewed by compliance.

- AMA explainer: extra step plus a documented reason before a flagged chart opens. It argues for opt-in on the confidential items instead of friction on everything. https://www.ama-assn.org/practice-management/digital-health/myth-or-fact-universal-break-glass-ehr-functionality-must
- AMA, on whether break-the-glass is required: https://www.ama-assn.org/practice-management/digital-health/are-break-glass-functions-required-employee-ehr-access
- University of Iowa Epic page: warning, reason, an audit trail, and a message to the compliance office. https://epicsupport.sites.uiowa.edu/epic-resources/break-glass

Lessons that carry over:

- The warning comes before the content renders, and the access is logged only after the user proceeds.
- Friction belongs on the confidential item only. Putting it on everything trains people to click through.
- A required reason is the heavy form of the pattern. This spec does not ask for one (see "Out of scope" in `idea.md`). A notice plus a confirm is the light form.

The search results gave no guidance on the warning text itself. The wording below is my own.

## 2. What the project already does

- `panel-framework` skill, Tables: "A row the viewer cannot act on states its fields and leaves its buttons column empty: no note saying why, no link to the page where it can be changed." This is the project's rule for a row action the viewer lacks the capability for. It is hide, not disable, and the rule is explicit and tested by the visual checklist.
- `educator-interface` skill, Staff roles: no explanatory note and no link to where the thing could be changed (an organisation role in a cohort Staff list says only "Organisation admin").
- Brand `voice.md`, Dialogs: "A disabled action shows its reason beside the control, and the control names it with `aria-describedby`." This applies to a disabled action, one that is blocked by a state. A permission refusal that the person cannot fix in the page falls under the panel-framework rule above.
- Withheld content has a precedent in `educator_interface/templates/educator_interface/panels/course_content.html`. A course the organisation sees only through a registration shows `<c-panel-empty-state message="Content preview isn't shared with your organisation." data-testid="preview-withheld" />` in place of the outline. The `educator-interface` skill adds that the Reference panel "shows the same withheld note".
- Panel-framework Dialogs: a refusal renders through `refusal_response(ctx, *, title, message, status=422)` in `modal/message.html`, which ends in a Close the footer focuses. A confirmation is a modal in `#app-modal`. A confirm dialog "states what is true now and what the action changes". A preview opens in `#app-modal` at wide size, titled "<title> (Preview)", and "no callout says it is a preview".
- Notices on panel pages use `<c-panel-callout tone title>`, never `<c-callout>` or `<c-admonition>`, and never a hand-built box. Tone follows the effect.
- `get_known_blocked_reason(ctx, instance)` on `DeleteAction` is the existing way to state a refusal before the dialog opens.
- Brand voice, principle 5 and the visual checklist: use the plain word for a refusal. Error messages name the problem, suggest a fix and leave blame out. Routine actions end on a full stop.
- The phrase "no permission" in the idea's recommended note is acceptable. "Hidden" is a plain word and cannot be misread as "not yet".

## 3. Patterns applied to each case in this spec

### 3.1 Outline rows whose preview is withheld

Options:

- (a) Hide the Preview button on the quiz rows and leave the buttons cell empty.
- (b) Show a disabled Preview button with a reason beside it.
- (c) Leave the button and refuse in a dialog on click.

Recommendation: (a), by the project's own rule, and so that it matches the idea ("Without the permission the action is not offered and a direct request is refused").

Reasons:

- The panel-framework rule names this exact situation (a row the viewer cannot act on). Option (b) adds a note the rule forbids.
- A disabled button repeated on every quiz row is noise. A page with many quizzes would show many disabled buttons, each with the same reason.
- The Smashing and Red Hat guidance splits on this, but the project rule decides it. The security case (the person cannot self-serve the permission) is also the case where Smashing says to hide.
- Topic, activity and survey rows keep their Preview button (per `answers.md`), so the table still has working actions. A quiz row with an empty actions cell reads as "nothing to open here".

Trade-off to name in the spec: a person may wonder why only some rows have Preview. Hiding costs discoverability. Option (c) fixes that but offers an action that always fails, which is worse. If the spec wants a single explanation, put one line at the panel level, not on each row. For example, add a `<c-panel-callout tone="info">` in the `panel_header` block, where the "still in development" callout already sits, saying "Quiz previews are hidden: you do not have permission to view questions." That fits the existing `panel_header` slot and keeps the rows clean. It is a choice for the spec: the rule forbids a note on a row, not a note on the panel. The shown-once, only-when-quizzes-exist condition needs checking so a course with no quizzes shows nothing.

Direct request: refuse with `refusal_response` (`modal/message.html`, 422 for HTMX per project convention), not a bare 403 page. Plain wording: title "Quiz preview is hidden", message "You do not have permission to view questions. Ask an organisation admin for the question bank viewer role." Check against the role name the spec settles on. An org admin may not be able to grant it, so the "who to ask" text should be generic ("someone who can give this role") unless the spec knows otherwise. The voice sample "Someone who can give this role can give it back to you" is the project's phrasing for this.

Prev/Next stepping: the preview sequence (`preview_sequence`) steps through items. A quiz in the sequence that the viewer cannot open needs a decision: skip it, or stop at it. Skipping silently is the common choice, because the stepping footer has no place for a reason. State the choice in the spec.

### 3.2 Report sections replaced by a "hidden" note

This follows the `preview-withheld` precedent: a `<c-panel-empty-state>` or a `<c-panel-callout tone="info">` in the panel's position, with the rest of the panel still shown.

Recommendations:

- Keep the note in the position of the gated content, so the report's structure does not shift between holders and non-holders. Keep per-quiz scores and counts visible, as `idea.md` recommends.
- One line, plain: "Question detail is hidden: you do not have permission to view questions." This matches `idea.md` and the voice rules (names the problem, no blame). Consider whether to add a fix ("Ask for the question bank viewer role"), per the error-message rule "suggest the fix". It is an option, not a requirement. Do not link to a page where it can be changed (panel-framework rule).
- Use `<c-panel-callout tone="info">` if the note sits above retained figures. Use `<c-panel-empty-state>` if the whole panel body is replaced. Never `<c-callout>` and never a hand-built box (enforced by invariant tests named in the skill).
- A note is better than omitting the section silently. A reader of a report should not take its absence for "there is no wrong-answer data". This is the main reason not to follow the "omit with no trace" pattern here, which differs from the row-action rule because a missing section looks like a finding, where a missing button does not.
- In the PDF there is no hover or focus. The note must be real text on the page, one line in place of the confusion tables and per-learner wrong answers. The PDF also needs to carry that fact in a form a later reader can see: a person who gets the file later should see why the detail is missing. The generation date is already displayed by the report's `as_of` stamp pattern (panel-framework: "As of <time>"), so the reader can tell the note describes the generator's permission at that time. Wording idea: "Question detail is not included: the person who generated this report did not have permission to view questions." This is the true statement, since the PDF decision is made at generation. The on-screen wording ("you do not have permission") would be false in a PDF read by someone else.
- Cached panel: the screen note and the detail version must not share a cache entry (idea's open item). From a UX view this is a safety property, not a style one: serving a holder's panel to a non-holder is a leak, and serving the note to a holder is only an annoyance.

### 3.3 Telling a user their view is being logged

Options:

1. Passive notice only: a line in the content, "This view is logged."
2. Notice and confirm before opening (break-the-glass light).
3. Notice plus a required reason (break-the-glass heavy).
4. No notice. Log silently.

Observations:

- The idea scopes this to: every view writes one entry, no dedupe, no throttle, no reason. Option 3 is out of scope. Option 4 is weak for a compliance audit: a user who does not know they are logged is not deterred, and the AMA material says deterrence and awareness are the point of the warning.
- The project's panel rules constrain the form. A preview "carries no 'this is a preview' callout", so the title says it. There is no rule against a notice about logging. Panel-framework says a notice in a dialog is `<c-panel-callout>`.
- Where the log is written matters. The idea says the entry is written only on the HTMX request that renders the questions. A confirm step in front of the render is therefore consistent with the log rule: the confirm dialog writes nothing, and the request that follows it writes one entry. This also solves "prefetch writes nothing" for free.
- An interstitial on every open adds a click on every quiz preview for every holder, and each Next step in the stepping footer would hit it again if each quiz is a separate open. That is the friction the AMA warns about. Mitigation: show the confirm once when opening from the outline row, not on Next/Previous within one preview session. But the idea says each render writes an entry, and "a paging request that continues an earlier open records nothing", so the notice and the log should follow the same boundary: the notice appears on the request that logs.

Recommendation for the spec to weigh, lightest first:

- Minimum: a persistent one-line `<c-panel-callout tone="info">` inside the preview dialog and the report panel for holders: "Viewing these questions is logged." It is true after the action and says what is true now. It does not delay the user. It does not break the "no preview callout" rule, which concerns saying the dialog is a preview.
- Stronger, if the audit expects informed access: a confirm dialog (`ConfirmAction`) before the first quiz preview opens: title "View quiz questions?", body "Each time you open a quiz's questions, FreedomLS writes an entry to the audit log with your name, the course and the time." Buttons: Cancel at the left, "Confirm" (the project's name for a final confirm button) at the right, primary variant, since it does not delete. Loading text ends in "…". The sentence in the body is true after the action, per the voice rule.
- Do not add a required reason. If the spec adds one later, `ReasonMixin` with `reason_required = True` is the existing mechanism.

For the PDF: the notice goes where the person clicks "Download", not in the file. A holder who downloads a PDF that carries the detail gets one entry per download (per `answers.md`), so the download control should say so, for example a short line beside it or in the confirm.

Wording for the audit message must match what is logged: name, course, time. Do not promise more. The exact fields come from the spec's audit details (ids and labels only).

Accessibility: the callout needs no `role="alert"` on load. A confirm dialog gets focus on its Cancel (the footer's `focus_cancel` default), which is the safe default for a gate.

### 3.4 Downloads refused for permission reasons

Cases from `answers.md`: a PDF that carries the detail, downloaded by someone without the permission; and older PDFs with no record, treated as carrying the detail.

Patterns:

- Do not offer a download link that will be refused if the page knows it will be. For a report list or history of generated PDFs, hide the Download button on a file that carries the detail when the viewer lacks the permission. This is the row-action rule again (button cell left empty, no note).
- A direct request (stale link, bookmark, a PDF generated by a holder and opened by someone else) is refused with a clear response: for HTMX, a `modal/message.html` dialog via `refusal_response`; for a plain browser request, a 403 page. A plain navigation to a download URL cannot render a dialog, so a normal 403 with a human message is needed. It must not return a 404 that suggests the file is gone, and it must not reveal the filename or content. Wording: "You do not have permission to download this report. It includes question detail." Refusal first, reason second, no blame.
- The refusal should write no audit entry as a view (nothing was viewed). Whether to log a refused attempt is a separate decision for the spec; `idea.md` does not ask for it.
- An older PDF has no flag and is treated as carrying the detail. A non-holder would see no Download button on every old report. That can look like a bug on the first visit after release. Mitigation, a one-time line in the docs and release notes, plus a regenerate path: the button to generate a new report stays available and the new file carries no detail for a non-holder. Because "Generate a new report" is already the project's action, a refused download can point to it in the message: "Generate a new report to get a copy without question detail." This is the voice rule "suggest a specific fix". It is only valid if a non-holder can generate. The spec should confirm.
- Never fall back to silently serving a stripped copy: the file on disk is a fixed artefact and it would be a different document than the user clicked.

## 4. Summary of recommendations

| Case | Pattern | Component / mechanism | Wording sketch |
|---|---|---|---|
| Quiz outline row, no permission | Hide the Preview button; empty actions cell | Existing row action `has_permission` | none on the row |
| Same, panel level (optional) | One info callout in `panel_header` | `<c-panel-callout tone="info">` | "Quiz previews are hidden: you do not have permission to view questions." |
| Direct request to a quiz preview | Refusal dialog, 422 | `refusal_response` / `modal/message.html` | "You do not have permission to view questions." |
| Report quiz panel, screen | Note in the panel's place; scores stay | `<c-panel-empty-state>` or callout | "Question detail is hidden: you do not have permission to view questions." |
| Report PDF | One line of text in place of detail; written from the generator's point of view | PDF template | "Question detail is not included: the person who generated this report did not have permission to view questions." |
| Logging notice | Persistent info callout in the preview and the report panel; optionally a confirm before first open | `<c-panel-callout>`; `ConfirmAction` | "Viewing these questions is logged." |
| Download refused | Hide the button when known; 403 with a plain message on direct request | row action; response | "You do not have permission to download this report. It includes question detail." |

## 5. Decisions the spec must make

1. Hide only, or hide plus one panel-level note, for quiz rows without permission.
2. Logging notice: persistent callout only, or a confirm before opening. If a confirm: once per open from the outline, and what Next/Previous does.
3. What the preview stepping footer does at a quiz the viewer cannot open (skip or stop).
4. Whether the PDF note is worded from the generator's point of view (recommended).
5. Whether a refused download, or a refused direct preview request, writes anything to the audit log (not requested by the idea).
6. Whether a non-holder can generate a new report, so a refused download can point to that fix.
7. Who to name in "ask for the role" copy, since the role name is still open in `idea.md`.

## 6. Sources

- https://smashingmagazine.com/2024/05/hidden-vs-disabled-ux/
- https://dev.wix.com/docs/wix-design-system/guidelines/interaction-behavior/disabled-states
- https://issues.redhat.com/browse/OCMUI-3493
- https://forum.djangoproject.com/t/disable-elements-based-on-permissions/13436
- https://www.uxtigers.com/post/inactive-buttons
- https://www.ama-assn.org/practice-management/digital-health/myth-or-fact-universal-break-glass-ehr-functionality-must
- https://www.ama-assn.org/practice-management/digital-health/are-break-glass-functions-required-employee-ehr-access
- https://epicsupport.sites.uiowa.edu/epic-resources/break-glass
- Project: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`, `.claude/skills/brand-guidelines/SKILL.md` and `voice.md`, `freedom_ls/educator_interface/templates/educator_interface/panels/course_content.html`

Note: the web findings come from search-result summaries, not a full read of each page.

status: ok · reason: complete
