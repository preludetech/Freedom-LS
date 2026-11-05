---
name: alpine-js
description: Inventory of the Alpine components already registered in FreedomLS, plus the icon cross-reference. Use alongside ds:alpine-js when adding client-side interactivity in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Alpine.js (FreedomLS overlay)

Read `Skill(ds:alpine-js)` first and follow it to the build resource it routes to; that file owns how components are written. This overlay adds **only** the component inventory and the icon cross-reference.

## Existing components

Reuse these registered components before writing a new one. Each app registers its own in `freedom_ls/<app>/static/<app>/js/alpine-components.js`; the File column names the app. Template paths are relative to that app's `templates/` directory.

### Components (`Alpine.data`)

| Component name | File | Used in | Behaviour |
|---------------|------|---------|-----------|
| `headerScroll` | `base` | `partials/header_bar.html` | Sets `scrolled` once the window scrolls, which the template binds to `data-scrolled` for the theme's sticky-header treatment |
| `stretchedLinkProxy` | `base` | `cotton/organisation-byline.html` (`learner_interface`) | Passes a click on the organisation name to the card's stretched title link |
| `dropdownMenu` | `base` | `cotton/dropdown-menu.html` | Toggle open/close, click-away, smart positioning |
| `toast` | `base` | `partials/_toast.html`, included by `partials/messages.html` | Auto-dismiss by severity (errors persist), pauses on hover, focus and window blur, caps visible toasts at five |
| `sidePanel` | `base` | `_base_interface.html` (sidebar); `panel_framework/partials/table_toolbar.html` (phone filter and sort sheet, `data-mobile-only`) | One `<dialog>`: docked with `show()` at `lg`+ with state in localStorage, modal with `showModal()` below, Back closes it, `aria-expanded` sync and focus return |
| `debugBadge` | `base` | `_base.html` | Collapsible debug badge |
| `localTime` | `base` | `local_time` template tag (`<time>`) in `base`'s `time_tags` library; `deadline_tags` re-registers it | Rewrites the server-rendered instant into the viewer's own time zone, with the zone label when `data-show-zone="true"` |
| `notificationBell` | `comms` | `comms/partials/notification_bell.html` | Header disclosure panel (built on `headerPanel`): loads on open, loading and error blocks, badge poll, closes when the messages panel opens |
| `messagesPanel` | `comms` | `comms/partials/messages_button.html` | Header disclosure panel (built on `headerPanel`): newest conversations load on open, refresh on `conversationChanged` while open |
| `refreshTimer` | `comms` | `comms/partials/messages_button.html`, `comms/partials/conversation_list.html`, `comms/partials/thread.html`, `panel_framework/partials/sidebar_nav.html` (menu counts) | Re-sends the element's own `hx-get` every `data-poll-seconds` while the tab is visible |
| `messageComposer` | `comms` | `comms/partials/composer.html` | Draft flag so a poll never swaps out unsent text, characters-left count, Ctrl/Cmd+Enter submit, retry on a network failure |
| `threadPane` | `comms` | `comms/thread.html` | Sets `--thread-top` to the site header's height on `#thread-pane`, so whatever htmx swaps into it fills the viewport below the header |
| `conversationThread` | `comms` | `comms/partials/thread.html` | Keeps the composer in view, opens the log at its newest message, follows new entries only when the reader is at the bottom, otherwise counts them on a "New messages" button |
| `questionFileUpload` | `form_engine` | `form_engine/inputs/file_upload.html` | Refuses an oversized file in the browser on `htmx:confirm`, before it uploads |
| `coursePart` | `learner_interface` | `learner_interface/partials/course_minimal_toc.html` | Expand/collapse with localStorage |
| `coursePlayer` | `learner_interface` | `learner_interface/course_topic.html`, `course_form.html`, `course_item_closed.html` | Scrolls the outline's current row into view on load |
| `examRunner` | `learner_interface` | `learner_interface/course_form_page.html` | Exam runner root: `beforeunload` warning once an answer is edited, focuses the page heading on load |
| `examExitDialog` | `learner_interface` | `learner_interface/course_form_page.html` | Exit confirmation (built on `makeConfirmDialog`): focus trap, Escape, focus return to the trigger |
| `examRunnerForm` | `learner_interface` | `learner_interface/course_form_page.html` | Live answered count and the final-page submit confirmation (built on `makeConfirmDialog`) |
| `dateEyebrow` | `learner_interface` | `learner_interface/dashboard.html` | Today's date in the browser's locale and zone, refreshed when the tab is shown again |
| `courseSectionPagination` | `learner_interface` | `learner_interface/partials/course_list.html`, `course_applications/partials/dashboard_applications.html` | Returns focus to the matching pager control after a swap, or to the section heading |
| `historyBackLink` | `learner_interface` | `learner_interface/course_detail.html` | Back link steps back through history, falling back to its `href` when there is no sending page or it would bounce |
| `memberRoleChooser` | `educator_interface` | `educator_interface/modal/add_staff_member.html` | Shows the cohorts block only for a role given on cohorts and tells `cohortChecklist` which role is chosen |
| `cohortChecklist` | `educator_interface` | `educator_interface/modal/add_staff_member.html`, `educator_interface/modal/change_cohorts.html` | Filters cohort rows by search text and by the chosen role; rows not offered are hidden and disabled |
| `appModal` | `panel_framework` | `panel_framework/partials/modal_host.html` | Native `<dialog>` host: trigger tracking, open on swap, focus after 422/re-render, close on `closeModal` |
| `quickView` | `panel_framework` | `panel_framework/partials/quick_view_host.html` | Drawer `<dialog>` host: `show()`/`showModal()` by breakpoint, skeleton while loading, retry on error, `aria-expanded` sync |
| `tableSelection` | `panel_framework` | `cotton/data-table.html` | Row and header checkbox state for the bulk-action bar, "Select all N matching", the table's background run from the `bulkRuns` store |
| `listRefresh` | `panel_framework` | `panel_framework/partials/list_refresh.html` | Re-fetches a list's table region, keeping page, sort, search and filters, when a create action's `HX-Trigger` event fires |
| `headerRefresh` | `panel_framework` | `panel_framework/views/_instance_header.html` | Re-fetches `#instance-header` so an instance page's stats and tab counts follow a panel's change |
| `refocusAfterRequest` | `panel_framework` | `educator_interface/panels/cohort_report_downloads.html` | After a form's htmx request, focuses the element `data-refocus-id` names, so a submit button disabled for the request (and possibly re-rendered) gets keyboard focus back |
| `equation` | `content_engine` | `cotton/equation.html` | Client-side KaTeX typesetting (widget-scoped) |
| `flashcard` | `content_engine` | `cotton/flashcard.html` | Flip state and 3-D face styles for the two-sided card; the animation honours reduced motion |
| `contentLightbox` | `content_engine` | `cotton/picture.html` | Focus-managing image lightbox (open/close, escape, focus restore) |
| `claimLinkNotice` | `course_applications` | `course_applications/partials/claim_link_notice.html` | Reveals the change-address form in place, reopening it with the field focused after a failed change |

### Stores (`Alpine.store`)

| Store name | File | Used in | Behaviour |
|-----------|------|---------|-----------|
| `bulkRuns` | `panel_framework` | `tableSelection` (read in JS, not from a template) | Background bulk runs keyed by table region id: polls each run's status URL until the result modal arrives; leaving the table drops the run and the requester gets a notification |

## Icons with Alpine

`<c-icon>` is server-rendered, so toggle icons with `x-show` on wrapper `<span>` elements, never by swapping the icon client-side. See `Skill(fls-dev:icon-usage)`.
