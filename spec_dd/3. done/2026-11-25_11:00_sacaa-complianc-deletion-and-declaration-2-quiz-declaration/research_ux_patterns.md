# Research: UX patterns for the quiz declaration step

Scope per `answers.md`: every attempt signs (no frequency setting, no skipping), own append-only model, Django admin only (no export). Signed-in learners only. The step sits between "Start Form" / "Try Again" and the first page, and guards "Continue Form" and direct fill-page links.

Sources: web findings are cited with URLs. The rest comes from this repo and general accessibility practice. I did not re-verify the general-practice points on the web, and I mark them "general practice".

## Recommendation summary

1. **A dedicated page**, not a modal or inline on the intro page. Use the same centred `max-w-xl` column as `course_form.html`. A full page is the only shape that guards every route (start, try again, continue, direct link) with one redirect.
2. **Enabled submit, validate on submit.** Do not disable the button until the form is valid. If anything is disabled, show the reason beside it and wire it with `aria-describedby` (repo rule, below). The simplest option is to never disable it.
3. **Server-validated, plain POST.** A `<form method="post">` with `required` on both controls. On a failed submit, return 422 and re-render with errors, as the repo's HTMX convention says. Without HTMX, a normal re-render is fine.
4. **Copy**: the heading is "Declaration". The checkbox label is the first-person statement. The name field is labelled "Full name". The helper text says what is stored.
5. **"Try Again" gets a fresh declaration page**, with nothing pre-ticked and nothing prefilled. Each attempt must be its own attestation. Resuming an open, unsigned attempt shows the same page.
6. **After signing**, show a one-line read-only confirmation. It could appear on the first page or in the attempt summary. This is optional and low-cost.

## 1. Page vs modal vs inline

| Option | For | Against | Verdict |
|---|---|---|---|
| Dedicated page (GET shows, POST signs, redirect to first page) | One guard covers every entry route. Works without JS. The back button and refresh behave. Scrolling a long declaration is easy on mobile. Easy to QA and to test (Playwright and plain Django client). | One extra step and page load. | **Recommended** |
| Modal | Keeps the intro page in view. | The "Continue Form" and direct-link routes land on a fill page, so the modal would need to be re-injected on every guarded page. Focus trapping and Escape-to-dismiss both fight a compulsory step. A dismissable modal is a bypass. Poor on small screens. | Reject |
| Inline on the intro page (form beside the Start button) | No extra page. | Does not cover "Continue Form" or a direct fill link. The intro page already carries the authored intro, fact pills and previous attempts, so a form there would be crowded. The start action is a GET link today (`form_start`), so it would have to become a POST. | Reject |

This matches common compliance-attestation flows (exam proctoring "honour code" pages, certification candidate agreements). They are a gate page between the instructions and the first question. This is general practice. I did not find a standard to cite.

Repo fit: `course_form.html` uses `<c-page>`, a badge, an eyebrow and `<h1>`, a left-aligned `c-markdown-container` for authored copy, and a `c-player-footer` with `c-button`. The declaration page can reuse that layout and put the form where the CTA sits. Declaration text is plain text. Render it with `|linebreaks` or the markdown container, whichever the spec picks. Whatever is shown must be byte-for-byte what is stored.

## 2. Button state: disabled until valid vs validate on submit

- Disabled-until-valid hides *why* the action is unavailable. Screen reader users get "dimmed" or "unavailable" and no explanation. Disabled buttons are also not focusable, so keyboard users cannot reach them to discover the reason (general practice, also the GOV.UK and Adrian Roselli position).
- WCAG 2.2 has no criterion banning disabled buttons. Disabled controls are exempt from the 1.4.3 contrast requirement. The issues are 3.3.1 Error Identification, 3.3.3 Error Suggestion and 3.3.2 Labels or Instructions. A disabled button gives none of the three. 3.3.1 and 3.3.3 only trigger once an error is detected, and a never-submittable form never reaches that.
- **Repo rule** (`.claude/skills/brand-guidelines/voice.md`, "Dialogs and list pages"): "A disabled action shows its reason beside the control, and the control names it with `aria-describedby`." The `✅` example is a *disabled button with the reason beside it*, so the repo permits disabling, but only with a visible reason. Validating on submit needs no reason text and is simpler.
- Recommended: leave "Continue" enabled. On submit with an unticked box or a blank name, return 422 and re-render with field errors. Add the HTML `required` attribute as a first line of defence. Browser-native validation gives an instant, localized message. The server check is the authority, because the stored record must never hold a whitespace-only name.
- If the author of the spec still wants instant feedback, a progressive-enhancement hint is fine: Alpine toggles `aria-disabled="true"` plus a visible "Tick the box and type your full name to continue" line. Keep it focusable and block the click in JS. The server still validates. This is more code for little gain.

