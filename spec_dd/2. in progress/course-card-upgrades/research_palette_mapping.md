# Deterministic name → theme-palette mapping

> **Implementation note (post-build):** the shipped feature diverged from the
> hash-of-title → role-token recommendation below. It instead uses a **separate,
> neutral 5-slot accent series** (`PALETTE = ("1".."5")`) rendered as vibrant
> **gradients** (`--fls-course-accent-<N>`), decoupled from the semantic UI role
> tokens so card vibrancy can be tuned without recolouring buttons/badges. The slot
> is **stored** on `Course.accent_slot` and assigned by per-site creation order
> (`count() % 5`) for guaranteed even distribution, rather than hashed from the title.
> The role soft-tints below (`--color-{role}-soft`, 12%) still exist and are used for
> general accents (e.g. the completed-card badge), just not for the accent tiles.
> The notes below are retained as the research record of the original approach. See
> `1. spec.md` §2 for the as-built contract.

## Recommendations for FLS

- **Use a 5-token subset, not the full role set.** Pick `primary`, `secondary`, `accent`, `info`, `success` for the per-course accent. Deliberately **exclude `error`/`warning`** so a course card never reads as a status alert, and exclude `surface`/`surface-2` (they are the card itself). Five buckets is enough variety for most cohorts; six (add `tertiary` if the theme defines one) is the upper limit before the wall of cards starts to look chaotic.
- **Hash with SHA-256, fold to an int, modulo the palette length.** MD5 (as used in `branch_name_to_color`) is fine for this non-security use, but SHA-256 is the de-facto standard in `color-hash`/XEP-0392-style libraries and gives better distribution on small palettes. Take the first 4–8 bytes of the digest, interpret as unsigned int, modulo `len(palette)`.
- **Render as "soft tint background + role-coloured icon".** Background = `--color-{role}` mixed 10–14% into `--color-surface` (CSS `color-mix(in oklab, var(--color-X) 12%, var(--color-surface))`). Icon = `--color-{role}` at full saturation. This is the Tailwind `bg-X-100 text-X-700` / Material 3 `X-container` / `on-X-container` pattern and is the most reliably legible. Do **not** use `--color-on-X` over `--color-X` for the card body — full-saturation backgrounds fight progress bars and make a six-card grid feel like a circus.
- **Verify 3:1 non-text contrast for the icon against the tint at theme build time**, not at runtime. Each (role, surface) pair is a fixed combination per theme, so this is a lint check, not a per-render computation.
- **Keep the title text on `--color-on-surface`**, never on the tinted background colour. The tint is an accent; the title still has to read like a title.
- **Make the mapping pure and stable.** Function signature: `course_accent_role(title: str) -> str` returning the token name (`"primary"`, `"accent"`, ...), not a hex value. Templates render `bg-{{ role }}-soft text-{{ role }}`. This survives theme switches for free.
- **Optional escape hatch:** allow a `Course.accent_override` field for editors who really need a specific colour (e.g. brand-aligned flagship course). Don't build it yet, but reserve the mapping function so it can be overridden.

## Reference implementations

- **GitHub Linguist** assigns one curated hex per language in `languages.yml`; colours are picked **by humans** for distinctiveness, not hashed. Works because the set is finite and edited via PR.
- **GitLab Pajamas avatars** use identicons with a **fixed light-tint palette** for project/group default avatars; selection is hash-based. The Pajamas guidance is explicit that avatar tints come from a constrained list.
- **Notion** exposes only **10 built-in icon colours**; users pick, the system doesn't auto-assign. Reinforces that small palettes are the norm even when humans choose.
- **Trello** ships ~30 curated label colours with a colour-blind toggle that adds a pattern; explicit WCAG AA target for label-on-card contrast.
- **Material 3** uses `primary-container` / `on-primary-container` (and the same for secondary/tertiary) as the canonical "soft tint + legible foreground" pair — exactly the pattern to copy.
- **XEP-0392** is the cleanest spec for "string → constrained palette": hash → hue angle → snap to nearest palette angle. Explicitly warns implementers not to assume uniqueness.

## Hashing strategies

