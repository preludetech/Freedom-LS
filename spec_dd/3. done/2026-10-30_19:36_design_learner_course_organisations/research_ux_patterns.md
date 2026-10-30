# Research: UX patterns for provider attribution on course cards, detail page and sidebar

Scope: the idea in `idea.md` (circular logo + org name under card header; tags top-right; text-only "Details" bottom-right; detail-page byline above an hr; "about the provider" sidebar card). Brand constraints from `.claude/skills/brand-guidelines/visual.md`. Web search coverage was thin (few direct sources); items marked (practice) are common conventions I'm stating from general knowledge, not a cited source.

## Brand constraints that bind the design
- Use role tokens and components only: `<c-chip>` for tags/levels (not status), `.surface` for the sidebar card, `<c-button variant="link">` for the text-only action, `<c-media-card>` exists for image cards. No new hex values.
- "If it's clickable, it looks clickable"; surfaces stay flat (no new shadows/borders beyond what the component carries). This favours a visibly link-styled "Details" and no extra dividers, matching the idea.
- Headings, body, links take no classes; `text-muted` for secondary text (org name row on cards).

## Patterns

1. **Avatar/byline row.** Small circle + single-line name, vertically centred, `flex items-center gap-2`. Same row shape on card, detail header and sidebar card, differing only by size. Make it one reusable component (`<c-...>` taking org) to honour the repo's no-repetition rule.
2. **Logo sizes.** Design-system size presets run from ~28px (compact inline) to ~64px (organisation pages), with a medium size recommended for list rows ([company-logo component docs](https://www.mintlify.com/ax-derrick/axmed-design-system/components/company-logo)). Suggested mapping (practice): card ~24-32px (`size-6`/`size-8`), detail byline ~32-40px, sidebar card ~48-64px. Keep fixed pixel/rem boxes with `shrink-0` so the circle never squashes.
3. **Long names.** Cards: single line, `truncate` (`min-w-0` on the flex child is required or ellipsis never fires), with `title` attribute carrying the full name. Detail byline and sidebar card have room: allow wrapping (`break-words`), maybe clamp to 2 lines in sidebar. Never let the name push the tag chips or Details action.
4. **Missing logo fallback.** Initials monogram in the same circle is the standard; one design system generates the colour deterministically from the name ([company-logo](https://www.mintlify.com/ax-derrick/axmed-design-system/components/company-logo)); Shopify Polaris avatar falls back to initials when src is missing, fails, or is slow ([Polaris avatar](https://shopify.dev/docs/api/app-home/polaris-web-components/media-and-visuals/avatar)). Here, the idea's fallback is the org's *default logo* (profile image else default logo), so a monogram is only needed if both are absent; tint from theme tokens (`bg-surface-2` + `text-muted`) rather than generated hexes, to stay on-brand and dark-mode safe. Also handle broken image URLs (onerror/hide) if cheap.
5. **Wide / non-square logos in circles.** Logos are usually wordmarks, so `object-cover` crops them badly. Use `object-contain` with padding on a neutral surface background inside the circle ([MDN object-fit](https://developer.mozilla.org/en-US/docs/Web/CSS/object-fit): contain for logos, cover for photos). A "profile" image upload (idea's data section) is intended square-ish; still enforce contain, and document/validate recommended aspect (e.g. square, min size) on the upload field help text. Optionally a thin ring (`ring-1` border token) so white-background logos stay visible on light cards.
6. **Tag placement and density.** Tags top-right, opposite the title/provider, are a G2-style layout: keep to 1-3 chips, `size="xs"`, no wrapping into the title; let chips wrap or overflow-hide (+N) on narrow widths (practice). Provider+level share the left cluster, tags the right; on mobile move tags below the title rather than squeezing.
7. **Text link vs bordered button, whole-card vs explicit action.** Text-only secondary action at bottom-right is a low-emphasis pattern; works when the card is also clickable or when "Details" is the only action. Whole-card click is common but has costs: screen readers read the entire card as the link label, structure lost, text unselectable ([Inclusive Components: cards](https://inclusive-components.design/cards/), [Nomensa](https://nomensa.com/blog/how-build-accessible-cards-block-links), [Atlas stretched-link](https://microsoft.github.io/atlas-design/components/card.html)). Recommended: one real link (the "Details" text, or the title) with a stretched-link `::after` covering the card, only if the card has a single link target. The idea says no link to org details, which keeps that true. Give the text link a descriptive accessible name (`aria-label="Details: <course title>"`) because many identical "Details" links fail link-purpose tests, while keeping visible text always "Details" as requested. Ensure a minimum ~44px tap target via padding even though visually borderless, and a visible focus ring (`focus-ring` token).
8. **Responsive.** Detail page: sidebar card stacks below main content on mobile (single column, `order` after content; with "under existing right-hand content" desktop it simply follows in DOM order, so no reordering trick needed). Consider whether provider info should appear before long content on mobile; the byline in the header already covers attribution there, so below-content is fine. Cards: grid collapses to one column; the name row truncates, tags drop under title.
9. **Dark mode logos.** Transparent/dark logos vanish on dark surfaces, and light logos vanish on light. Safest pattern: render the logo on a fixed light neutral backing inside the circle (`bg-white`/surface token + padding + contain) in all themes, rather than trying to invert. Check the monogram fallback and ring use tokens that flip with the theme. Verify against each shipped theme (`default`, `first_class`).

## Recommendations to carry into spec
- One shared org-attribution component with `size` and `wrap|truncate` options, used by dashboard card, long-format card, detail header and sidebar.
- `object-contain` + padded light backing in a fixed circle; monogram fallback via tokens.
- Single stretched link on the card; visible text "Details", descriptive `aria-label`; adequate hit area and focus style.
- Truncate on cards (with `title`), wrap on detail/sidebar; `min-w-0` on flex children.
- Specify logo upload guidance (square, min dimensions) and a test with a very long org name, a wide logo, no logo.

## Sources
- https://inclusive-components.design/cards/
- https://nomensa.com/blog/how-build-accessible-cards-block-links
- https://microsoft.github.io/atlas-design/components/card.html
- https://www.mintlify.com/ax-derrick/axmed-design-system/components/company-logo
- https://shopify.dev/docs/api/app-home/polaris-web-components/media-and-visuals/avatar
- https://developer.mozilla.org/en-US/docs/Web/CSS/object-fit
- https://doc-en.scheer-imc.com/FuncRef/learning-card (provider logo placement on learning cards)

status: ok
