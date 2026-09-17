# Footer area

## Why

FLS has no footer anywhere in its web chrome. `_base.html` runs from `</main>` straight to the debug
badge, with no footer element or block in between. Every page funnels through that shell.

So a concrete implementation that needs a footer on its learner-facing pages has exactly one option
today: shadow `_base.html` whole. That is a ~140-line fork carrying the PostHog snippet, the CDN
script tags, the entire `head_seo` block and the debug badge, and it then has to track FLS forever.
The project this request came from already carries one such fork for its landing pages, and that
file's own comment admits the maintenance cost. A second fork, for a footer, is a bad trade.

## What we are building

A `{% block footer %}` in `_base.html`, placed after `</main>` and before the debug badge, wrapping a
one-line `{% include "partials/footer_bar.html" %}`. It mirrors the existing `{% block header %}` and
`partials/header_bar.html` pair exactly, with a generic block name and a specifically-named partial.
A downstream project fills it by overriding one small partial instead of the page shell.

The block sits outside `<main>` so `<footer>` is a sibling landmark rather than a generic region
nested in main content. That placement is the whole point. Nested inside `<main>`, the element maps
to `generic` and the `contentinfo` landmark is lost without any warning. `{% block extra_body %}`
sits inside `<main>`, which is why it is not the seam.

## What is settled

**The seam is template override only.** No settings, no models, no database-backed footer content. A
downstream project supplies markup and nothing else.

**The partial is `partials/footer_bar.html`,** mirroring `header_bar.html`, since both are horizontal
chrome bars. "Footer" is already six other things in FLS: `cotton/player-footer.html`, the cotton
`footer` slot on modal and media-card, the runner's own sticky action bar, `.email-footer`, and the
PDF report's `.footer-*` classes. Every one of them means "the bottom of one component" rather than
site chrome. `footer_bar` keeps the new file distinct from all six. Prose says "the site footer".

**FLS ships a real footer, not an empty seam.** It renders a copyright line and links to the site's
legal documents. The copyright line reuses what the outbound email footer already does, a
`{% now "Y" %}` year against the installation's display name, which every template already has as
`header_title` from the `site_config` context processor. The links go to `accounts:legal_doc` for
`terms` and `privacy`, the only two values in `ALLOWED_DOC_TYPES`.

**Those links render unconditionally.** FLS's own repository ships both `legal_docs/_default/terms.md`
and `privacy.md`, so both resolve for every site unless a project deletes both and supplies no
override. Gating them on `has_legal_doc` would be correct in that degenerate case and expensive in
every other one. The function is uncached and resolves the git blob at HEAD, so gating costs either a
`git show` subprocess or a full manifest re-read, twice, on every page render.

**Where it renders:**

- Plain `_base.html` pages get the full footer. That is the dashboard, course detail, all-courses,
  legal docs, auth pages and the application pages.
- `_base_interface.html` pages, meaning course topics and the educator interface, override the block
  with a compact variant. Same copyright and legal links on one line, small type, tight padding. The
  partial carries a `data-compact` attribute saying which variant rendered, so the choice is
  assertable without a test pinning utility classes. Its
  desktop sidebar is a sticky full-height column, so a full-bleed footer under the whole grid makes a
  learner scroll a viewport of pinned sidebar to reach it. A short bar keeps the legal links on the
  most learner-facing pages in the product and makes that scroll cost small. Aligning the footer to
  the content column instead would mean restructuring the shell's grid, and it would put the footer
  back inside `<main>`, losing the landmark.
- The exam and form runner blanks it, the way `_exam_runner_base.html` already blanks
  `{% block header %}` because the runner owns its own bar. Its layout is `h-screen overflow-hidden`
  with a `sticky bottom-0` action bar, so an inherited footer would be clipped or would collide.
- Error pages blank it. `500.html` and `503.html` are standalone documents that do not extend
  `_base.html` at all, deliberately, so they render with no request or database context. They cannot
  inherit the block. Blanking it on the other five keeps all seven behaving alike.

**Two override paths, both valid.** Resolution order is the host project's own `templates/`, then the
active theme's `templates/`, then FLS's app directories. So `templates/partials/footer_bar.html` in
the project wins over a theme-level copy. The originating note claimed the theme path is unusable
when FLS is a read-only submodule. That is overstated. A project can put its own
`themes/<slug>/templates/` under `BASE_DIR / "themes"` without writing into the submodule. Project
level is still the better default, because a footer is not tied to theme identity.

## Constraints the design has to respect

`research_footer_accessibility.md` holds the checkable list. These are the ones that shape the markup
rather than the styling. Exactly one `contentinfo` per page, so the runner's sticky action bar must
never be marked up as a second page-level `<footer>`. No explicit `role="contentinfo"`, because the
implicit role is enough now and validators flag the redundant one. If the links are wrapped in
`<nav>` it needs an `aria-label`, and the label is `Legal`. FLS labels every secondary `<nav>`
except the header's, and a second unlabelled one would make the two indistinguishable. Footer text and its focus ring both need
their contrast checked against the footer's own background, not assumed from a `text-muted` token
used elsewhere. Link order stays the same on every page.

The footer needs nothing for HTMX. Boosted player navigation targets and selects `#interface-main`,
so a footer outside `<main>` is never in a swap. No `hx-preserve`, no `aria-live`.

A downstream project's `templates/partials/footer_bar.html` lives outside FLS's own `@source` globs,
so its Tailwind classes are silently absent from the compiled bundle unless that project adds a glob
covering its template tree. This pitfall is already documented, but a brand-new template file is a
fresh way to hit it, so the footer's documentation should point at it.

## Not in this piece of work

A cookie-consent link or preferences control. FLS ships a tracking cookie with no consent gate and
documents that as the operator's responsibility, so there is nothing to link to. An accessibility
statement, which would mean a third value in `ALLOWED_DOC_TYPES` plus the content to go with it. A
contact address, since no `contact_email` setting or context value exists anywhere in FLS.
`research_legal_footer_content.md` covers what each would cost and which regimes drive them, for
whenever they are wanted.

Two pre-existing accessibility gaps stay open. FLS has no skip link anywhere in its chrome, and the
header's `<nav>` is the one unlabelled nav in the codebase. Neither is caused by this work.

Whether the footer gets its own `--color-footer` and `--color-on-footer` token pair, the way the
header and side panel have theme tokens, is a styling question for the spec to settle. There is no
footer token today because there was no footer.

## Research

- `research_footer_ux_patterns.md`. How comparable products treat footers on sidebar course pages,
  and the per-shell reasoning behind the coverage decisions above.
- `research_footer_accessibility.md`. The `contentinfo` landmark, the WCAG criteria a footer touches,
  and the HTMX and print questions.
- `research_legal_footer_content.md`. What FLS's legal-document machinery actually is, which template
  variables supply each footer item, and what the missing items would cost.
- `research_fls_extension_seams.md`. The `header_bar.html` conventions to match, the verified
  template resolution order, and the documentation surfaces that advertise the seam.
