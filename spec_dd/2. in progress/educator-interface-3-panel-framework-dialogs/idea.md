# Panel framework dialogs: the modal and the quick view

Spec 3 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Two dialogs the framework hosts for every consumer.

A **modal**: one shared native `<dialog>` in the interface layout, opened with `showModal()`, whose content loads over htmx on demand. It carries every action form (create, edit, confirm-delete) and can also show read-only content, such as a topic's markdown at reading width so an educator can check what a learner sees.

A **quick view**: a right-hand drawer that slides in without a backdrop on large screens and leaves the page underneath fully interactive. An educator clicks a learner in a table, reads the summary, clicks the next learner, and the drawer repopulates. Below `md` it becomes a modal sheet. Its content is fetched over htmx from an endpoint the consumer provides. It is the place learner-facing communications will live later. It is not a `Panel`; it is hosted by the framework and fed by a fragment endpoint.

## Why

The current modal, `cotton/modal.html`, is an Alpine `div` with `role="dialog"`. It does not move focus in, trap it, inert the page or return focus on close. `FormPanelAction` and `DeleteAction` render their form, and for a delete the full cascade summary, on every render of the owning panel whether or not anyone opens the modal. A validation error swaps the whole component and drops the focused field. `showModal()` does all of that natively, and loading on open removes the eager work.

The quick view does not exist. The source idea requires it of the framework, and the learner table, the cohort detail and the dashboard's attention list all want it.

## What is settled

### Where it lives

- Spec 1 already left empty `modal_host` and `quick_view_host` blocks in `_base_interface.html`, outside `#interface-main` and the sidebar dialog. The two dialogs go there, so navigation swaps of `#main-content` never touch them.
- The Alpine components go in `panel_framework/static/panel_framework/js/alpine-components.js`. Spec 2 adds components to the same file; whichever lands second rebases.
- The quick view copies `sidePanel`'s pattern rather than sharing code with it. `sidePanel` breaks at `lg`, persists state in `localStorage`, and closes on any `htmx:beforeRequest`, which would fight the quick view's own fetches. `research_current_code.md` has the detail.

### Modal

- One `<dialog id="app-modal">`, run by a small Alpine component. It replaces `cotton/modal.html`, `modal_form.html` and `delete_confirmation.html`. Actions stop rendering their forms eagerly.
- Triggers are a cotton component that `hx-get`s the fragment into the modal body with no URL push. The component calls `showModal()` after the swap, so an empty modal never flashes and native `autofocus` in the fragment works. The browser picks initial focus once, at `showModal()`.
- The fragment carries its own heading. Initial focus follows the APG: first field for a form, the cancel button for a destructive confirmation, the heading for long read-only content.
- A form posts to itself and swaps itself. A 422 re-renders the form with errors and the component moves focus to the error summary or the first invalid field. Success returns 204 with an `HX-Trigger` naming the close event and the domain events (below). "Save and add another" re-renders a blank form in the modal and fires the same domain events. Navigation after success uses `HX-Location` targeting `#main-content`, replacing today's `HX-Redirect`, so it stays an htmx navigation with history. Nothing in the codebase uses `HX-Location` yet.
- Closing a form with changes asks first. Esc and the close and cancel buttons all go through `requestClose()` and one `cancel` listener on the dialog. A clean form closes straight away. A dirty one shows a "Discard changes?" prompt inline in the modal, above the form, which stays intact underneath. This is not a nested modal. Backdrop click closes read-only content and never closes a form. `closedby` would do the backdrop part natively but Safari has not shipped it, so it is hand-written for now.
- Page scroll locks through CSS while a modal is open. iOS Safari may leak scroll through `overflow: hidden`; QA checks it. The body is cleared on close. No nested modals; a confirmation inside a flow replaces the body.
- Heavy flows such as CSV import and bulk review are pages, never modals. Spec 8 follows that.
- Behaviour lives in `Alpine.data` components driven by htmx events, with listeners registered in `init()`. No `hx-on`, no trigger filters, nothing that needs eval under the CSP.

### Domain events

- The framework provides the mechanism, not the names. An action declares which events it fires on success, with ids in the detail. Tables, panels and the quick view declare which events they refresh on. The framework is installed into other projects, so it cannot hard-code learner or cohort events.
- The educator interface names four, camelCase with no dots or colons to match `panelChanged`: `learnerChanged`, `cohortChanged`, `registrationChanged` and `educatorChanged`. Id fields are always arrays, so a cohort move fires one `cohortChanged` for both cohorts, and a mutation touching two entity types fires both events in one `HX-Trigger`. Specs 6 to 9 use these and do not add their own. `research_domain_events.md` maps every mutation in 6 to 9 to its events and listeners.
- Tables and panels refetch on the event name alone. The quick view reads the ids and goes stale only when its own entity is named.
- `panelChanged` and the per-action `get_created_event_name()` give way to declared events. The page title update that `panelChanged` carries today keeps working.

