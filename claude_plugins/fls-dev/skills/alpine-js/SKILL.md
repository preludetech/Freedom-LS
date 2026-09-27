---
name: alpine-js
description: FreedomLS-specific extension of the ds:alpine-js skill. Adds the inventory of Alpine components already registered in the FreedomLS codebase plus the icon-usage cross-reference. Use alongside ds:alpine-js when adding client-side interactivity in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Alpine.js (FreedomLS overlay)

Read `Skill(ds:alpine-js)` first, and follow it through to the build resource file it routes you to — that file, not this one, owns how components are written. This overlay adds **only** the FreedomLS component inventory and the icon cross-reference.

## Existing components

These Alpine components are already registered in the FreedomLS codebase — reuse them before writing a new one:

| Component name | File | Used in | Behaviour |
|---------------|------|---------|-----------|
| `dropdownMenu` | `base/.../alpine-components.js` | `cotton/dropdown-menu.html` | Toggle open/close, click-away, smart positioning |
| `message` | `base/.../alpine-components.js` | `partials/messages.html` | Auto-dismiss toasts |
| `sidebarComponent` | `base/.../alpine-components.js` | `_base_interface.html` | Toggle open/close, localStorage, responsive |
| `appModal` | `panel_framework/.../alpine-components.js` | `panel_framework/partials/modal_host.html` | Native `<dialog>` host: trigger tracking, open on swap, focus after 422/re-render, close on `closeModal` |
| `quickView` | `panel_framework/.../alpine-components.js` | `panel_framework/partials/quick_view_host.html` | Drawer `<dialog>` host: `show()`/`showModal()` by breakpoint, skeleton while loading, retry on error, `aria-expanded` sync |
| `debugBadge` | `base/.../alpine-components.js` | `_base.html` | Collapsible debug badge |
| `coursePart` | `learner_interface/.../alpine-components.js` | `course_minimal_toc.html` | Expand/collapse with localStorage |
| `equation` | `content_engine/.../alpine-components.js` | `cotton/equation.html` | Client-side KaTeX typesetting (widget-scoped) |
| `contentLightbox` | `content_engine/.../alpine-components.js` | `cotton/picture.html` | Focus-managing image lightbox (open/close, escape, focus restore) |

## Icons with Alpine

Since `<c-icon>` is server-rendered, toggle icons with `x-show` on wrapper `<span>` elements rather than swapping the icon client-side. See `Skill(fls-dev:icon-usage)`.
