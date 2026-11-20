# Research: UX patterns for inline alerts in app pages

Topic `ux_patterns`, spec `misure-of-admonitions`. Scope: a theme-appropriate static alert for learner pages, educator panels, forms and login, replacing `<c-callout>` (the content-styled box in app pages).

## 1. Key finding: a near-fit already exists

`<c-panel-notice tone title>` (`freedom_ls/panel_framework/templates/cotton/panel-notice.html`) already is a theme-token alert: `rounded-md border p-3 text-sm`, tinted `bg-<tone>/10` with `border-<tone>/20`, tones `info|warning|error|success`, optional bold `title`, no outer margin ("the parent spaces its children"). `error` gets `role="alert"`, `success` gets `role="status"`, `info`/`warning` are read in place.

Rules already in force that constrain the new component:
- panel-framework SKILL.md line 213: "A notice inside a dialog or panel is `<c-panel-notice tone title>` ..., never `<c-callout>` or a hand-built `bg-error/10` box." The invariant test `FORBIDDEN_IN_DIALOGS` (`panel_framework/tests/invariants/test_templates.py:643-649`) bans `<c-callout>` and `bg-error/10` in dialog bodies.
- `<c-panel-notice>` lives in `panel_framework`, but learner pages and login (`base`) cannot depend on it. The spec must decide: promote it to the base app as the general alert (and keep `c-panel-notice` as a thin wrapper or rename), or add a base-app alert and have panel-notice delegate. Either way avoid two near-identical components.
- `<c-callout>` today: `my-6 p-4 border-l-4 rounded-r-lg`, title as `h4 text-xl font-semibold` with a `size-5` icon, slot with `px-4 space-y-4 pt-2`, error text in `text-error` for the whole body. This is the "content-styled" look: heavy left stripe, built-in vertical margin, oversized title, own padding fights the surrounding panel.

## 2. Project rules that apply (quoted)