References:
- WCAG 2.2 Understanding 3.3.1 / 3.3.3 / 3.3.2: https://www.w3.org/WAI/WCAG22/Understanding/
- Redundant entry (3.3.7), fetched: https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html

## 3. Copy patterns

Voice rules (`.claude/skills/brand-guidelines/voice.md`): direct, plain outcomes for adults, "you" when a person acts on themselves, a label names what the thing is, a button names what the person does, routine actions end on a full stop, no SaaS phrasing.

Suggested copy (final wording is for the spec, and the declaration text itself is author-supplied):

- Page heading: `Declaration`. The eyebrow is the form title. This follows the `course_form.html` pattern, where `<h1>` is the form title and the eyebrow is the subtitle.
- Lead-in line, one sentence: "Before you start, read this declaration and sign it."
- Declaration text: a left-aligned block, in a bordered box so it reads as a document. It should be selectable text and never an image or a scrolling iframe.
- Checkbox label, a full-sentence first-person statement: "I have read the declaration above and I agree to it." The legal weight sits in the author's text. The tick only means "I agree to that".
  - Alternative, per the idea's "I declare that…" pattern: the author text itself begins "I declare that I will complete this quiz myself…" and the tick label is "I make this declaration." This is better when the stored text should read as a standalone statement.
  - The default `form_engine` setting text should be written as a complete first-person statement so either label works. Example: "I declare that I am the person named on my account and that I am completing this quiz myself, without help from anyone else."
- Name field label: `Full name`. Helper text, associated by `aria-describedby`: "Type your name as it appears on your ID. FLS stores it with the time and your IP address." The "as it appears on your ID" part is optional. The spec says the name is not compared with the account name, and an ID-matching instruction would imply a check the system does not make. A safer line is "Type your full name. FLS stores it with this declaration, the time and your IP address." This is honest about what is stored, which fits the "show, don't tell" and "respect the reader's time" principles.
- Primary button: `Sign and start`. It names what the person does. A bare "Continue" is also fine. On a resume or a direct link it still fits, because the learner is starting or restarting the attempt. If the page also serves "Continue Form" resumes, consider `Sign and continue`.
- Secondary: a back link (`<c-back-link>`, which the visual guide requires on a page opened from another page) to the form intro page. It is a link, not a button.
- Avoid: "Confirm your integrity", "Please be honest", "unlock your quiz". These are off-voice and condescending.

## 4. Error messages

Follow the voice rule: name the problem, suggest the fix, no blame. A field's own error stays as text beside that field (`text-error text-sm`, as in `consent-checkboxes.html`). An error that belongs to no single field goes in a `<c-callout tone="error">` above the form (`visual.md`).

| Case | Message |
|---|---|
| Box unticked | "Tick the box to confirm the declaration." |
| Name blank or whitespace only | "Type your full name to sign." |
| Both | Both messages, each beside its own field. |
| Rendering failure, missing attempt (a guard redirect, not a field error) | A callout: "This attempt is no longer open. Start the form again." |

Details:
- Re-render with all fields' state preserved. Keep the typed name. Keep the tick as it was.
- Add an error summary (GOV.UK pattern) or at least move focus to the first error. This matters for long declarations that push the fields below the fold on mobile. See accessibility.
- Do not use the words "invalid" or "required" alone ("This field is required" is the generic Django default and does not say which action to take). Override via the form field `error_messages`.

## 5. Accessibility

Checklist for the template (WCAG 2.2 references in brackets). Items that depend on the browser are marked.

