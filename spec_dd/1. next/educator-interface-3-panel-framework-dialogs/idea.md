# Panel framework dialogs: the modal and the quick view

Spec 3 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Two dialogs the framework hosts for every consumer.

A **modal**: one shared native `<dialog>` in the interface layout, opened with `showModal()`, whose content loads over htmx on demand. It carries every action form (create, edit, confirm-delete) and can also show read-only content, such as a topic's markdown at reading width so an educator can check what a learner sees.

A **quick view**: a right-hand drawer that slides in without a backdrop on large screens and leaves the page underneath fully interactive. An educator clicks a learner in a table, reads the summary, clicks the next learner, and the drawer repopulates. Below `md` it becomes a modal sheet. Its content is fetched over htmx from an endpoint the consumer provides. It is the place learner-facing communications will live later. It is not a `Panel`; it is hosted by the framework and fed by a fragment endpoint.

## Why

The current modal is an Alpine `div` with `role="dialog"`. It does not move focus in, trap it, inert the page or return focus on close, and every action's form is rendered eagerly into the page whether or not anyone opens it. A validation error swaps the whole component and drops the focused field. `showModal()` does all of that natively.

The quick view does not exist. The source idea requires it of the framework, and the learner table, the cohort detail and the dashboard's attention list all want it.

The mechanics were researched against htmx 2.0.8, the Alpine CSP build and Django 6, with the browser platform facts and the current code's failure points, in `../educator-interface-full-polish/htmx-modal-drawer-url-state.md` sections 1 and 2. The UX survey and the accessibility model are in the two research files beside this idea. Where the older survey disagrees with the decisions below, the decisions win; the survey carries a note saying so.

## What is settled

### Modal

- One `<dialog id="app-modal">` in the layout, outside anything navigation swaps, run by a small Alpine component. It replaces `cotton/modal.html` and the framework's `modal_form.html`.
- Triggers are a cotton component that `hx-get`s the fragment into the modal body with no URL push. The component calls `showModal()` after the swap, so an empty modal never flashes.
- The fragment carries its own heading. Initial focus follows the APG: first field for a form, the cancel button for a destructive confirmation, the heading for long read-only content.
- A form posts to itself and swaps itself. A 422 re-renders the form with errors and the component moves focus to the error summary or the first invalid field. Success returns 204 with an `HX-Trigger` naming both the close event and a domain event that tables, panels and the quick view refresh on. Navigation after success uses `HX-Location` targeting the main content, not a redirect, so it stays an htmx navigation with history.
- Backdrop click closes read-only content, not a form with typed input. Esc works natively. Page scroll locks through CSS while a modal is open. The body is cleared on close. No nested modals; a confirmation inside a flow replaces the body.
- Heavy flows (CSV import, bulk review) are pages, never modals. Spec 8 follows that.
- Behaviour lives in `Alpine.data` components driven by htmx events. No `hx-on`, no trigger filters, nothing that needs eval under the CSP.

### Quick view

- One `<dialog id="quick-view">` in the layout, sibling of the main content, run by an Alpine component modelled on the existing `sidePanel` (share its code if the extraction is clean). `show()` on desktop, `showModal()` below `md`. A dialog cannot change modality while open, so on a breakpoint change it closes and reopens.
- Triggers are one cotton component. It `hx-get`s the fragment into the drawer body with `hx-sync` replace on the body, so a new click aborts the request in flight, and no URL push. The component opens the drawer and shows a skeleton and whatever the trigger already knows (name, cohort, status from `data-*` attributes) before the response arrives, and marks the body busy until it lands.
- Clicking the trigger for the content already showing closes the drawer. Closing hides the drawer without clearing it, so reopening the same trigger shows it without a request. Domain events from mutations mark the content stale and refetch if the drawer is open. No HTTP caching.
- Desktop: no backdrop, no scroll lock, no focus trap, and click-outside does not dismiss, because clicking the next row is the whole point. Focus stays on the trigger after open (the component refocuses it, since `show()` moves focus). Esc closes and returns focus to the trigger. The trigger exposes `aria-expanded` and `aria-controls`, and a polite live region announces what loaded.
- Mobile: `showModal()` gives inert background, focus containment and Esc. One history entry is pushed on open so Back closes it, reusing `sidePanel`'s logic.
- Errors render inline in the body with a retry button. The drawer never auto-closes on error.
- The drawer header has a title, an "open" link to the entity's full page (that link is the shareable URL; the drawer state is never in the URL), and a close button. Actions inside the drawer open the shared modal.
- The endpoint returns a fragment. A plain GET to it redirects to the entity's full page. Responses carry `Vary: HX-Request`.
- Hidden in print. Logical CSS properties so RTL flips. Respects reduced motion.
- Width about 480px on desktop, internal scroll, sticky header.

### First consumers

- A learner quick view: name, email, organisation status (active, pending, removed), cohorts, course registrations with progress percentage, last active. Reachable from every table cell that shows a learner, through one shared cell template.
- A cohort quick view: name, status, learner count, courses, a link to the cohort.

Both are deliberately thin. Spec 10 adds the progress detail; comms come later.

## Open until the spec

- Whether the `sidePanel` extraction is worth doing now or the quick view copies the pattern. Decide by reading the component; do not let it grow the spec.
- Exactly which domain events the modal emits on success, named once and reused by specs 6 to 9.

## Out of scope

- Deep-linking an open quick view (`?peek=`). The design leaves room for it.
- Pinning two quick views side by side, drag-to-resize.
- A message composer. The drawer only has to be able to host one.

## Resources

- `research_ux_patterns.md`, the survey of Linear, Notion, Stripe and others, with a note on the points this idea overrides.
- `research_ux_pitfalls.md`, the accessibility and keyboard model, mobile flip pitfalls, table-cell trigger specifics.
- `../educator-interface-full-polish/htmx-modal-drawer-url-state.md`, sections 1 and 2 and the pitfalls list.
- Mockups: `Educator Learners.dc.html` screens 03 and 04, `Educator Mobile Learners.dc.html` screen M06, `Educator Cohorts and Admin.dc.html` screen 07 (a modal).
- Skills: `ds:alpine-js`, `fls-dev:alpine-js`, `ds:htmx`, `fls-dev:template`, `fls-dev:playwright-tests`.
