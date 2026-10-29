# Idea: smaller learner-facing problems found in a downstream QA run

## The bug

Source: this downstream project's mega QA run on 2026-10-28. Each section below is one problem
on the FLS side, with the QA reference, what the learner saw, the cause and a suggested fix. None
blocks a learner on its own, so they are grouped here rather than filed one by one. Content-side
halves of the same findings are this project's to fix and are left out.

## Code blocks overflow the page; no Mermaid support (LEARN-6)

`/courses/remote-pilot-certificate-rpc-multirotor/7/` has a ```` ```mermaid ```` fence. It renders
as a `<pre>` 838px wide that isn't scroll-contained: the document is 1326px wide at a 1280px
viewport and 854px at 390px, so the whole page scrolls sideways. Item 47 shows a raw `mindmap`
source.

Cause: no stylesheet in FLS gives `pre` an overflow rule (nothing in `tailwind.components.css`,
`tailwind.input.css` or either theme's `theme.css`), so it keeps `overflow-x: visible`. The
Markdown pipeline (`markdown_rendering/markdown_utils.py:18-26`) has `fenced_code` but no Mermaid
handling.

Fix: style rendered `pre` with `overflow-x: auto` and a max width. Separately, decide whether
FLS supports Mermaid (render `language-mermaid` blocks client-side) or `content_validate` warns
on them.

## Quiz result page for a quiz never attempted (LEARN-7)

`/courses/introduction-to-the-drone-industry/8/complete` for a quiz the learner never started
renders "Quiz complete — Knowledge check: rules and the commercial world has no pass mark, so
there is no pass or fail — here is how you scored." with no score. The quiz has an 80% pass mark.

Cause: `course_form_complete` (`learner_interface/views.py:1670`) renders whatever
`completed_attempts(...).first()` returns, including `None` (`:1690-1694`). With no attempt,
`quiz_verdict` stays `None` and the template takes its "no pass mark" branch
(`course_form_complete.html:41-47`).

Fix: when there is no completed attempt, redirect to the item's start page.

## "Form", "test" and "quiz" for the same thing (LEARN-10)

The start page says "Start Form" / "Continue Form" / "Try Again"
(`learner_interface/utils.py:755,765,772`). The runner's X is "Exit test" and its dialog "Leave the
test?" (`course_form_page.html:80,107`). The result page says "Retry quiz"
(`course_form_complete.html:243`), the finish page "Start quiz" / "Start form"
(`course_finish.html:64`). "Form" is internal vocabulary.

Fix: name the action after the form's strategy (quiz for `QUIZ`, something neutral otherwise) and
use that one word everywhere, in sentence case.

## A wrong answer whose option has `correct: null` shows "Not marked" (LEARN-11)

In "Review incorrect answers" the learner's wrong pick gets a grey question mark ("Not marked")
instead of a red cross, under a "Marked wrong" chip. The content left wrong options' `correct`
unset rather than `false`.

Cause: `course_form_complete.html:117-123` treats `correct is None` as "no verdict" on purpose.
That makes sense for a question with no marked options, not for one that has a correct option.

Fix: when the question has at least one option with `correct: true`, treat `None` as `False`,
either in the template's data or by normalising at `content_save`.

## A locked item URL bounces to the course page with no explanation (LEARN-12)

A learner at item 4 who opens a bookmarked `/courses/introduction-to-the-drone-industry/10/` lands
on the course detail page with no message.

Cause: `_blocked_item_redirect` (`learner_interface/views.py:1113`, redirect at `:1139-1142`)
redirects without adding a message.

Fix: add a `messages.info` such as "Finish the earlier lessons to open that one."

## The course time limit is labelled "Course" (LEARN-13)

Dashboard card: "Missed deadline | Course 19 Oct 2026". "Course" alone doesn't say it is the time
limit. The player's outline never mentions the course time limit at all.

Cause: `COURSE_DEADLINE_TITLE = "Course"` (`learner_interface/views.py:123`), used by
`_card_deadline_line` (`:142`). The deadlines spec's own testing section expects "Course time
limit".

Fix: use "Course time limit", and show it in the player outline.

## Outline chevrons point the wrong way (LEARN-14)

In the player outline an open part shows a right chevron and a closed one a down chevron. The
accordions on the same page do the opposite.

Cause: `partials/course_minimal_toc.html:88-93` shows the `collapse` icon when expanded and
`expand` otherwise. `icons/mappings.py:14-15` maps those to `chevron-down` and `chevron-right`.

Fix: show a down chevron when open and a right one when closed, or rotate one icon as the
accordion does.

## Finish page dates are US style (LEARN-17)

"Started: October 28, 2026 / Completed: October 28, 2026", while quiz attempts show "28 Oct
2026".

Cause: `course_finish.html:88,95` hard-code `date:"F j, Y"`.

Fix: use the same format as the rest of the learner interface (`j M Y`) or the locale's
`DATE_FORMAT`.

## Coming-soon copy promises a notification nothing sends (DISC-1)

Every coming-soon course reads "Register your interest and we'll let you know when the course is
ready.", before and after the learner registers interest. Nothing sends that message.

Cause: `_COMING_SOON_ACQUISITION_SUBTEXT` (`course_access/backends.py:368-370`). The comment above
it (`:364`) and `course_interest/templates/course_interest/partials/express_interest_cta.html:19` both say the copy must not
promise a notification.

Fix: "Register your interest so we know to run it." or similar, until a launch notification
exists.

## Section descriptions render as plain text (DISC-3)

A category description with `**IMPORTANT:**` shows the asterisks on the dashboard.

Cause: `learner_interface/partials/course_list.html:112` outputs `{{ section.description }}`.

Fix: render it as inline Markdown, or document that it is plain text and have `content_validate`
flag Markdown in it.

## Home page title is "Dashboard"; generic meta description (DISC-5)

The anonymous home page has `<title>Dashboard</title>` and `meta description="Learning management
system"`, as do `/articles/`, login, signup and the legal pages.