### Quick view

- One `<dialog id="quick-view">`, run by its own Alpine component. `show()` on desktop, `showModal()` below `md`. A dialog cannot switch between modal and non-modal while open, so on a breakpoint change it closes and reopens.
- Triggers are one cotton component. It `hx-get`s the fragment into the drawer body with `hx-sync` replace on the body, so a new click aborts the request in flight, and no URL push. The component opens the drawer and shows a skeleton and whatever the trigger already knows from its `data-*` attributes, such as name, cohort and status, before the response arrives, and marks the body busy until it lands.
- Clicking the trigger for the content already showing closes the drawer. Closing hides the drawer without clearing it, so reopening the same trigger shows it without a request. A domain event naming the shown entity marks the content stale and refetches if the drawer is open. No HTTP caching.
- Desktop: no backdrop, no scroll lock, no focus trap, and click-outside does not dismiss, because clicking the next row is the whole point. Focus stays on the trigger after open. `show()` moves focus, so the component puts it back. Esc closes and returns focus to the trigger. The trigger exposes `aria-expanded` and `aria-controls`, and a polite live region announces what loaded.
- Mobile: `showModal()` gives inert background, focus containment and Esc. One history entry is pushed on open so Back closes it, as `sidePanel` does.
- htmx history restore must not bring back an open dialog. Both dialogs close before the history snapshot, or `hx-preserve` keeps them out of it; QA confirms whichever is chosen.
- Errors render inline in the body with a retry button. The drawer never auto-closes on error.
- The drawer header has a title, an "open" link to the entity's full page, and a close button. That link is the shareable URL; the drawer state is never in the URL. Actions inside the drawer open the shared modal.
- The endpoint returns a fragment. A plain GET to it redirects to the entity's full page. Responses carry `Vary: HX-Request`. It authorises through the framework's existing `authorise_instance` hook, so an out-of-scope learner or cohort is a 404, and it does not add its own permission check.
- Hidden in print. Logical CSS properties so RTL flips. Respects reduced motion. The slide-out on close may be instant in Firefox, which cannot transition `display` yet.
- Width about 480px on desktop, internal scroll, sticky header.

### First consumers

- A learner quick view: name, email, organisation status, cohorts, course registrations, individual and through a cohort, with progress percentage, last active. Reachable from every table cell that shows a learner, by making `cotton/data-table-cells/link.html` able to act as the trigger.
- A cohort quick view: name, status, learner count, courses, a link to the cohort.
- Both link to the learner and cohort detail pages spec 1 landed. `research_quick_view_data.md` gives the source of every field.
- Two fields have no data until later specs. A learner's "pending" status is defined by spec 7, and a cohort's active or inactive status needs `Cohort.is_active` from spec 6. This spec shows a placeholder for each, visibly marked in the template and in a code comment as a stand-in for spec 6 or 7 to replace. Until then the learner shows active or removed from `Learner.is_active`.

Both views are deliberately thin. Spec 10 adds the progress detail; comms come later.

## Out of scope

- Deep-linking an open quick view (`?peek=`). The design leaves room for it.
- Pinning two quick views side by side, drag-to-resize.
- A message composer. The drawer only has to be able to host one.

## Resources

- `research_current_code.md`: the modal, actions, `sidePanel`, layout and cell templates as spec 1 left them.
- `research_dialog_platform.md`: `closedby`, `requestClose()`, invoker commands, focusing steps, animation, scroll lock and htmx history, with support status as of 2026. Includes the Safari and VoiceOver issues to test by hand.
- `research_domain_events.md`: mutation-to-event map for specs 6 to 9, payload shapes, htmx and Alpine naming constraints.
- `research_quick_view_data.md`: where each quick-view field comes from and what the query costs.
- `research_ux_patterns.md`: the survey of Linear, Notion, Stripe and others. Where it disagrees with this idea, this idea wins.
- `research_ux_pitfalls.md`: the accessibility and keyboard model, mobile flip pitfalls, table-cell trigger specifics.
- `../educator-interface-full-polish/htmx-modal-drawer-url-state.md`, sections 1 and 2 and the pitfalls list: the htmx 2.0.8, Alpine CSP and Django 6 mechanics.
- Mockups: `Educator Learners.dc.html` screens 03 and 04, `Educator Mobile Learners.dc.html` screen M06, `Educator Cohorts and Admin.dc.html` screen 07, a modal.
- Skills: `ds:alpine-js`, `fls-dev:alpine-js`, `ds:htmx`, `fls-dev:template`, `fls-dev:playwright-tests`. `fls-dev:alpine-js` calls the sidebar component `sidebarComponent`; the registered name is `sidePanel`.
