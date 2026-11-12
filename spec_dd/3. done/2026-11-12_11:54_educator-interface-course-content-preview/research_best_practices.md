# Best practices: educator course-content preview in a modal

Scope: course details page (details plus table of contents) in the educator interface; each TOC item has a Preview button that opens a modal showing the item as a learner sees it (topic markdown, activities, forms/quizzes).

Source key: [W] = web-sourced (URL given). [P] = project code or skill (path given). Web search quality was mixed: mostly secondary practitioner pages plus MDN. Claims I could not verify against a primary source are flagged.

## 1. Side-effect-free preview

Findings
- Preview must not write progress, quiz/form attempts, completion times, or analytics events. [W] Brightspace documents this as the expected behaviour: an instructor's quiz preview attempt is not seen in the Gradebook even if grading is selected. https://teachanywhere.uvic.ca/learning-tech/brightspace/how-can-i-preview-a-quiz-and-attempt-it-as-a-learner/
- Canvas "Student View" creates a test student and real test submissions, and works only on published items. That is the opposite design (it writes records under a fake user), and it is the source of "ghost" data complaints. https://community.canvaslms.com/t5/Canvas-Ideas/Student-View-Test-assignment-submissions-for-unpublished/idi-p/600932 . Moodle-specific preview behaviour was not found in search (unverified here).
- [P] The learner views write on GET. `freedom_ls/learner_interface/views.py` `view_topic` does `TopicProgress.objects.get_or_create(...)` and then `topic_progress.save()` on every view (around lines 1718-1726). It handles `POST mark_complete`. `form_start` (around line 1829) calls `get_or_create_incomplete`. Reusing these views for the preview would create progress rows and attempts. The `can_record_progress = course_progress is not None` pattern (around line 1698) shows templates already hide completion controls when there is no `CourseProgress`.

Recommendations
- Build a dedicated read-only preview view that renders the same content partials the learner sees, rather than calling the learner views. Pass `course_progress=None`-style context so the templates hide Mark complete, Start, Submit and Next-as-completion controls.
- Only allow GET (`require_GET` or `@require_safe`). Preview templates contain no `<form>` that posts to learner endpoints. No `hx-post`.
- Forms/quizzes: render the questions with inputs disabled, `readonly`, or inert. Do not render a Submit button. Add a visible "Preview – not recorded" banner so the educator knows nothing is saved.
- Correct answers: educators are authors/staff, so showing correct options is the useful default for review. Mark them clearly (an "Answer key" marker per question, not color alone), and make that visibly different from learner view so nobody mistakes it for what a learner sees. Make the show-or-hide decision explicit in the spec. A toggle "Show correct answers" is a common optional refinement; it is not required.
- Add a test that a preview request creates zero `TopicProgress`, `FormProgress`, attempt and answer rows, and sends no analytics event (assert row counts before and after, and use `django_assert_num_queries` or a write-guard for the no-write guarantee).
- Unpublished or draft content: decide whether previews cover it. Educators usually need to preview unpublished content (Canvas ties Student View to published items, which is a documented pain point).

## 2. Accessible modal / dialog