- **MD5/SHA-256 + modulo** is fine for palettes up to ~16 entries; modulo bias on a 5-entry palette from a 256-bit digest is negligible. Don't use Python's built-in `hash(str)` — it's randomised per-process.
- **Avoid `sum(ord(c)) % n`** (the naive `string-to-color` approach): anagrams collide and short titles cluster on low indices.
- **Don't** hash to HSL then snap to nearest palette colour by hue distance — for a 5-entry palette this is just a more expensive modulo and re-introduces clustering when the palette hues are unevenly spaced (which they are, in any brand theme).
- For 5–8 buckets, expect ~1 collision per ~3 sibling courses. That's fine; the goal is variety, not uniqueness.

## Accessibility on tinted backgrounds

- **WCAG 1.4.11** requires **3:1** non-text contrast for meaningful icons/UI components against their adjacent background. Decorative icons that duplicate the title don't strictly need it, but treat the course icon as meaningful.
- A 10–14% tint of a saturated role colour into `surface` almost always clears 3:1 against the same role colour at full saturation in light themes; verify per theme. Dark themes need a higher mix (~18–22%) or the role colour stepped one tone lighter for the icon.
- `--color-on-X` over `--color-X` (full-saturation card) clears 4.5:1 trivially but is visually loud across a grid. Reserve that pattern for single-card hero states.

## Soft-tint patterns

- Tailwind `bg-X-100 text-X-700`, Material 3 `X-container` / `on-X-container`, Carbon "subtle" tag styles, Radix `X3` background + `X11` text — all converge on the same recipe: **low-chroma background, mid-to-high-chroma foreground, both derived from one hue**. Use OKLCH/`color-mix` for the tint so it survives theme swaps without per-token hand-tuning.

## Pitfalls to avoid

- Including `error`/`warning` in the rotation — a red "Intro to Python" card looks broken.
- Pure-hue rotation across the spectrum — a 6-card grid with red/orange/yellow/green/blue/purple looks like a toy.
- Tinted backgrounds saturated enough to compete with the course progress bar.
- Hashing to arbitrary HSL (the current `branch_name_to_color` style) for production UI — it ignores the theme and breaks dark mode.
- Trying to guarantee no-two-adjacent-cards-the-same; that's a layout-ordering problem, not a hashing problem, and solving it stochastically makes the mapping non-deterministic.
- Storing the resolved hex on the model — store the **role token** so theme switches keep working.

## References

- [GitHub Linguist languages.yml](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)
- [How GitHub picks language colors (Quora)](https://www.quora.com/How-did-GitHub-select-its-language-colors)
- [GitLab Pajamas — Avatar component](https://design.gitlab.com/components/avatar/)
- [Notion Help — Style & customize your page](https://www.notion.com/help/customize-and-style-your-content)
- [Trello — 20 new label colors (Atlassian)](https://www.atlassian.com/blog/trello/20-new-trello-label-colors)
- [Material Design 3 — Color roles](https://m3.material.io/styles/color/roles)
- [Material Design 3 — How the color system works](https://m3.material.io/styles/color/system/how-the-system-works)
- [IBM Carbon — Color overview](https://carbondesignsystem.com/elements/color/overview/)
- [XEP-0392: Consistent Color Generation](https://xmpp.org/extensions/xep-0392.html)
- [color-hash (zenozeng) — SHA-256 + HSL](https://github.com/zenozeng/color-hash)
- [string-to-color (Marko19907)](https://github.com/Marko19907/string-to-color)
- [colorhash on PyPI](https://pypi.org/project/colorhash/)
- [WCAG 2.1 Understanding 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html)
- [W3C G207 — 3:1 contrast for icons](https://www.w3.org/WAI/WCAG21/Techniques/general/G207)
- [WebAIM — Contrast and Color Accessibility](https://webaim.org/articles/contrast/)
- [Red in UI Design — best practices and pitfalls](https://medium.com/design-bootcamp/red-in-ui-design-guidelines-limits-and-smart-ux-decisions-0dd94cf2667d)
- [Carbon — Status indicator pattern](https://carbondesignsystem.com/patterns/status-indicator-pattern/)
