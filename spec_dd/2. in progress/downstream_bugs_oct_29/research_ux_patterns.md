# Research: UX patterns for the learner-facing and account-facing changes

Voice basis (`.claude/skills/brand-guidelines/voice.md`): direct, brief, name the problem and the fix, no blame, routine actions end on a full stop, learners not students, sentence case. Domain glossary: "registration" is the word for course access; the page copy the bundle already uses is "enrolment" ("Enrol for free", "You're enrolled"), so user-facing copy keeps "enrol" and never says "grant". Deadlines say "Deadline" and "Missed deadline", never "Due". Notifications skill: never notify a user of their own action, so every confirmation below is inline or a Django `messages` flash, never a `Notification`.

Sources used (patterns, not copied text):
- GOV.UK Design System: [Error summary](https://design-system.service.gov.uk/components/error-summary/), [Error message](https://design-system.service.gov.uk/components/error-message/), [Skip link](https://design-system.service.gov.uk/components/skip-link/), [Button](https://design-system.service.gov.uk/components/button/), [Pagination](https://design-system.service.gov.uk/components/pagination/), [Confirmation pages](https://design-system.service.gov.uk/patterns/confirmation-pages/), [Create accounts](https://design-system.service.gov.uk/patterns/create-accounts/), [Check answers](https://design-system.service.gov.uk/patterns/check-answers/), [Phone numbers](https://design-system.service.gov.uk/patterns/telephone-numbers/) (use `type="tel"`, `autocomplete="tel"`, be lenient on format).
- NN/g: [Error-message guidelines](https://www.nngroup.com/articles/error-message-guidelines/), [Confirmation dialogs](https://www.nngroup.com/articles/confirmation-dialog/), [Progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/), [Visibility of system status](https://www.nngroup.com/articles/visibility-system-status/), [Breadcrumbs / wayfinding](https://www.nngroup.com/articles/breadcrumbs/).
- WCAG: [Bypass Blocks 2.4.1](https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks.html), [Page Titled 2.4.2](https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html), [Autocomplete 1.3.5](https://www.w3.org/WAI/WCAG22/Understanding/identify-input-purpose.html), [Error Identification 3.3.1](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html).
- allauth defaults: [Templates](https://docs.allauth.org/en/latest/common/templates.html), [Email/verification flows](https://docs.allauth.org/en/latest/account/email_confirmation.html), [Configuration](https://docs.allauth.org/en/latest/account/configuration.html). Stock wording: "Sign Out", "Change Email", "Bad Token", "Confirm Email Address".
- LMS conventions: [Open edX learner docs](https://docs.openedx.org/en/latest/learners/index.html), [Moodle quiz attempts](https://docs.moodle.org/404/en/Quiz_activity), [Canvas quizzes](https://community.canvaslms.com/t5/Student-Guide/tkb-p/student), [Coursera learner help](https://learner.coursera.help/hc/en-us). Pattern points: Canvas and Moodle say "Resume quiz"/"Continue your attempt" on an unfinished attempt and "Take the quiz again"/"Re-attempt quiz" after; Moodle autosaves the current page on exit; Coursera replaces enrol/price copy with "Go to course" once enrolled and shows a plain "Enrolled" state.

Where a URL is a docs landing page rather than a specific article, treat the claim as the widely documented convention and verify in the spec if it becomes load-bearing.

## 1. Account pages

Decision on verbs (follow the codebase and brand skill): **"Log in", "Log out", "Sign up"**. `account/login.html` already says "Log in" and the voice sample uses sentence case; "Login" (noun) and "Sign Out" (`partials/login_prompt.html`, `partials/logout_button.html`) are the odd ones. Use "Log in" as the verb everywhere, "Sign up" for creating an account, "Log out" for ending the session. The voice file's error sample says "Try signing in"; treat as stale and say "Try logging in".

Headings: sentence case; `<title>` is "{page} — {site name}", built once in `_base.html` (see 4.f); each page's `head_title` names only the page.

- **Logout confirmation**: one page, one primary button. Heading "Log out". Body "Log out of {site name}?" Button "Log out" (the only primary). Secondary text link "Cancel" (to `/` or the previous page), not a button. Drop the manage nav (Change email/Change password/second Sign Out) from this page. Pattern: GOV.UK one-primary-button; NN/g confirmation dialogs (confirm only when meaningful; logout needs a POST in allauth, so the page stays).
- **Email management, one verified address**: heading "Email address". Show the address with a "Verified" tag and "Primary" tag. Actions: none on the lone primary verified address. Show "Make primary" only when more than one verified address exists; "Remove" only on non-primary addresses; "Resend confirmation" only on unverified ones. Add-email form below, headed "Add another email address", one primary button "Add email". Secondary actions are styled as secondary (link or outline), never all primary. This follows GOV.UK's "show only the actions that can do something".
- **Email-confirm page** (address appears once): heading "Confirm your email address". Body "Confirm that **{email}** is your email address." Button "Confirm". Drop the "is an email address for user {user}" clause when `user_display` equals the email; show the user clause only when it differs.
- **Already confirmed re-click**: heading "Email address already confirmed". Body "{email} is already confirmed. You don't need to do anything else." Onward link: "Go to your dashboard" when logged in, "Log in" when not (carry `next`). Not an error style (no red); it is an informational result (NN/g: don't call a harmless repeat an error).
- **Verification-sent page**: heading "Check your email". Body "We sent a confirmation link to **{email}**. Open it to finish signing up. It can take a few minutes. Check your spam folder if it doesn't arrive." Action: button "Send the link again" (POST, secondary), with the result flashed as "We sent a new link to {email}." Replace "contact us" with a real link to the site's contact/support URL when the site has one, else drop the sentence. British spelling ("finalise" avoided; use "finish").
- **Bad/expired reset link**: heading "This reset link no longer works". Body "Reset links expire after use or after a few days. Ask for a new one." Primary link-button "Request a new reset link" (to reset page). Never "Bad Token" (names the problem in the system's terms, not the learner's; NN/g error guidelines).
- **"Set your password" vs "Change password"**: choose by `user.has_usable_password()`. No usable password (staff-created learner, claim flow): heading "Set your password", button "Set password", no "current password" field. Usable password: heading "Change your password", button "Change password". Reset-from-key page: heading "Choose a new password" for everyone, button "Save password". "Cancel" is a text link, never primary. The account-setup email says "Forgot your password?" page to match the login link exactly (`account_setup_message.txt`).
- **Password-set page after a claim** (one task): heading "Set your password". One line above the form: "Your email is confirmed. Choose a password to finish setting up your account." Single primary button "Set password and continue" (continues to `next`, the application status page). Hide the manage nav (Change email, Change password, Log out) on this page; use a bare layout. Add a small footnote only if needed: "You can use 'Forgot your password?' to set one later." GOV.UK create-accounts pattern: one task per page.
- **Signup errors**: GOV.UK error summary at top of the form with `role="alert"` (or focus moved to it on load via `autofocus`/`tabindex="-1"` + script), title "There is a problem", each entry a link to the field; non-field errors (honeypot) appear in the summary as plain text. Inline field error goes **between the label and the input** (GOV.UK) with the field's `aria-describedby` pointing at it, prefixed visually hidden "Error:". Add `autocomplete="given-name"` / `"family-name"` (WCAG 1.3.5). Page `<title>` gets "Error: " prefix on failed submit (GOV.UK convention).
- **"Email added by another account" email** (for `ACCOUNT_PREVENT_ENUMERATION`): subject "[{site}] Confirm an email address added to an account". Body: "Someone added this email address to a {site name} account and asked us to confirm it. If that was you, confirm it here: {link}. If it wasn't you, ignore this email. Nothing changes unless the link is opened." Do not reveal whether the address already has an account (enumeration). Pattern: GitHub/Google "was this you?" emails; keep the enumeration-safe text identical for new and existing addresses where the template can't tell.
- **Claim page for an existing-account holder**: branch on `claim_sets_a_password` plus account existence. New address: "You'll then choose a password for your new account." Existing account (unverified or no usable password): "You already have an account with this email address. You'll set a new password for it, and your old password will stop working." Heading unchanged. Reasoning: say what will happen and its side effect (revoking the old password) before the click (NN/g: tell users consequences in advance).
- **`next` lost across devices (ACCT-6)**: lowest-effort accepted pattern is a message on the post-confirm page: "Your email is confirmed. Log in to carry on." plus the stored destination link if available. Storing `next` server side against the address is a spec decision, not a UX one; flag it as optional.
- **Coming-soon, anonymous, then "Create an account"**: one line above the signup form when `next` is a coming-soon interest URL: "Create an account to register your interest in {course title}."

## 2. Header

- **Auth links return to the current page**: "Log in" and "Sign up" carry `?next={current path and query}`, except on the home page and `/accounts/` pages (bare). Pattern: allauth `redirect_field_name`, Open edX `?next=`. After login/signup the learner lands where they were.
- **Site name as non-heading**: render as a `<span>`/`<p>` inside the link; the link's accessible name is the logo alt text or the site name. Exactly one `<h1>` per page (WCAG 1.3.1, GOV.UK).
- **Skip link**: first focusable element in `<body>`, visually hidden until focus, text "Skip to main content" (GOV.UK's wording, widely recognised), `href="#main-content"`, `<main id="main-content" tabindex="-1">`. Placed before the header. Per [GOV.UK Skip link](https://design-system.service.gov.uk/components/skip-link/) and WCAG 2.4.1.

## 3. Course detail

- **"Continue"**: button goes to `course_home` (which redirects to the resume pointer). "Start course" and "Review course" keep item 1. The back link's forward path follows the same URL. Matches Coursera/edX "Resume" behaviour (the button always lands where you left off).
- **Registered learner on a gated or priced course**: hero stat "Enrolment: Enrolled" (or "You're enrolled"); side panel heading "You're enrolled", no subtext, primary button "Start course" / "Continue" / "Review course". Do **not** show "Free · open to everyone". Price: keep the real price line in the hero stat (it is a fact about the course, and "Price on request" is what the course is); drop it from the side panel because the learner no longer has to act on it. `is_accessible_for_free` stays the course's real value so the free badge and JSON-LD stay correct.
- **Finished a free course**: side panel heading "You've finished this course." (full stop, routine) no acquisition subtext, button "Review course". Never "One click. No credit card." after the funnel.
- **"Coming soon" enrolment icon**: neutral icon (clock or calendar, or a dash), not a tick; decided by the access decision (a `stat_icon` field), tick only when open.
- **Coming-soon register interest copy**: before: "Register your interest so we know to run it." After registering: "You've registered your interest. Thanks." Matches the `express_interest_cta.html` comment: no promise of notification until one exists (notifications skill: "coming-soon course launched" is a valid notification only once built).
- **Hero icon on phone/tablet**: hide below `md` (`hidden md:block`) and use `right-4`/`lg:right-90` above. The icon is decorative (`aria-hidden`), so hiding costs nothing; a small offset on tablet keeps the design.

## 4. Dashboard

- **Applications panel after registration**: **hide** the row once the learner is registered. The course already sits in "In progress"; a duplicate "Accepted" row adds a second source of truth and a stale "Continue application" button. Show a row again only for applications on courses the learner is not registered for. (Alternative, if the spec wants history: show "Accepted" with a link to the course and no editable button. Recommend hide, the simpler of the two.)
- **Section descriptions**: render as inline Markdown only (bold, italic, links, code; no block elements), sanitised. One helper, same pipeline as other inline Markdown. A `content_validate` warning for block-level Markdown is optional.
- **Course time limit label**: "Course time limit" (matches the deadlines spec). Dashboard card: "Course time limit · 19 Oct 2026", with the chip "Missed deadline" when missed. Player outline: show a line at the top of the outline, "Course time limit: 19 Oct 2026" (or "Missed deadline" prefix), near the course title, since it applies to the whole course, not an item.
- **Home page `<title>` for anonymous visitors**: "{site name}" alone (`head_title` blank for them). Signed-in learners: "Dashboard — {site name}". The meta description fallback comes from a `SiteConfig` field, not a literal string. A neutral built-in default may stay as the last resort.
- **`<title>` branding**: `_base.html` appends " — {site name}" once; `head_title` names the page only; skip the suffix when the page title already equals the site name. WCAG 2.4.2: titles say where you are.

## 5. Form runner

- **One word by strategy**: `QUIZ` strategy says "quiz"; every other strategy says "form". Never "test", never "Form" capitalised mid-sentence. Sentence case throughout.
  - Start page buttons: "Start quiz" / "Continue quiz" / "Try again" (after completion; Canvas "Take the quiz again", Moodle "Re-attempt quiz" both name the object, but "Try again" is the existing label and is clearer after a failed attempt). Non-quiz: "Start form" / "Continue form" / "Start again".
  - Runner exit: X with accessible name "Exit quiz". Dialog title "Leave the quiz?". Result page retry: "Try again" (replaces "Retry quiz").
  - Finish page: "Start quiz" / "Start form" per strategy.
  - Implementation hint: one helper returning the noun from the strategy; templates never hard-code it.
- **"Leave and save" really saves**: the button posts the runner form to a save-only endpoint (`require_answers=False`, `formnovalidate`), then redirects to the start page. Dialog copy stays "Your progress is saved. You can pick up where you left off." Confirmation on the next page via `messages.success`: "Answers saved." Moodle autosaves the current page on exit; same here.
  - If the spec decides not to save partial pages: change the dialog to "Answers on this page won't be saved. Earlier pages are." (honest copy beats a false promise; NN/g).
- **Result page for a never-attempted quiz**: redirect to the item's start page, no message needed (the start page is the answer).
- **`correct: null`**: if the question has at least one option with `correct: true`, treat `None` as wrong on every unmarked option. Only if no option is marked correct, show "Not marked" with the grey question mark (it means the question has no verdict, which is a true statement).
- **Locked-item redirect message**: `messages.info`: "Finish the earlier lessons first. That item isn't open yet." Better than the idea's draft because "that one" has no referent after a redirect; name the item when cheap: "Finish the earlier lessons to open '{title}'." Item is the glossary-ambiguous word; the learner-facing copy says "lessons"/the title, not "item".
- **Outline chevron convention**: right chevron when closed, down chevron when open (GOV.UK Details, Material expansion panels, Canvas modules). Use one icon rotated by state (CSS rotate) to match the accordions.
- **Finish page dates**: `j M Y` ("28 Oct 2026") to match the quiz attempts.
- **Zero-page form on the start page** (belt and braces after `content_validate` rejects it): hide "Start quiz"; show "This quiz has no questions yet. Let your educator know." in place of the button, and never list it under "Still to do" as blocking if it cannot be sat. Primary fix remains rejecting it at content time.

## 6. Content

- **Code blocks**: `pre { overflow-x: auto; max-width: 100%; }`, and keep `tabindex="0"` on the scroll container so keyboard users can scroll it (WCAG 2.1.1, 1.4.10 reflow allows two-dimensional scroll for code). Pattern: GitHub, MDN.
- **Mermaid**: smallest honest option is a `content_validate` warning: "Mermaid blocks aren't rendered. The diagram will show as plain code." Rendering client-side adds a JS dependency, so defer unless the spec wants it. Whichever is chosen, unrendered Mermaid shows as an ordinary scrollable code block, never overflowing the page.

## 7. Errors

- **404 for anonymous visitors**: "This page doesn't exist." plus button "Go to the home page" (link `/`). Signed-in: "Go to your dashboard". Optional second link "Browse courses" matches the voice-skill sample. GOV.UK 404 pattern: say it's not found, suggest the next step.
- **Honeypot error message that can be acted on**: once the widget never re-renders a value the existing text works: "We couldn't process this sign-up. If you used autofill or a password manager, type your details in by hand and try again." Shorten "please" per the direct-over-diplomatic principle, keep one sentence of fix. Do not mention "honeypot" or a field name (don't help bots).

## 8. Pagination that survives Back

Use `hx-push-url`? No: the idea chose `hx-replace-url` so the `?page=N` lands in the URL without a history entry. UX effect: Back from a row returns to the full-page render with the same page (the server reads `clamped_page`); Back does not step through each page of the pager. GOV.UK pagination keeps the page in the URL. Optional: `aria-current="page"` on the current page link and an `aria-live` region announcing "Page 4 of 5".

## 9. Profile form

- **Required first name**: inline "Enter your first name" is the GOV.UK form of the message; Django's default "This field is required." is acceptable and matches signup. Recommend one message for both forms: "Enter your first name." (GOV.UK: tell people what to do). Spaces-only fails the same way.
- **Success**: POST-redirect-GET to the profile page with `messages.success`: "Profile saved." (existing wording; routine, full stop). Message region has `role="status"`.

## 10. Application phone field

- Keep `type="tel"` and `autocomplete="tel"`; do not add a rigid `pattern` (GOV.UK: allow spaces, brackets, plus signs). Server check: strip spaces, hyphens, brackets and a leading `+`; require at least 7 digits and only digits remaining. Message: "Enter a phone number with at least 7 digits, like 012 345 6789." Say what is wrong and show an example (NN/g). Real validation later with libphonenumber.

## Open points for the spec (not UX-decidable here)

- Server-side `next` storage for cross-device confirmation (ACCT-6).
- Render Mermaid versus warn.
- Whether applications panel hides or shows "Accepted" (recommend hide).
- Whether "Leave and save" saves the page (recommend yes) or the dialog copy changes.

status: ok