Findings
- Native `<dialog>` opened with `showModal()` gives: top layer, inert background, focus moved into the dialog, Escape to close (`closedby` default `closerequest`), implicit `role=dialog` and `aria-modal=true`. https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog
- MDN: initial focus goes to the first focusable element. For dynamically loaded content where the best target is unknown, the `<dialog>` can be the focus target. Use `autofocus` on the most useful element, or on the Close button if nothing else needs immediate interaction. Do not put `tabindex` on `<dialog>`. Always provide an explicit Close button (most robust for all users). MDN's page does not cover aria-labelledby, scroll lock or focus return (confirmed absent).
- Secondary sources agree: label the dialog with `aria-labelledby` pointing at its heading, return focus to the trigger on close, and listen to the `close` event for cleanup. Examples: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/ (authoritative APG pattern; only seen via search results, not fetched), https://frontendchecklist.io/rules/accessibility/modal-accessibility , https://allyjs.io/tutorials/accessible-dialog.html . Browsers differ on automatic focus restoration, so restore explicitly.
- [P] FLS already has the pieces. `appModal` (panel_framework `modal_host.html`) is a native `<dialog>` host with trigger tracking, open on swap, focus after 422/re-render, and close on `closeModal`. `quickView` is a drawer `<dialog>` with a skeleton while loading, retry on error, and `aria-expanded` sync. `makeConfirmDialog` gives a focus trap, Escape and focus return. Registry: `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`. Components `<c-modal-header>`, `<c-modal-footer>`, `<c-modal-trigger>` and the partial `panel_framework/partials/modal_host.html` are listed in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` (it also says all triggers outside a dialog footer are `size="small"`, and a person is linked via `<c-panel-person-link>`).

Recommendations
- Reuse the existing `appModal` host and `<c-modal-trigger>` rather than adding a new dialog mechanism. Check whether it supports a large size. If it does not, add a size variant (for example `lg`/`xl` or near-fullscreen), not a new host.
- Modal contents: heading with an id referenced by `aria-labelledby`; Close button in the header with a visible accessible name ("Close preview"); body is the only scroll container (`overflow-y: auto; max-height` of the dialog), so the header (title, Close, prev/next) stays visible. Prevent background scroll while open (`body:has(dialog[open]) { overflow: hidden }` or the host's existing handling).
- Long reading content: a large (near-fullscreen on phones) modal beats a narrow centred one. Drawers/sheets suit short supplementary detail (the project's `quickView` use) and compare/lookup tasks; a full content preview with markdown and quiz questions needs width and height. On a phone, go full-screen (100dvh, no margin) with a sticky top bar. Keep a 44px touch target for the Close and navigation buttons, which the project already requires for phone buttons.
- Respect `prefers-reduced-motion`; no animation is required.
- Keep Escape and the browser Back button working. The project's `sidePanel` and `quickView` already close on Back on small screens (see the `sidePanel` registry row), which argues for matching that on phones.
- Don't nest dialogs; the preview content must not open another modal (a stacked-modal Escape closes only the top one, but nesting hurts mobile focus).
- Accessibility check in Playwright (see `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md`): open via keyboard, focus lands in the dialog, Tab stays inside, Escape closes, focus returns to the same Preview button, the dialog has an accessible name.

## 3. Lazy loading with HTMX; deep links; prev/next

Findings and recommendations
- Fetch the item on click: the Preview button uses `hx-get` to a per-item preview URL, `hx-target` the modal body (or whatever the `appModal` swap target is), with the `appModal` open-on-swap behaviour. The page then ships only the TOC, not every item's rendered markdown. Rendering all items inline would be heavy for large courses.
- Loading and error states: `quickView` already shows a skeleton and a retry; mirror this (loading skeleton, then content; error block with retry). HTMX validation errors return 422 (project convention in `CLAUDE.md`); a preview has no validation, but a 404 for a missing or out-of-scope item should render a friendly error in the modal rather than leave it empty (HTMX does not swap 4xx/5xx by default; check how the project's `htmx:responseError` handling is configured, in `claude_plugins/django-stack/skills/htmx/SKILL.md`).
- Use the same URL for both the modal fragment and a full page (the usual HTMX pattern): when `request.htmx` is true, return the fragment; otherwise redirect to the details page with the item open, or render the page with the modal opened server-side. That makes preview URLs shareable between educators and survives refresh. A URL per previewed item (e.g. `…/courses/<course>/preview/<item>/`) is recommended: it gives deep links, testable endpoints, and a stable access-scoped route. Whether to also `hx-push-url` (so Back closes the modal and refresh restores it) is a design choice. Pure modal with no push is simpler and matches existing `appModal` behaviour; pushing adds history entries that must be unwound on close. For a minimum viable version: per-item URL for the fragment, no history push, and defer push-url/refresh restore.
- Next/previous inside the modal: render Previous/Next buttons in the modal header or footer from the course's flattened TOC order (the same order the learner sees, including the learner `course_index`/part structure). Each button is an `hx-get` to the neighbouring item's preview URL, targeting the same modal body, so the dialog stays open and focus moves to the modal heading (set focus programmatically after the swap, and announce the change with `aria-live="polite"` on the title, or move focus to the heading). Disable or omit Previous on the first item and Next on the last. Show "Item 3 of 27" for orientation. Compute neighbours server-side, not in JS.
- Keep the TOC rows' Preview buttons as real `<button>` elements with an accessible name that includes the item title (e.g. `aria-label="Preview: <title>"`), because many identical "Preview" labels are ambiguous to screen-reader users.
- Alpine vs HTMX: per the project rule, HTMX does the fetch and swap; Alpine only holds client UI state (`claude_plugins/django-stack/skills/htmx/SKILL.md`, "Separation of Concerns").

## 4. Security

Findings and recommendations
- [P] The preview endpoint is its own URL and must apply the same access scoping as the course details page. Hidden or hand-typed ids are the usual leak. Scope every lookup by site (the project's site-aware manager filters automatically), by whatever educator-to-course relationship the details page enforces, and by course: `get_object_or_404` on the course through the scoped queryset first, then look the item up inside that course's collection (an item id that is valid but belongs to another course or another educator's course must 404, not render). Use the shared scoping helper or mixin rather than re-implementing it. Return 404, not 403, for out-of-scope ids to avoid confirming existence.
- Check permission in the view even if the button is hidden in the template. Add tests: staff without access, wrong-site, wrong-course item, learner (non-staff) user, anonymous (redirect to login). Cover both the fragment and the full-page fallback.
- Preview is GET-only and idempotent, so CSRF is not at issue; still keep the global `hx-headers` CSRF setup.
- Do not expose answer keys through any endpoint a learner can reach. The preview URL must be staff-only; do not reuse a learner route with a `?preview=1` flag (a flag on a learner route is a classic privilege-escalation or answer-leak bug).
- Markdown: render with the same pipeline the learner pages use, so the preview matches what learners see. Content comes from authored course files (a trusted-ish source), but the principle stands: sanitise rendered HTML (allow-list tags/attributes, drop `javascript:` URLs, `on*` handlers, `<script>`/`<iframe>` unless explicitly supported), and use Django's auto-escaping everywhere except the one deliberate `|safe` of already-sanitised output. I found no sanitiser reference (`bleach`/`nh3`) in `freedom_ls/content_engine/*.py` by keyword search; the spec should confirm how the existing pipeline renders and whether it sanitises (for example the Cotton widget rendering described in `claude_plugins/fls-content`), and should reuse it rather than add a second renderer. Do not introduce an unsanitised second path just for preview.
- Content shown inside the modal must not break out of it: scope CSS so learner-page styles do not leak, and make embedded media (images, video, iframes) responsive within the modal width.

## 5. Suggested checklist for the spec

1. Dedicated read-only preview view and template (no learner view reuse); GET-only; no writes; test asserts zero rows created.
2. Per-item preview URL, staff/educator-scoped identically to the details page, item looked up inside the scoped course; 404 otherwise.
3. Reuse `appModal` host and `<c-modal-trigger>` (size small); add a large/mobile-fullscreen variant if absent; `aria-labelledby`, Close button, scrolling body, focus return.
4. Fragment vs full-page response for the same URL; loading skeleton and error/retry like `quickView`.
5. Prev/Next from server-computed TOC order, same modal, position indicator, focus to heading.
6. Forms/quizzes rendered disabled with an answer-key treatment (decision: show correct answers, labelled) and a "Preview – nothing is recorded" banner.
7. Same markdown/widget renderer as learners, with confirmed sanitising.
8. Playwright a11y flow and permission tests as in sections 2 and 4.

## References
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog (fetched)
- https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/ (from search results, not fetched)
- https://frontendchecklist.io/rules/accessibility/modal-accessibility , https://allyjs.io/tutorials/accessible-dialog.html , https://dev.to/chille87/accessible-modals-how-to-build-dialogs-that-dont-trap-confuse-or-exclude-users-3o3p (search results only)
- https://teachanywhere.uvic.ca/learning-tech/brightspace/how-can-i-preview-a-quiz-and-attempt-it-as-a-learner/ (search snippet)
- https://community.canvaslms.com/t5/Canvas-Ideas/Student-View-Test-assignment-submissions-for-unpublished/idi-p/600932 (search snippet)
- Project: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`, `claude_plugins/django-stack/skills/htmx/SKILL.md`, `freedom_ls/learner_interface/views.py` (`view_topic`, `form_start`)

status: ok
