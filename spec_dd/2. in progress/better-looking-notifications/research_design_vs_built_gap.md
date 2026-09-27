# Research: design vs built gap for notifications core

Compares the Claude Design notifications design (`design_snapshot_notifications.md`,
verbatim excerpts of `uc/uc-shell.jsx`, `uc/uc-notify.jsx`, `uc/uc-data.jsx`, `uc/uc.css`) against
what `user-communication-1-notifications-core` actually built, read from the templates below and
the spec's own screenshots. "How to treat it" (`spec_dd/1. next/user-communication/design.md`)
says: take structure/density/hierarchy/states/copy, never raw colours/fonts/spacing, FLS role
tokens / cotton components / `c-icon` win. Gaps below are judged against that rule, not against
the design's literal CSS.

Built templates read:
- `freedom_ls/comms/templates/comms/partials/notification_bell.html`
- `freedom_ls/comms/templates/comms/partials/notification_badge.html`
- `freedom_ls/comms/templates/comms/partials/notification_panel.html`
- `freedom_ls/comms/templates/comms/partials/notification_row.html`
- `freedom_ls/comms/templates/comms/notification_list.html`
- `freedom_ls/base/templates/partials/header_bar.html`
- `freedom_ls/base/templates/cotton/button.html`

Screenshots read: `page-1-many.png`, `page-3-1-panel-open.png`, `page-3-8-panel-failed.png`,
`page-4-centre-p1.png`, `page-4-8-all-read.png`, `page-4-9-unread-empty.png`, `page-4-10-empty.png`,
`page-7-1-mobile-header.png`, `page-7-1-mobile-panel.png`, `page-7-2-mobile-centre.png`,
`page-8-1-bell-focus.png`, `page-9-tablet-centre.png` (all under the done spec's `screenshots/`).

FLS icons are **Heroicons** by default (`freedom_ls/icons/mappings.py`, `HEROICONS_MAPPING`), not
Phosphor — the design's `ph-*` names (bell, gear-six, checks, arrow-right, chat-circle-text,
user-plus, seal-check, file-text, calendar-blank, circle, check, check-circle, x) don't carry over
1:1; FLS's `<c-icon>` takes semantic names instead (`fls-dev:icon-usage`). Equivalents found below;
none are missing outright, but several design icons (double-check "checks", filled dot "circle",
category glyphs for message/registration/deadline/application) have no semantic name of their own
and the spec already chose different FLS icons for the two shipped categories (`course` for
registration, `achievement` for completion) rather than the design's `user-plus`/`seal-check` — a
spec decision, not a bug.

## 1. Header / bell / badge

