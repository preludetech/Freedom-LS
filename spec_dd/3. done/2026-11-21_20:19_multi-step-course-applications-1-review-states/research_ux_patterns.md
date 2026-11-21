# Research: UX patterns for the applicant status page

Topic `ux_patterns`, spec `multi-step-course-applications-1-review-states`.

## Inputs read

- `idea.md` and `answers.md`: withdraw asks for a confirm dialog first (POST after confirm); the dashboard panel keeps rejected and approved applications visible, not only active ones; reject message is required.
- Brand voice: `.claude/skills/brand-guidelines/voice.md` (the skill lives at `.claude/skills/brand-guidelines/`). Relevant rules:
  - Direct, specific, no SaaS phrasing.
  - Errors: name the problem, suggest the fix, leave blame out. Routine actions end on a full stop.
  - Confirm dialogs: state what is true now and what the action changes. Every sentence stays true after the action. "You" when acting on yourself. The final button says "Confirm" or names the change. Two buttons in a row never share a bare verb.
  - Dates render with `<c-date>` / `<c-datetime>` (`3 Nov 2026`), never hand-formatted.
  - Learner-facing UI carries the deploying organisation's brand.
- Existing templates in `freedom_ls/course_applications/templates/course_applications/`:
  - `application_status.html`: two branches on `is_email_verified` ("Your application" with "currently pending review", or "Check your email"). A NOTE comment marks where the state badge, reviewer message and withdraw action go.
  - `partials/dashboard_applications.html`: rows use `<c-chip>` with `variant` "info" ("Pending review") or "warning" ("Incomplete"). The CTA reads "View my application" or "Continue application". The row is a `c-course-row-shell` with a stretched title link and a `c-button` footer.
  - Existing components to reuse: `c-chip` (variants info, warning, and likely success, danger and neutral; check), `c-button`, `c-page`, `c-date`.

## External patterns