From `.claude/skills/brand-guidelines/visual.md`:
- "Style through the token and the component, so a theme that repoints one applies everywhere."
- Palette: Signal `bg-error`/`text-error` is "Warm accent: alerts, destructive actions, error text"; Sand `bg-warning` is "Warning: callouts, non-critical alerts"; Forest is "Success".
- Contrast: "Sand and Forest are background colours only: as text on a light background they fail contrast. For status text on a pale tint, use the `-light` pair." "Signal is dark enough to set error text directly on white and on Chalk". Tested pairing: Midnight on Sand 10.8:1 "Warning callouts".
- UI principle 3: "Surfaces stay flat; a shadow, border or rule appears only where it does a job ... no box around each item in a group, no box inside a box".
- Principle 4: "Things line up: ... Blocks start and stop on their container's padding."
- "Icons are single-colour outline icons, placed through `<c-icon>`."
- Components table: "A callout in a page: `<c-callout level=... title=...>`" (the row to be replaced); "A page a person cannot use (closed or blocked): A large centred `<c-icon>` (`size-12`) with the explanation as plain text under it, never a callout box"; "A callout in course content: `<c-admonition ...>`"; "A status badge" is `<c-panel-status-badge>` (a state of a record is a badge, not an alert).
- "Where you do write utilities, keep to Tailwind's spacing scale and use `rounded-md`".
- "Separate outcomes get separate panels. A result page puts what succeeded and what failed in two sibling panels, never one card holding both."
- "Headings, body text, links, lists ... take no classes." (so the alert's inner text should not need classes).
- Checklist: "A page a person cannot use shows a large centred icon with text under it, not a callout."

From `.claude/skills/brand-guidelines/voice.md`:
- Error messages tone: "Human, brief, helpful. Name the problem, suggest the fix, leave blame out." "Name the specific problem, suggest a specific fix, in plain language. ... Routine actions end on a full stop."
- Examples: good "This email is already registered. Try signing in, or use a different email."; bad "Error 409: Duplicate entry." Good "Progress saved. You're 60% through this module."; bad "Success! Your learning journey progress has been updated."
- "A list page opens with its heading and its toolbar, so the list starts at the top. Help for the page lives in a dialog the page opens, or in the docs." (no explanatory banner above a list.)
- "A disabled action shows its reason beside the control" (reason is body text by the control, not an alert elsewhere).
- Empty state sample: "No courses yet. Drop some Markdown files ... [See the docs ->]" (plain sentence plus link; `<c-panel-empty-state>` owns tables).

From `claude_plugins/fls-dev` panel-framework SKILL.md:
- Line 151: "An empty table shows `<c-panel-empty-state>` inside the data table's empty row".
- Lines 293-295, 398: a notice or error summary that takes focus (`tabindex="-1"`) "shows no outline. One shared rule does this."
- Dialogs: `partials/error_summary.html` is the validation-summary pattern; `<c-panel-notice>` the notice pattern. These are two distinct jobs and the new alert should not absorb the error summary.
- Body text in a dialog is one size; "Lists, consequences, notices and errors in the body take no `text-sm`" (note: `c-panel-notice` itself sets `text-sm`; check this is consistent when the alert is shared into dialog bodies).

Current callout usage (all to migrate): login "New here?" (info, titled, a prompt more than an alert); applicant_details "We couldn't use those details" (error, titled, form-level); check_your_answers (error body-only, success body-only); form_page (info); educator `course_content` panel (info, `class="my-0"` to cancel margin); form_engine `answer_errors` (two titled errors); `question.html` (dev-only unhandled-type error); learner `course_detail` (info + warning); panel-framework reference example.

## 3. General pattern guidance (web)

### Choosing the channel
- NN/g: choose by type, urgency and whether the user must act. Validations (errors in the user's input) go inline next to the field; notifications are system events; toasts are "passive, low-stakes feedback like confirmations", and "Toasts are a poor choice for errors. ... Errors that need correction should stay visible and be placed inline or near the affected element." Put feedback "where the user is focused". https://www.nngroup.com/articles/indicators-validations-notifications/
- Carbon: inline = action status in task flows, top of main content or near the item; toast = time-based, brief, top right, cover content so information must exist elsewhere; callout = contextual info at page load, never success/error (those are post-action feedback). https://carbondesignsystem.com/components/notification/usage/
- GOV.UK: do not use a banner for validation errors; use field error messages plus an error summary, and never show both a banner and an error summary on one page. https://design-system.service.gov.uk/components/notification-banner/

Decision table for FLS (static, non-dismissible alert, per the answers file):

| Situation | Use |
|---|---|
| Problem with one input | Field-level error under the field (existing form-input error styling), plus an error summary for multi-field forms |
| Form could not be submitted for a reason not tied to one field (non-field errors, "We couldn't use those details", server refusal) | Inline alert, `error`, above the form |
| State of the page the viewer should know, relevant to the task (course in development, closed registration with a path forward, informational context) | Inline alert, `info`/`warning`, in the content flow near what it concerns |
| Result of an action after reload (saved, added) | Inline alert `success` at top of the next page or panel, or the HTMX-swapped panel; toast only if the project already has a toast system (none found; do not add one, per "Don't build functionality that is not explicitly requested") |
| State of a record (Active, Stalled) | `<c-panel-status-badge>`, not an alert |
| A page the person cannot use | Large centred icon + text, never an alert (project rule) |
| A list or table has no rows | `<c-panel-empty-state>` / plain sentence, never an alert |
| Dev-only impossible state (`UNHANDLED FORM TYPE`) | Not UX; keep as plain error alert or raise, a spec decision |
| Marketing-like nudge ("New here? Create an account") | A plain text link line under the form, arguably not an alert at all |

### Placement
- Above the form it concerns, below the page heading; in a panel, at the top of the panel body so it starts on the panel's padding. GOV.UK puts banners immediately before the `h1`; Carbon puts inline notifications at the top of the main content or just above submit/cancel in forms. For FLS, one consistent slot per context is more important than which: heading, then alert, then content.
- Match the width of surrounding content (GOV.UK: same column as the content; Carbon: align to grid columns). An alert must not be wider or narrower than the card or form it sits with.
- Put feedback near where attention is: on a long page, a top-of-page alert after a bottom-of-page action is missed (NN/g).

### Title + body vs body-only
- Carbon: title short, lead with the key point, no final period; body 1-2 short sentences, do not repeat the title; errors must include a next step. https://carbondesignsystem.com/components/notification/usage/
- GOV.UK: title is a short label ("Important", "Success") so meaning does not rely on colour alone; single-line body for short messages. https://design-system.service.gov.uk/components/notification-banner/
- Pattern: support both. Body-only for one sentence (most existing uses); title for the error case that needs a heading ("Missing answers") or when the body is a list. Do not make the title a mandatory restatement. Fits `c-panel-notice`'s optional bold first line.
- FLS voice: a sentence ends in a full stop; name problem and fix.

### Compact vs full-width
- Compact (about `p-3`, base text size) in panels and dialogs; the same size in pages is fine because the "Whitespace is the structure" principle prefers light chrome. The old callout's `p-4` + `px-4` slot + `text-xl` title is the oversize look to avoid. No built-in outer margin: the parent spaces siblings (`space-y-*`), which also removes the `class="my-0"` hack at `course_content.html`.
- Full container width by default; width is the parent's job (`<c-page width>`), not the alert's.

### Tone per severity and colour
- Four tones, consistent with `c-chip`, `c-panel-status-badge` and `c-panel-notice`: info, success, warning, error. Carbon fixes one icon and colour per status (info blue, success green, warning yellow, error red); never rely on colour alone, so keep the icon and for errors/warnings a lead word or title.
- Use `-light`/`on-*` text tokens on tints (visual.md contrast rule). `c-callout` sets the whole error body in `text-error`; `c-panel-notice` sets body in `text-on-surface` with a tinted box, which is more readable and keeps error colour for the border/icon. Prefer the latter.
- Tint + thin full border (`border-<tone>/20`), not a thick left stripe: the stripe is the admonition look and a "border that does no job" under the flat-surface principle.
- Copy tone: errors human, brief, helpful, no blame; success states the fact ("Progress saved."); info states what is true; warning states the consequence.

### Icons
- One single-colour outline icon per tone via `<c-icon>` (`info`, `warning`, `error`, `success` names already used by callout). Decorative: `aria-hidden`; the tone must also be conveyed in text (title or wording) for colour-blind and forced-colours users. `c-panel-notice` currently has no icon; adding one is a design choice for the spec (Carbon and GOV.UK-style systems always show one in inline notifications).

### Accessibility
- Announce correctly: `role="alert"` for errors that appear dynamically (HTMX swaps), `role="status"` for success; `info`/`warning` rendered at page load need no live role (GOV.UK uses `role="region"` + `aria-labelledby` for the important banner, `role="alert"` for success only because it moves focus on load). `c-panel-notice` already follows this split.
- A `role="alert"` present in the initial HTML of a full page load is not reliably announced; on those pages the error summary focus pattern (tabindex -1, no outline) is the mechanism. Static, non-dismissible means no close button, no keyboard handling, and no JS (consistent with the answers file).
- Carbon: screen readers read title and body as one sentence, so do not depend on styling for meaning.

### How many per page
- GOV.UK: at most one banner per page; combine related messages; show only the highest priority if they differ. Carbon: use sparingly, avoid stacking callouts. NN/g: irrelevant interruptions are ignored.
- Practical rule for FLS: one alert per region (page, panel or form), at most two on a page when they sit in different regions; never a success and an error in the same panel (visual.md "Separate outcomes get separate panels"). Never a banner plus an error summary on the same form.
- Existing counter-example to resolve: learner `course_detail.html` renders an info and a warning callout adjacent (lines 76-88); the spec should state which wins or merge.

### Consistency with surrounding cards and panels
- Radius `rounded-md`, tokens only, no shadow, border colour from the tone at low opacity, same horizontal edges as the card or form it sits in (no extra `px-4` indent).
- Inside a `.surface` card or `<c-panel-card>`, do not add another heavy box ("no box inside a box"): a tinted, low-contrast notice is the accepted exception because it carries meaning; keep it flat and compact.
- Sibling spacing from the parent (`space-y-4`/`space-y-6`), not from the alert.

## 4. Recommendations for the spec

1. One general alert component in the base app, tones `info|warning|error|success`, optional `title`, optional icon, default-slot body, no outer margin, `attrs` passthrough (for ids, `tabindex`, `hx-*` targets). Static (no dismiss), per answers.
2. Reuse `c-panel-notice`'s look and ARIA mapping; resolve the two-component overlap explicitly (rename/promote, or make `c-panel-notice` delegate), and update the panel-framework skill sentence and the `FORBIDDEN_IN_DIALOGS` invariant so they still point at one right answer.
3. Rewrite the visual.md components row ("A callout in a page") to the new alert, keep the "page a person cannot use" row, and add rules: placement slot, one per region, no alert for empty states, validation errors or record states. Update the example page in visual.md (it uses `<c-callout>`).
4. Per-site decisions: login "New here?" is a prompt, probably plain text or a link rather than an alert; `question.html` unhandled type is a developer error; educator `course_content` info drops the `my-0` hack; learner `course_detail` pair needs a priority.
5. Invariant test (answered yes): no content-engine cotton component (`c-admonition`, content-only ones) in app templates, plus no `c-callout` once deleted.
6. Copy: review every migrated message against voice.md (name problem, suggest fix, full stop). E.g. "ERROR! UNHANDLED FORM TYPE" violates the voice.

## References
- https://design-system.service.gov.uk/components/notification-banner/
- https://carbondesignsystem.com/components/notification/usage/
- https://www.nngroup.com/articles/indicators-validations-notifications/
- Project: `.claude/skills/brand-guidelines/visual.md`, `voice.md`; `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`; `freedom_ls/panel_framework/templates/cotton/panel-notice.html`; `freedom_ls/base/templates/cotton/callout.html`.

status: ok