| Design element | What was built | Gap |
| --- | --- | --- |
| Bell sits immediately left of the avatar, 44×44 hit target, `rounded-full`, hover tint `--surface-3` | `notification_bell.html`: `size-10` (40px) button, `rounded-full`, `hover:bg-header-action hover:text-on-header-action`, sits before `header_bar_user_menu.html` inside a flex row (`header_bar.html` line 20-24) | Matches structurally (bell left of avatar, hover tint). Slightly smaller hit target (40px vs 44px) — minor, not worth a token change. |
| Badge: pill, `min-width 20px`, caps "99+", offset with a 2px ring in the surface colour so it reads as "notched" against the header | `notification_badge.html`: `absolute -top-0.5 -right-0.5`, `bg-error text-on-error`, `min-w-[1.25rem]`, `{{ unseen_count|badge_count }}` (caps at 99+ per `comms_tags.badge_count`) | Count-capping and colour are right (role tokens `bg-error`/`text-on-error`). No separating ring/shadow between badge and header bar — the design's `box-shadow:0 0 0 2px var(--surface)` visual "notch". Fixable with an existing-token box-shadow (e.g. `shadow-[0_0_0_2px_var(--color-header)]`), not a new token. |
| Accessible name: "Notifications, N unread" / "Notifications, none unread"; live region | `notification_badge.html`: `<span id="notification-bell-label" class="sr-only">Notifications, {{ unseen_count }} new / none new</span>`, `role="status"` wrapper | Matches (spec chose "new" over the design's "unread" wording deliberately — Open question in the done spec: "so 'new' keeps meaning unseen"). Not a gap, a spec decision. |
| Keyboard focus ring on the bell | `screenshots/page-8-1-bell-focus.png`: visible focus ring, circular, around the bell | Matches. |
| Long site title truncates at 375px | `header_bar.html`: title `<h1>` is `hidden sm:block` when a logo image is configured, i.e. hidden rather than truncated on mobile; `truncate` class only applies when the `<h1>` is shown | `header_bar.html` is pre-existing, outside `comms`'s scope, and FLS's own header behaviour (hide vs the design's truncate) — flag for the user, not a `comms` fix. |
| 99+ badge state | `screenshots/page-1-many.png` shows a "6" badge in a QA scenario, not tested at 99+ visually, but `badge_count` filter caps at 99+ per the model tests | Behaviourally correct; no visual issue seen. |
| Panel disclosure semantics: design draws `aria-haspopup="dialog"`/`role="dialog"` | `notification_bell.html`: no `aria-haspopup`, panel div has no `role` | **Not a gap** — Decision 9 in the done spec deliberately rejects `role="dialog"` because the panel doesn't trap focus; this is the spec overriding the design on purpose. |

## 2. Panel (desktop popover and 375px sheet)

| Design element | What was built | Gap |
| --- | --- | --- |
| Heading "Notifications" + "N unread" in a muted, smaller weight beside it | `notification_panel.html`: `<h2>Notifications <span class="text-muted text-sm">{{ unread_count }} unread</span></h2>` | Matches structurally. |
| Row: 36px icon tile with rounded corners and a **category-tinted background** (`c-message` = primary tint, `c-completion` = success tint, `c-deadline`/`c-application` = warning tint), icon coloured to match | `notification_row.html`: bare `<c-icon :name="notification.icon" class="mt-0.5 size-5 shrink-0 text-muted sm:mt-0" />` — no background tile at all, every category renders identically muted-grey | **Real gap.** FLS has the pieces to build the tile without new tokens: `bg-success-light`/`text-on-success-light`, `bg-warning-light`/`text-on-warning-light`, `bg-error-light`/`text-on-error-light`, `bg-info-light`/`text-on-info-light` (all in `theme.css`), plus the established opacity-modifier pattern `bg-primary/10 text-primary` used today in `freedom_ls/base/templates/cotton/callout.html`. A tile could be `size-9 rounded-md grid place-items-center` with one of those pairs keyed to category, `<c-icon>` inside at `size-5`. No FLS token is missing; the row template just never built the tile. |
| Unread row = bold text + dot + "New"/"Unread" label + **tinted row background** (`.uc-ni.unread{background:var(--primary-tint)}`) | `notification_row.html`: unread gets `font-semibold` and a dot+label (`bg-primary` dot, "Unread" text) but the `<li>` background never changes (`bg-surface` always, only `hover:bg-surface-2` on hover) | **Real gap.** Row tinting for unread is entirely missing. `bg-primary/5` or `bg-info-light` on the `<li>` when `not notification.read_at` would express it with existing tokens/opacity modifiers, no new token needed. |
| Two-line message clamp, meta line "label · time" below | `notification_row.html`: message has no `line-clamp` (design uses `-webkit-line-clamp:2`); meta line format matches (`{{ notification.label }} · <time>`) | Minor: long messages in the panel could grow rows unevenly instead of clamping to 2 lines. Small CSS-only fix (`line-clamp-2` is a Tailwind utility, no token issue). |
| Footer: "Mark all as read" **with a double-check icon**, disabled when nothing unread; "See all" with a trailing arrow | `notification_panel.html`: `<c-button variant="ghost" size="small" disabled=... >Mark all as read</c-button>` (no `icon_left`) and `<c-button ... icon_right="next">See all</c-button>` | Partial gap: "See all" already carries its arrow (`icon_right="next"` → Heroicons `arrow-right`, matching the design's `arrow-right`). "Mark all as read" has no icon in the built version. FLS's icon-usage table has no semantic double-check ("checks") — closest existing name is `"check"` (single tick). Recommend `icon_left="check"` as the nearest available icon rather than proposing a new semantic name. |
| Close button (mobile only) with `aria-label="Close notifications"` | `notification_panel.html`: `sm:hidden` button, `aria-label="Close notifications"`, `<c-icon name="close">` | Matches. |
| Failed-load state: "Couldn't load your notifications." + "Try again" | `notification_bell.html` (`x-show="failed"`) + `screenshots/page-3-8-panel-failed.png`: message and retry link both present, plain text styling | Matches; not drawn as a design artboard for this state, spec added it — visually plain but that's consistent with "plain, not broken." |
| Row link target: whole row is clickable (`.uc-nrow-link::after{inset:0}` — the anchor's pseudo-element stretches over the row; the mark-read button sits `z-index:1` above it) | `notification_row.html`: only the message text itself is an `<a>`; the rest of the `<li>` (icon, meta, whitespace) is not clickable | **Real gap**, easy fix with existing patterns: add a stretched-link (`after:absolute after:inset-0`) on the message anchor, keep the mark-read `<c-button>` at a higher `z-index`/`relative` so it stays clickable — no new component needed, same idiom the design uses. |
| Panel width ~400px desktop, full-width sheet at 375px | `notification_bell.html`: `sm:w-96` (384px) desktop, `fixed inset-0` (full-viewport) below `sm` | Matches closely enough (384 vs 400px, immaterial). |

## 3. Notification centre (populated / all read / empty / long list / 375px)

| Design element | What was built | Gap |
| --- | --- | --- |
| Page header: `<h1>Notifications</h1>` + a "Preferences" ghost button with a gear icon, top-right | `notification_list.html`: `<h1>Notifications</h1>` only, no Preferences control | **Not a gap** — the done spec's Scope explicitly excludes "the Preferences links (gear in the panel header, button on the centre)" (spec 2's territory). List separately below as scope-excluded, not a defect. |
| Toolbar: segmented `All`/`Unread N` control (`role="radiogroup"`, pill background, active pill gets `bg-surface`+shadow), "Mark all as read" pushed right | `notification_list.html`: `<nav aria-label="Filter">` with two `<a>` links styled `rounded-full ... bg-surface-2 p-1`, active one gets `aria-[current=page]:bg-surface ... shadow-sm` via `aria-current` | Structurally very close (pill container, active pill lifted with a shadow) even though it's link/`aria-current` semantics rather than `radiogroup`/`aria-checked`. That's a legitimate accessibility-pattern choice (filter links + `aria-current` is a common, valid alternative to a radiogroup for navigation-style filters) — not a colour/token gap, so not flagged as broken, just noted as a deliberate pattern difference the user may want confirmed. |
| Unread pill shows a small count badge | `notification_list.html`: `<span class="... bg-primary px-1.5 py-0.5 text-xs font-semibold text-on-primary">{{ unread_count }}</span>` | Matches. |
| Category icon tile (colour-coded) on each row, as in the panel | `notification_row.html` shared with the centre (`show_actions=True`) — same bare muted icon, no tile | Same gap as panel row (see above); same fix (existing `-light` tints / `bg-primary/10` opacity modifiers). |
| Unread row = bold + dot + label + **tinted row background** | Same as panel: bold + dot + "Unread" text present; row background never tints | Same gap as panel row. |
| Day heading: `12px`, `font-weight:700`, `letter-spacing:.06em`, `text-transform:uppercase`, muted colour, on a hairline-bordered strip | `notification_list.html`: `<h2 class="bg-surface-2 px-5 py-2 text-sm font-semibold text-muted">{{ heading }}</h2>` — sentence case ("Today"), `text-sm` (14px), no letter-spacing/uppercase | **Real, cheap gap.** Change to `text-xs uppercase tracking-wide font-semibold text-muted` — pure Tailwind utilities, no new tokens, closer to the design's density/hierarchy intent without copying its literal 12px/0.06em values verbatim. |
| Per-row "Mark read" / "Mark unread" button, icon-only at 375px with an accessible name that includes the message | `notification_row.html`: `<c-button ... icon_left="check|close" aria-label="Mark read/unread: {{ notification.message }}">` with `<span class="hidden sm:inline">` for the label text | Matches design and spec requirement exactly, confirmed in `screenshots/page-7-2-mobile-centre.png` (icon-only buttons at 375px). |
| "All read" status banner: `role="status"`, success tint, filled check-circle icon, "You're up to date. Everything has been read." | `notification_list.html`: `id="notification-list-up-to-date" role="status" ... bg-success-light text-on-success-light`, `<c-icon name="complete" class="size-5">`, same copy | Copy and tint role match. Icon choice is slightly off: `"complete"` maps to a bare checkmark (`HEROICONS_MAPPING["complete"] = "check"`), while FLS already has `"success"` mapped to `check-circle` — the design draws a filled circle-check, and `"success"` is the closer existing semantic match. Small, no-new-icon fix: swap `name="complete"` → `name="success"`. |
| Empty state: bell icon, "Nothing yet.", "We'll tell you here when something happens on your courses." | `notification_list.html`: `<c-icon name="notifications" class="mx-auto size-10 text-muted">`, exact copy match | Matches (`screenshots/page-4-10-empty.png`). |
| Unread-filter-empty state: "No unread notifications." | `notification_list.html`: exact copy, confirmed in `screenshots/page-4-9-unread-empty.png` | Matches. |
| "Show older notifications" button on the long-list artboard | Not built; `c-pagination` used instead | **Not a gap** — done spec's Scope explicitly says "the centre paginates instead" of "Show older notifications." List separately below. |
| Card container: `border`, `rounded-xl`, `overflow:hidden`, white surface | `notification_list.html`: `mt-6 divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface` | Matches (uses FLS's `rounded-lg` token rather than copying the design's literal `12px`, exactly as intended). |
| Whole-row click target on centre rows (same stretched-link idiom as the panel) | Same as panel: only the title text is a link | Same gap as panel (see above), same fix. |
| 375px layout: header wraps, icon-only mark buttons, single-column | `screenshots/page-7-2-mobile-centre.png` confirms icon-only buttons and readable single-column layout | Matches; visually plain (no icon tiles, no tinting) for the same reasons as above, not additionally broken at mobile width. |
| Populated / long list at 1280 tablet | `screenshots/page-9-tablet-centre.png` shows layout holds at intermediate widths | No new gap found at tablet width beyond the ones already listed. |

## 4. In the done spec's scope vs deliberately left out by the design

**In scope (the spec asked for these; the gaps above are real, fixable-now items):**
- Bell, badge, panel structure and states (all header states, panel open, mobile sheet, failed load).
- Notification centre: All/Unread filter, day groups, mark read/unread, mark all as read, the four
  states (populated, all read, empty, unread-empty), pagination instead of "Show older."
- Category icon + label rendering, unread bold/dot/label, relative time, day headings.

These are exactly where the visual gaps sit: icon tiles, row tinting, day-heading typography, the
whole-row click target, the "Mark all as read" icon, and the all-read banner's icon choice. None of
them require the spec's *scope* to change — they're presentation-only fixes inside surfaces the
spec already built.

**Deliberately left out by the done spec (design draws them; do not silently re-add — the user
decides):**
- The gear/"Preferences" links (panel header icon button, centre page button) — spec 2's territory.
- "Show older notifications" button — the centre paginates instead, an intentional behaviour choice.
- The message item / row (`cat: "message"`, chat-circle-text icon) — spec 4 (direct messaging)'s
  territory; there is no message category to render yet.
- `aria-haspopup="dialog"` / `role="dialog"` on the panel — Decision 9 explicitly rejects this
  because the panel doesn't trap focus; a WAI-ARIA disclosure was chosen instead.
- The centre row's "about" column (third meta segment, e.g. "Conversation with Ada Lovelace") —
  named in `2. plan.md`'s Design section as deliberately left out.
- The design's segmented `radiogroup` control for All/Unread — the built filter uses links +
  `aria-current`, which is a defensible accessibility-pattern substitution rather than an omission,
  but flag it since it's a structural (not just cosmetic) departure the user may want to weigh in on.

## 5. Broken vs merely plain

Nothing found rises to a hard accessibility or functional break. Specifically checked and found
sound:
- Accessible names on the bell (`aria-labelledby` → live region span), on mark-read/unread buttons
  (`aria-label="Mark read/unread: <message>"`), and on the mobile close button.
- Keyboard focus: visible ring on the bell (`page-8-1-bell-focus.png`), autofocus handling on
  `mark_all`/`row_removed` focus targets in `notification_list.html`, panel heading `tabindex="-1"`
  with conditional `autofocus`.
- Mobile overflow: 375px screenshots show no clipped content, and mark-read/unread buttons
  correctly collapse to icon-only with retained accessible names.

One minor (not broken, worth a line in the fix list) double-announcement: `notification_row.html`
puts a visually-hidden "Unread. " before the message **and** a visible "Unread" label with an
`aria-hidden` dot right after — a screen reader hits "Unread." then, moments later in the same row,
"Unread" again as the trailing label text (the label span itself isn't `aria-hidden`, only its dot
is). Not a defect the design would have caught either way, but cheap to tidy while touching this
template (e.g. make the trailing "Unread" label `aria-hidden="true"` too, since the leading
visually-hidden text already carries the meaning for screen readers).

## 6. Visible in the screenshots, missing from the tables above

`screenshots/page-3-1-panel-open.png` and `page-4-centre-p1.png` show two things the tables
understate:

- **Every row title renders as a blue, underlined link**, in the panel and the centre, read or
  unread. The design's rows read as inbox items: `.uc-nrow-link` and `.uc-ni` set
  `text-decoration:none` and `color:var(--on-surface)`, with underline only on hover in the centre.
  The built anchors pick up FLS's default link styling. This is the single biggest reason the
  built UI looks "messy".
- **The All / Unread filter pills are underlined links too**, which the design draws as a plain
  segmented control.
- "Mark all as read" in the panel renders as primary-coloured plain text with no icon; on the
  centre it is an outlined button with no icon. The design draws a ghost button with the
  double-tick (`checks`) icon.

## References

- `design_snapshot_notifications.md` — verbatim design excerpts (JSX/CSS).
- `spec_dd/1. next/user-communication/design.md` — how to treat the design.
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/1. spec.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/2. plan.md`
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/screenshots/*.png`
- `freedom_ls/comms/templates/comms/partials/notification_bell.html`
- `freedom_ls/comms/templates/comms/partials/notification_badge.html`
- `freedom_ls/comms/templates/comms/partials/notification_panel.html`
- `freedom_ls/comms/templates/comms/partials/notification_row.html`
- `freedom_ls/comms/templates/comms/notification_list.html`
- `freedom_ls/base/templates/partials/header_bar.html`
- `freedom_ls/base/templates/cotton/button.html`
- `.claude/skills/brand-guidelines/SKILL.md`
- `claude_plugins/fls-dev/skills/icon-usage/SKILL.md`
- `freedom_ls/icons/mappings.py` (`HEROICONS_MAPPING`)
- `freedom_ls/themes/default/static/themes/default/theme.css`
- `freedom_ls/base/templates/cotton/callout.html` (precedent for `bg-<role>/10` opacity-modifier tints)

status: ok