Cause: `learner_interface/dashboard.html:8` sets `head_title` to "Dashboard" for everyone.
`base/templates/_base.html:14,42` fall back to "Learning management system".

Fix: use the site name as the home page title for anonymous visitors. Give the description
fallback a site-level setting or `SiteConfig` field rather than a fixed string.

No downstream workaround: a context processor supplying `meta_description` works, but it fails
FLS's `base/tests/components/test_head_metadata.py::test_og_description_falls_back_to_the_generic_default`,
which runs in the downstream suite under the downstream's settings.

## `<title>` branding is inconsistent (DISC-6)

Player pages end with "— {{ site_name }}" (`learner_interface/_course_base.html:12`). Course detail
pages are just the course title (`course_detail.html:11-13`), and so are articles, legal docs,
login and signup.

Fix: append the site name in `_base.html`'s `<title>` once, so each page's `head_title` only
names the page.

## Course detail hero icon misplaced on phone and tablet (DISC-8)

At 390px the large translucent course icon sits off the left edge; at 768px it sits under the
title.

Cause: `course_detail.html:82`, `absolute bottom-0 right-90` with no responsive variant.

Fix: a small offset below `lg` (`right-4 lg:right-90`), or hide it below `md`.

## "Enrolment: Coming soon" has a tick (DISC-9)

The enrolment stat always uses `stat_icon="check"` (`course_detail.html:146`), so "Coming soon"
reads as available.

Fix: let the access decision choose the icon, or use a neutral one.

## 404 page offers "Go to your dashboard" to anonymous visitors (DISC-14)

Cause: `base/templates/404.html:6,13-15` shows the dashboard button whenever the URL reverses.

Fix: label it "Go to the home page" for anonymous visitors. (The missing footer is deliberate,
`_error_base.html:13-17`.)

## Phone questions accept any text (APP-1)

An application's phone question accepts "hello", shows it on check-your-answers and stores it.

Cause: `form_engine/typed_answers.py:175-177` does no phone check on purpose ("Real phone
validation needs libphonenumber and a country"). The `<input type="tel">` has no `pattern`.

Fix: at least reject input with fewer than 7 digits until full validation lands.

## Section pager loses its page on Back (APP-7)

Page "Your applications" to 4 to 5 of 5, open a row, press Back: the panel is on page 1 again.

Cause: `base/templates/cotton/section-pagination.html:21-24,43-46` swap with `hx-get` and no URL
update, by design ("Paging still never pushes a URL").

Fix: add `hx-replace-url` so the page query lands in the URL without a new history entry. The
full-page view already reads it (`clamped_page`).

## Notifications are raised when `NOTIFICATIONS_ENABLED` is off (LEARN notes)

With `NOTIFICATIONS_ENABLED` at its default `False`, a staff registration still writes a
"You've been registered for ..." notification. There is no bell, so nobody sees it, and they
pile up at `/notifications/`, which is still reachable.

Cause: `raise_notification` (`comms/notify.py:27`) checks only `NOTIFICATION_CATEGORIES`
(`:47-50`). `NOTIFICATIONS_ENABLED` is read only by the bell tag (`comms/templatetags/comms_tags.py:35`).
Callers include `learner_progress/signals.py:159` and `comms/messaging.py:329`.

Fix: return early from `raise_notification` when `NOTIFICATIONS_ENABLED` is false, and 404 the
notification views. A project can work around it today by setting `NOTIFICATION_CATEGORIES = []`.
