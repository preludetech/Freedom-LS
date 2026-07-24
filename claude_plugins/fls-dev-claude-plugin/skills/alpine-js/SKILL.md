---
name: alpine-js
description: FreedomLS-specific extension of the ds:alpine-js skill. Adds the inventory of Alpine components already registered in the FreedomLS codebase plus the icon-usage cross-reference. Use alongside ds:alpine-js when adding client-side interactivity in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Alpine.js (FreedomLS overlay)

Read `Skill(ds:alpine-js)` first for the generic Alpine conventions (its CSP-build restrictions apply only when configured). This overlay adds **only** the FreedomLS component inventory and the icon cross-reference.

## Existing components

These Alpine components are already registered in the FreedomLS codebase — reuse them before writing a new one:

| Component name | File | Used in | Behaviour |
|---------------|------|---------|-----------|
| `dropdownMenu` | `base/.../alpine-components.js` | `cotton/dropdown-menu.html` | Toggle open/close, click-away, smart positioning |
| `modal` | `base/.../alpine-components.js` | `cotton/modal.html` | Toggle open/close, escape key, backdrop click |
| `message` | `base/.../alpine-components.js` | `partials/messages.html` | Auto-dismiss toasts |
| `sidebarComponent` | `base/.../alpine-components.js` | `_base_interface.html` | Toggle open/close, localStorage, responsive |
| `scrollTableLabels` | `base/.../alpine-components.js` | Tables | Scroll-synced table labels |
| `debugBadge` | `base/.../alpine-components.js` | `_base.html` | Collapsible debug badge |
| `coursePart` | `student_interface/.../alpine-components.js` | `course_minimal_toc.html` | Expand/collapse with localStorage |
| `equation` | `content_engine/.../alpine-components.js` | `cotton/equation.html` | Client-side KaTeX typesetting (widget-scoped) |
| `contentLightbox` | `content_engine/.../alpine-components.js` | `cotton/picture.html` | Focus-managing image lightbox (open/close, escape, focus restore) |
| `tabContainer` | `panel_framework/.../alpine-components.js` | Panel tabs | Tab switching |

## Icons with Alpine

Since `<c-icon>` is server-rendered, toggle icons with `x-show` on wrapper `<span>` elements rather than swapping the icon client-side. See `Skill(fls-dev:icon-usage)`.