- **Label association [1.3.1, 3.3.2, 4.1.2]**: `<label for="id_name">` on the name input. The tick box is wrapped in a `<label>` as in `consent-checkboxes.html` (`flex items-start gap-2`), and a Django `{{ form.field }}` render supplies the `id`. The label text is visible and is the accessible name. Never use a placeholder as the label.
- **Required [3.3.2, 1.3.1]**: HTML `required` on both controls. Also show it visibly ("required" word or marker). Do not rely on colour. A lone asterisk needs an explanation, so state "Both fields are required." once above the form.
- **Helper text [3.3.2, 1.3.1]**: `aria-describedby` points at the helper id. When there is an error, point it at *both* the helper and the error id (`aria-describedby="id_name_help id_name_error"`). Set `aria-invalid="true"` on a field with an error.
- **Declaration text association**: put the declaration in a container with an id and mark the tick box with `aria-describedby` pointing at it. Screen-reader users who tab straight to the box then hear what they are agreeing to. Alternatively `role="group"` plus `aria-labelledby` on a wrapper holding the text and the controls.
- **Autofill [1.3.5 Identify Input Purpose, AA]**: the name field is a user's own name, so set `autocomplete="name"`. This helps users with cognitive or motor disabilities. Whether it is *wise* for a signature field to be browser-autofilled is a product choice. Autofill is fine here, since the learner is still typing or choosing the value. The spec says nothing about prefilling it from the account, and the repo should not prefill it either (see section 6).
- **No cognitive test [3.3.8 Accessible Authentication (Minimum), AA]**: typing one's own name is not a cognitive function test of the kind this criterion bars. Pasting must not be blocked. Do not set `onpaste` blockers, and do not add "type the name exactly as shown" challenges.
- **Redundant entry [3.3.7, A]**: does not apply here. Re-entry is exempt when essential, and a signature typed each attempt is the essential case. See https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html. Say so in the spec so a reviewer does not flag the repeat on "Try Again".
- **Error announcement [3.3.1, 4.1.3 Status Messages, AA]**: on a full-page 422 re-render the screen reader reads the page from the top. Set focus to the error callout or the first invalid field on load (`autofocus` is unreliable, so use `tabindex="-1"` and `focus()` in Alpine). If the form is ever swapped by HTMX, the error region needs `role="alert"` (or `aria-live="assertive"`) so the swap is announced. A plain page post does not need this.
- **Focus order and visible focus [2.4.3, 2.4.7, 2.4.11 Focus Not Obscured (Minimum), AA new in 2.2]**: the order is declaration, tick, name, button. The repo's `.btn` shows the ring on `focus-visible` only. A sticky header or footer must not hide the focused field on a small screen. Check that `c-player-footer` does not cover the name field when the keyboard opens.
- **Target size [2.5.8 Target Size (Minimum), AA new in 2.2]**: a checkbox must be at least 24 by 24 CSS px, or have enough spacing. The whole label row should be the click target. The repo's `flex items-start gap-2` label already makes the label text clickable. A larger checkbox (`size-5` or `size-6`) is better on touch.
- **Colour [1.4.1, 1.4.3]**: errors are never colour alone. They have text, and `text-error` (Signal) is 5.0:1 on white per `visual.md`.
- **Disabled buttons**: see section 2. WCAG 2.2 does not ban them, but they hide the reason and cannot be focused. The repo's own rule requires a visible reason plus `aria-describedby`.
- **Language and reading level [3.1.5 AAA, advisory]**: keep the declaration copy plain. Authors write the text, so the default text is the only one the spec controls.

WCAG 2.2 references (from general knowledge, with the criteria index at): https://www.w3.org/TR/WCAG22/ and https://www.w3.org/WAI/WCAG22/quickref/

## 6. Mobile (375px baseline per `visual.md`)

- One column, `max-w-xl`, as the intro page. The declaration box wraps and breaks long tokens (`break-words`, as in `course_form.html`). A long declaration should not scroll inside a nested region. Let the page scroll, since a nested scroller traps touch users and is hard for screen readers. If one is unavoidable, follow the repo's pattern (`max-h-96 overflow-y-auto` with `tabindex="0"`, `role="region"`, `aria-label`).
- The name input is full width, at least 16px font (iOS zooms inputs below 16px). The repo's base layer sets form input sizes, so use the unclassed input. Use `autocomplete="name"` and `autocapitalize="words"`, and leave `spellcheck="false"`.
- The button label fits on one line at 375px (`visual.md`). "Sign and start" does.
- Keep the primary button reachable after the keyboard opens. Avoid a fixed bottom bar that the virtual keyboard overlaps, or check that it does not hide the fields (see 2.4.11 above).
- Do not use `position: sticky` on the declaration text. Do not use a modal, which is the mobile reason against one.

## 7. "Try Again" and resume

- **Try Again**: `form_start` creates a new `FormProgress` and the learner lands on a fresh declaration page. The tick box is unticked and the name empty. The previous attempt's name is *not* prefilled. A prefilled name makes signing a reflex, which weakens the attestation, and it implies the system compares it with the earlier one. Autofill by the browser is the user's own choice.
- **Say what is different**: the page can show a short line when the learner has earlier attempts ("This is a new attempt, so you sign the declaration again."). It is optional and helps explain why the learner sees the page again. A learner who has just passed once, or failed once, will otherwise wonder if something broke.
- **Resume ("Continue Form") of an unsigned open attempt**: this arises when the learner started, closed the tab on the declaration page, and returned. The guard redirects the fill-page route to the declaration page. The page is identical to the first visit, with the same copy and no "welcome back" text. Do not mark the attempt as started in the sense of the timer until signed (spec question: whether any time limit or start time begins at creation or at signing; flag for the spec).
- **Resume of a signed open attempt**: no declaration page. The learner goes to the fill page directly. This is today's behaviour.
- **Direct link to a fill page with no signature**: redirect to the declaration page. Use a 302 with no error message. A message here is noise, since the page explains itself.
- **Signed attempt, learner revisits the declaration URL**: redirect to the first page (or the page they were on). Never show the form again for an attempt that has a record, since a second POST must fail. The model is write-once, so the view should not even attempt a second create.
- **Double submit**: disable the submit button on click via Alpine or `hx-disabled-elt`, and make the view idempotent. The one-to-one with `FormProgress` gives a unique constraint, so the second POST hits an existing record and should redirect, not raise. This also covers the idea's `START_REUSE_WINDOW` case.