1. **State shown as plain text first, a badge second.** The GOV.UK confirmation pattern says to state who has the application and what happens next, in specific sentences ("We've sent your application to X. They will contact you either to confirm… or to ask for more information."). Source: https://design-system.service.gov.uk/patterns/confirmation-pages/. Apply it here: each state gets one sentence on what is true now and one on what happens next. The chip is a scan aid, not the only carrier of meaning (colour must not be the sole signal).
2. **Bookmarked pages must respond helpfully.** The same GOV.UK page says users bookmark the page as a receipt, and that it should still answer sensibly later. The status page is the bookmarkable URL, so every state needs a body, including closed ones, each with a next step.
3. **Destructive actions.** The GOV.UK warning-text component has no destructive-action guidance (https://design-system.service.gov.uk/components/warning-text/). Common practice, and FLS's own voice rules: a secondary-styled (not primary) button, a confirm step that names the consequence, and a final button that names the change. Withdraw is reversible only by applying again, so the confirm says so.
4. **Rejection.** Common practice in application and job-portal UIs: lead with the outcome, put the reviewer's message in a quoted block labelled as from the reviewer, avoid red alarm styling and blame, and always follow with what the applicant can do next. This is a convention, with no single authoritative source. GOV.UK's content guidance on plain, specific language (https://www.gov.uk/guidance/content-design/writing-for-gov-uk) supports saying "was not approved" rather than softening it to the point of ambiguity.
5. **Closed items on a dashboard.** Common practice: active items first, closed ones below and visually quieter (neutral chip, no primary CTA). Decisions the applicant has not yet seen deserve emphasis. Withdrawn applications are the applicant's own choice, so they need no decision surfacing.

## Proposed wording

Chip labels (dashboard and status page), with `c-chip` variant:

| State | Chip | Variant |
|---|---|---|
| draft | Not submitted | warning |
| submitted | In review | info |
| approved | Approved | success |
| rejected | Not approved | danger, or neutral (see decision 2) |
| withdrawn | Withdrawn | neutral |

"Incomplete" and "Pending review" in the current template are replaced. "Pending review" becomes "In review", because the idea settles that there is no `under_review` state, and "In review" must not imply a reviewer has picked it up. Check this against the glossary. "Awaiting review" is a safer alternative and is the recommendation: it is true even when no one has opened it.

**Revised chips: draft "Not submitted", submitted "Awaiting review".**

Status page (heading, then body). The `is_email_verified` branch still applies on top of `submitted`.

- **draft** — H1 "Your application". "You started your application for **{course}** but have not submitted it. Finish it to have it reviewed." CTA primary "Continue application". Secondary "Withdraw application".
- **submitted** — H1 "Your application". "Your application for **{course}** is with the reviewers. We will show their decision here. You do not need to do anything now." Shows "Submitted {date}" via `<c-date>`. Secondary "Withdraw application". (Existing "No action is required" is kept in spirit. Drop "You will be notified", because the spec has no email, and promising a notification would be false.)
- **approved** — H1 "Your application was approved". "Your application for **{course}** was approved on {date}." Spec 3 owns registration, so this spec must not promise access. Neutral line only: "Approved on {date}." Spec 3 adds the next step. Do not write "You can start the course", as it would be untrue until spec 3 lands.
- **rejected** — H1 "Your application was not approved". "Your application for **{course}** was not approved on {date}." Then a labelled block: "Message from the reviewer" followed by the stored message, rendered escaped with line breaks preserved. Then "You can apply again if you want to." and the CTA (below). No red alert box. Use a neutral bordered block (quote style). No "Unfortunately" and no "we regret". The voice is direct and leaves blame out.
- **withdrawn** — H1 "You withdrew your application". "You withdrew your application for **{course}** on {date}. Nobody will review it." CTA "Apply again".

The reject message must reach the applicant verbatim. Never blend it with generic apology text, and never show it on other states.

## Withdraw action and confirm dialog

Per the voice rules (before and after, "you", every sentence true after, button names the change, no two buttons sharing a bare verb):

- Trigger: secondary button "Withdraw application" (form POST inside the dialog, so it works with the Alpine/dialog component used elsewhere; check which dialog component FLS already has before the spec picks one).
- Title: "Withdraw your application?"
- Draft body: "Your application for {course} is a draft. If you withdraw it, nobody will review it, and you can apply again later."
- Submitted body: "Your application for {course} is waiting for review. If you withdraw it, it will not be reviewed, and you can apply again later."
- Buttons: "Keep application" (cancel) and "Withdraw application" (confirm; names the change). The voice rule allows "Confirm" or a named change. A named change is clearer here, and the two buttons do not share a bare verb.
- Do not promise that the answers are deleted or kept unless the service does one of them. Check the spec's behaviour before writing a sentence about the answers. The idea does not say, so leave it out.
- A stale POST (the application was decided while the dialog was open) should land on the status page with a message: "This application can no longer be withdrawn. It was {approved / not approved} on {date}." Name the problem and show the current state, without blame. The service raises, and the view catches the specific exception.

## Apply again (closed-application CTA)

- Label: "Apply again" on the status page (rejected, withdrawn) and in the dashboard row and course CTA. It is a verb phrase naming what the person does. Approved needs no CTA: it shows "View my application" (the registration CTA belongs to spec 3).
- On the course CTA (replacing "View my application" for a closed application): "Apply again", with a small secondary link "View your previous application" so the reject message stays reachable. For rejected applications the dashboard also keeps the message reachable (see below).
- Rejected: "Apply again" is shown plainly. Whether a course allows re-application is not a settled rule in the idea (it settles that re-applying makes a new application), so the spec need not add a cooldown.
- The new application starts fresh, so the page does not say "pre-filled" unless the spec copies answers.

## Dashboard panel

Per `answers.md`, the panel shows active, rejected and approved applications. The idea's "narrows to active" is revised by that answer. Withdrawn is the open point: the answer names only rejected and approved. Recommendation: hide withdrawn from the dashboard (the applicant did it themselves), keep it on the status page URL.

Row design (reuse `c-course-row-shell` and `c-chip`):

- Order: draft and submitted first, then rejected and approved, newest decision first within a group. Pagination (`get_active_applications` is paged) is kept.
- Draft row: chip "Not submitted", the existing hint "Finish your application to have it reviewed." (keep), button "Continue application".
- Submitted row: chip "Awaiting review", button "View my application".
- Rejected row: chip "Not approved", a one-line hint "Decision on {date}. Read the reviewer's message.", button "View my application". Do not truncate the message into the row, since it can be long and sensitive. Answers say the message is visible via the dashboard, so the row links to it. If the spec wants the message in the row, show the first line clamped with a "Read the full message" link.
- Approved row: chip "Approved", hint "Approved on {date}.", button "View my application".
- A closed row is visually quieter: no warning variant, and the "Apply again" CTA sits on the status page and the course CTA rather than crowding the row. Decide whether the row also carries "Apply again". Recommendation: yes for rejected, as a secondary-styled link beside "View my application".
- Rejected and approved rows should not stay forever. Open question for the spec: whether closed rows age out of the panel (for example after the course is registered or after N days). Without a rule the panel grows. Recommendation: no age-out in this spec, as the panel is paged, and record it as a follow-up.
- Screen-reader text: the existing `sr-only` " for {course title}" pattern stays. The panel status region text "Your applications: showing…" stays valid.

Panel heading stays "Your applications". An empty panel renders nothing (existing behaviour).

## Accessibility notes

- State is carried by the chip's text and not colour alone. Heading text changes with state, so the page title (`head_title`) should include the state: "Application (not approved) — {course}".
- The reject block is a `<blockquote>` or a labelled region (`aria-labelledby` on the "Message from the reviewer" heading), not a live alert, because it is not time-critical.
- After a withdraw POST, redirect to the status page and show a one-line confirmation ("Application withdrawn.", routine action ends on a full stop, per voice). Check whether the Django messages framework renders on that page.
- The confirm dialog returns focus to the trigger when cancelled, as the existing dialogs do.

## Open items for the spec

1. Chip labels for submitted: "Awaiting review" (recommended) vs "In review" vs the current "Pending review".
2. Rejected chip colour: danger or neutral. Recommendation: neutral or warning, since the page body carries the message and a red chip reads as an error.
3. Whether withdrawn applications show on the dashboard (recommendation: no).
4. Whether closed dashboard rows age out (recommendation: no, follow-up).
5. Whether the approved page says anything beyond the date (recommendation: no until spec 3).
6. Whether withdraw keeps or deletes the answers (service decision, not UX; the confirm copy depends on it).
7. Check `c-chip` supports `success`, `danger` and `neutral` variants, and which dialog component FLS uses for confirms.

## Sources

- GOV.UK Design System, Confirmation pages: https://design-system.service.gov.uk/patterns/confirmation-pages/
- GOV.UK Design System, Warning text (no destructive-action guidance): https://design-system.service.gov.uk/components/warning-text/
- GOV.UK content design, Writing for GOV.UK: https://www.gov.uk/guidance/content-design/writing-for-gov-uk (cited from general knowledge, not fetched this session)
- Local: `.claude/skills/brand-guidelines/voice.md`, `freedom_ls/course_applications/templates/course_applications/application_status.html`, `.../partials/dashboard_applications.html`

status: ok
