---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/base/templates/cotton/button.html
  - freedom_ls/content_engine/templates/cotton/accordion.html
  - freedom_ls/content_engine/templates/cotton/flashcard.html
  - freedom_ls/content_engine/templates/cotton/picture.html
  - freedom_ls/learner_interface/templates/cotton/course-card-shell.html
  - freedom_ls/learner_interface/templates/cotton/course-row-shell.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: component styling moves into the component

A component's styling now lives in that component's own template rather than in a shared
stylesheet. `tailwind.components.css` keeps only three things: the `@layer base` element
rules, the component classes a theme is expected to reopen, and the `.task-list*` classes
the markdown renderer emits at render time.

Nothing about the rendered look changed. What changed is where the CSS lives, which files
exist, and how you override a component.

## Breaking changes

**Two stylesheets were deleted.** `tailwind.base_interface.css` and
`tailwind.picture_spotlight.css` are gone; their rules moved into
`_base_interface.html` and `cotton/picture.html`. A downstream project owns its own
`tailwind.input.css`, so **your build will fail until you delete both `@import` lines from
it.** See "Manual steps".

**Seven theme tokens no longer exist.** A `theme.css` that sets any of them is now setting
a variable nothing reads — silently, with no build error:

| Removed token | Where the value lives now |
|---|---|
| `--fls-flashcard-back-gradient` | `cotton/flashcard.html`, as `--flashcard-*` custom properties in its own `<style>` block |
| `--fls-flashcard-back-fg` | same |
| `--fls-flashcard-back-accent` | same |
| `--fls-flashcard-back-border` | same |
| `--fls-card-radius` | `.course-card` in `tailwind.components.css` (`rounded-2xl`) |
| `--fls-card-hero-height` | `h-28` on `cotton/course-card-shell.html` |
| `--fls-card-padding` | `p-4` on both course-card shells |

To restyle the flashcard's answer face, shadow `cotton/flashcard.html` and retune the four
custom properties at the top of its `<style>` block. Every descendant rule follows them.
`--fls-course-accent-*` is unchanged and is still the way to rebrand course cards.

**Five class families were removed from the compiled bundle.** They are no longer generated
anywhere, so any downstream markup or test that reaches for one now matches nothing:

`.flashcard-*` (except `.flashcard-back`, which the component's own `<style>` still uses),
`.accordion`, `.accordion-summary`, `.accordion-title`, `.accordion-body`,
`.accordion-body-inner`, `.accordion-chevron`, `.picture-figure-ref`,
`.picture-figure-title`, `.course-card-hero`, `.course-card-body`,
`.htmx-hide-on-request`, `.htmx-show-on-request`.

`.spotlight-dialog` and `.side-panel-*` also left the bundle, but the side-panel classes are
still applied by the shell template and styled from its own `<style>` block, so a selector
against `.side-panel-body` still resolves.

The htmx loading-state pair is the one with a real trap: a template of yours that carries
`class="htmx-hide-on-request"` will simply stop hiding, with no error. `c-button`'s
`loading` prop is unaffected — it now uses a `[.htmx-request_&]` descendant variant instead.

**A theme can no longer restyle these components from `theme.css`.** A component's `<style>`
block sits later in document order than the compiled bundle, so within `@layer components`
it wins. Restyle them by shadowing the template at
`themes/<slug>/templates/cotton/<name>.html`, which now carries the markup and the look in
one file. The Tier-2 surface is exactly the class list in
`docs/how tos/theme-fls.md`; nothing outside it is re-openable.

## Manual steps

1. **Delete the two dead imports from your own `tailwind.input.css`**, then rebuild:

   ```diff
   - @import "./tailwind.base_interface.css";
   - @import "./tailwind.picture_spotlight.css";
   ```

   ```
   npm run tailwind_build
   ```

   Without the rebuild the old rules stay in your compiled bundle and duplicate the ones the
   templates now emit.

2. **Grep your project for the removed class names** listed above, and for the seven removed
   tokens in every `theme.css` you ship. Neither produces a build error.

3. **If a theme of yours re-opened `.flashcard-*`, `.accordion-*`, `.picture-figure-*`,
   `.spotlight-dialog` or `.side-panel-*` in its `theme.css`**, move that work into a Tier-3
   template shadow. The rules will not take effect where they are.

No `migrate`, no `npm install`, no settings change and no package upgrade.
