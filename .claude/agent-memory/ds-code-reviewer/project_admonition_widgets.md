---
name: project-admonition-widgets
description: Admonition/flashcard/accordion content widgets — registry, icon resolution, callout migration
metadata:
  type: project
---

Content widgets (more_course_widgets SDD) replacing `c-callout` with `c-admonition` plus flashcard/accordion.

**Admonition registry**: `ADMONITION_TYPES` dict in `config/settings_base.py` (~line 306). Each entry: `{"label", "icon", "color"}`, optional `"icon_fallback"`. Must include a `"default"` key. Deploys extend it by merging `**ADMONITION_TYPES` in their own settings (e.g. `settings_dev.py` adds `regulation`).

**Resolution**: `freedom_ls/content_engine/templatetags/content_tags.py` — `admonition_config` (lookup w/ default fallback) + `admonition_icon` (delegates to `render_icon`). Template `cotton/admonition.html` enumerates color→bg/text classes literally (info/success/warning/error) so Tailwind doesn't purge them.

**Icon resolution** (`freedom_ls/icons/render.py`, `render_icon`) is a 5-step order: empty→default_semantic; semantic name; literal glyph in active set (`FREEDOM_LS_ICON_SET`, default heroicons); `<iconset>:<glyph>` fallback; graceful default. Verify literal glyphs exist in `node_modules/@iconify-json/<set>/icons.json`. Outline variant has no suffix (see `HEROICONS_VARIANTS` in `mappings.py`).

**Callout→admonition mapping** (spec §7.2): no-level/`info`→`note`, `success`→`tip`, `warning`→`warning`, `error`→`danger`. Preserve `title`.

**Note**: `c-callout` cotton component (`freedom_ls/base/templates/cotton/callout.html`) still exists and is used in live Django templates (e.g. `course_form_page.html`) — only the *markdown content* sanitization allowlist drops it. Don't flag developer-facing `c-callout` template usage as needing migration; only `demo_content/` markdown was in scope for the migration.

**Named slots in markdown (`c-flashcard`)**: authors write `<c-slot name="front">...</c-slot>`. Security flow: outer markdown is nh3-sanitised (`c-slot` allowlist carries only `name`), then cotton-rendered; inside the widget template `{% markdown front %}` re-runs `render_markdown` on the slot body, so the body is sanitised a second time. Verified XSS coverage in `markdown_rendering/tests/test_markdown_utils.py` (TestCAccordion, flashcard slot tests, script-strip tests).

**Admonition colour→class tokens**: theme defines `--color-{info,success,warning,error}-light` and `--color-on-{...}-light` in BOTH `themes/default` and `themes/first_class` theme.css. `cotton/admonition.html` branches on `cfg.color` and passes literal `bg-*-light`/`text-on-*-light` strings via `{% with %}` (Tailwind-scannable, not purged). Default branch covers `info`+unknown.

**Flashcard Alpine (CSP)**: `Alpine.data("flashcard", ...)` in `content_engine/static/.../alpine-components.js` exposes `flipped`, `flip()`, `frontStyle()`, `backStyle()` (style objects, not class strings → bypass purge). Template uses only registered names + `x-bind:inert`/`x-bind:aria-hidden`/`x-bind:style`/`x-on:click` — no inline expressions.