## 8. Confirmation of what was signed

Options:

1. **None.** The learner proceeds to the first page. Simplest. The risk is that the learner never sees evidence that the declaration was recorded.
2. **A one-line read-only note** on the fill pages or the attempt result, such as "Declaration signed by Sam Dlamini on 3 Nov 2026, 07:37." Use `<c-datetime>` for the time (voice.md: never write a date format in a template). Do not show the IP address to the learner. It is stored for the auditor and adds nothing for the learner.
3. **A confirmation page** between signing and the first page. Extra click, delays the quiz. Reject.
4. **An email receipt.** Out of scope and not requested ("Don't build functionality that is not explicitly requested").

Recommendation: option 1 for the spec's core scope, with option 2 as the lowest-cost addition if the spec wants the learner to see proof. The idea only requires the admin read-only view. A learner-facing confirmation is therefore a decision for the spec, not a requirement. If added, it needs a place: the exam results page (`exam_previous_attempts.html`) is a candidate, since each attempt's row could carry "Declaration signed" as a chip.

## 9. Existing repo UI to reuse

- `freedom_ls/accounts/templates/cotton/consent-checkboxes.html` is the signup clickwrap. It renders `<label class="flex items-start gap-2">{{ form.accept_terms }}<span>I accept the <a …>Terms and Conditions</a></span></label>`, with a per-field `<p class="text-error text-sm">{{ form.accept_terms.errors.0 }}</p>` below. It is wrapped in `space-y-2` and fed by `add_consent_fields`. Reuse its structure for the tick box. It carries no `aria-describedby`, no `aria-invalid` and no `required` marker today. The new page should do better, and the two should stay visually the same. Do not refactor the signup component without being asked. The quiz declaration is a different record (`LegalConsent` is the analogue for storage, not for UI).
- `freedom_ls/learner_interface/templates/learner_interface/course_form.html` is the page the declaration sits behind. Layout: `<c-page flush="true">`, `max-w-xl text-center space-y-6`, badge, eyebrow, `<h1>`, left-aligned `c-markdown-container`, `c-player-footer` with `c-button size="small"`. Start and Try Again are `c-button href=…` links to `form_start`, so a GET starts an attempt. The declaration step is a new view and template in `learner_interface`, and the start view redirects there when the form requires a declaration. The page copies the same centred column.
- `claude_plugins/fls-dev/resources/templates_and_cotton.md` only covers path convention, theme shadowing and "a component owns its own styling". A new cotton component (for example `cotton/declaration-fields.html`) must carry its own Tailwind in its own template, not in `tailwind.components.css`. It lives at `freedom_ls/<app>/templates/cotton/<name>.html`, and themes shadow it at the same path. A page-level template does not need a component. The generic `ds` template resource (`Skill(ds:template)`) covers cotton, HTMX and Alpine, and `CLAUDE.md` says to return HTTP 422 for HTMX validation errors. I did not read it for this note.
- Brand skill (`.claude/skills/brand-guidelines/SKILL.md`, `voice.md`, `visual.md`): rules that bite here are headings and form inputs take no classes, one `c-callout tone="error"` for non-field errors, a back link at the top left on a page opened from another page, button labels on one line at 375px, `focus-visible` rings, and the disabled-action rule. Dates go through `<c-datetime>`.

## 10. Points for the spec to decide

1. Page and view shape: a new URL such as `form_declaration` under `learner_interface`, GET to show and POST to sign. The guard lives in one helper that the start, fill-page and continue routes call.
2. Checkbox label wording: generic "I agree" versus a declaration-authored "I make this declaration."
3. Name helper text. Avoid wording that implies a match against the account name or an ID.
4. Whether the learner sees a confirmation of the signed record, and where.
5. Whether a timed quiz starts its clock at attempt creation or at signing.
6. Whether the "this is a new attempt" line shows on repeat attempts.
7. The `autocomplete="name"` choice, and an explicit "no prefill" rule.

Nothing here needs a library. It is a Django `Form` with two fields, one cotton-free template and the existing `c-button`, `c-back-link` and `c-callout` components.

status: ok
