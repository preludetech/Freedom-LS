# Research: internal spacing of buttons that carry an icon

## 1. Exact mechanism — why "Next" reads as cramped

The call site is `submodules/Freedom-LS/freedom_ls/learner_interface/templates/learner_interface/course_topic.html:15-57` (the `<c-player-nav>` block). Both nav buttons pass `size="small"`:

```
<c-button href="{{ previous_url }}" variant="secondary" icon_left="previous" size="small">Previous</c-button>
...
<c-button href="{{ next_url }}" icon_right="next" size="small">Next</c-button>
```

`size="small"` (`button.html:43`) appends a `btn-sm` class. That is the whole story — **`px-6 py-3` from the first_class theme never applies to these two buttons.** The cascade:

- `tailwind.components.css:163-168` — base `.btn { px-6 py-2 }` (default theme baseline).
- `tailwind.components.css:211-213` — `.btn.btn-sm { px-2 py-1.5 text-sm }`.
- `theme.css:95-99` (first_class) — reopens `.btn { px-6 py-3 text-sm font-semibold }`.

`.btn.btn-sm` is a **compound selector** (specificity 0,0,2,0) vs. the theme's `.btn` (specificity 0,0,1,0). Compound beats single regardless of import/source order, so **`.btn.btn-sm`'s `px-2 py-1.5` always wins over the theme's `px-6 py-3`**, on every theme, forever — this isn't a first_class-specific bug, it's true of the default theme too. Effective padding on Previous/Next is **8px horizontal / 6px vertical** (`px-2` = 0.5rem, `py-1.5` = 0.375rem), not the 24px/12px the brief's starting hypothesis assumed.

Icon markup (`button.html:50`) is hardcoded `size-5` (1.25rem = **20px**) regardless of `size="small"` — the icon does not scale down with the button. So on "Next": content row = `[label][ml-2: 8px][icon: 20px]`, sitting inside `px-2` (8px) padding on both sides. Right edge sequence is `…label → 8px gap → 20px icon → 8px padding → edge`. The CSS box distances (label→icon = 8px, icon→edge = 8px) are numerically *equal*, but they don't read as equal:
- The 20px icon is drawn on a tighter, mostly-hollow-arrow glyph (a chevron/arrow SVG typically has ample internal whitespace inside its own viewBox), so its *visible ink* sits closer to the icon box's trailing edge than the label's baseline sits to its own box edge. The optical margin from ink-to-edge is smaller than 8px even though the CSS box margin is 8px.
- A button height driven by `py-1.5` (6+6=12px) plus a 20px line-box is only ~32px tall — well short of the 44/48px targets discussed in §3 — so the icon (20px) occupies proportionally more of the button's total height than it would in a `px-6 py-3` button, making it read as "crowding the edge" rather than "sitting inside generous padding."

**`.btn-secondary`'s `border-2` is a second, smaller, real contributor.** Tailwind's global `border-box` sizing means the border is *inside* the button's outer visible edge and *outside* the padding: outer-edge → content distance = `border-width + padding`.
- Next (`.btn-primary`, no border): 0px border + 8px padding = **8px** outer-edge-to-content.
- Previous (`.btn-secondary`, `border-2` from `theme.css:101-103`): 2px border + 8px padding = **10px** outer-edge-to-content.

That's a real, if modest, 25% difference (10px vs 8px) that plausibly reads as "Previous looks a bit better" — on top of Previous using a *leading* icon (icon-then-label), which doesn't suffer the same trailing-edge optical-weight problem (see §2).

## 2. The optical-balance problem with trailing icons

Equal left/right padding around an icon+label reads as *unbalanced* toward the icon side, because glyphs are visually "lighter" (less ink, more internal whitespace) than a text label of the same box height. Design systems compensate by giving the icon side *less* end padding than the label-only side, or by controlling the icon-label gap with `gap` rather than folding it into the padding box. Concrete precedent:

- **Material Design 3** — button padding conventions: an icon side gets **16dp** padding-start/end while the icon-free label side gets **24dp** (text-only buttons use symmetric 24dp both sides only when there is *no* icon at all). Icon size in MD3 buttons is **18dp**, gap between icon and label **8dp**. Filled/outlined/text buttons are **40dp** tall, container radius full/pill; the surrounding touch target is padded out to **48×48dp** even when the visible button is shorter. ([m3.material.io/components/buttons/specs](https://m3.material.io/components/buttons/specs), [m3.material.io/components/icon-buttons/specs](https://m3.material.io/components/icon-buttons/specs))
- **Shadcn/ui** — default button: `h-9 px-4 py-2 gap-2`, with a global icon rule `[&_svg]:size-4 [&_svg]:shrink-0` (icons fixed at 1rem/16px, spaced via the container's `gap-2`, not per-icon margin). ([shadcn button docs](https://v3.shadcn.com/docs/components/button))
- **Tailwind UI** catalog buttons use `gap-x-1.5`/`gap-x-2` on the flex button itself for icon spacing at every size step (`xs`–`xl`), never per-icon margin — i.e. Tailwind's own reference implementation already treats this as a `gap` problem, not a margin problem.
- **Bootstrap 5** — `.btn { padding: .375rem .75rem; font-size: 1rem; line-height: 1.5; border: 1px solid transparent; }` (6px/12px); Bootstrap has no built-in icon slot, so icon spacing is whatever utility (`me-2`, or a flex `gap`) the consuming template chooses — it doesn't prescribe an answer, but its own docs example code favours `gap` in flex-based custom buttons.
- **Apple HIG** — minimum tappable area **44×44pt**; recommends 12–48px between adjacent controls to avoid mis-taps; icon/label spacing inside a button is left to the platform's system button styles rather than a fixed px value. ([HIG discussion citing 44pt minimum](https://medium.com/@zacdicko/size-matters-accessibility-and-touch-targets-56e942adc0cc))
- **WCAG 2.2 SC 2.5.8 Target Size (Minimum, AA)** — interactive targets must be **≥ 24×24 CSS px** unless spaced ≥24px from neighbours, inline in text, or the size is essential/user-agent-controlled. ([W3C SC 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), search-confirmed via [github.com/w3c/wcag#1894](https://github.com/w3c/wcag/issues/1894)) The stronger **44×44** figure is WCAG 2.1 SC 2.5.5 Target Size (Enhanced, AAA), not a hard AA floor. FLS's `btn-sm` (~32px tall) clears the 24px AA floor (given the buttons sit at opposite ends of a `justify-between` row, well over 24px apart) but misses the 44px AAA/HIG recommendation — worth flagging even though it's out of scope for this pass.

**Convention to adopt:** keep the icon-adjacent edge padding smaller than the label-adjacent edge padding when there is exactly one icon, or — the more idiomatic Tailwind-v4 fix — decouple icon-label spacing from edge padding entirely by moving to `gap` (§4), which sidesteps the "which side gets less padding" arithmetic altogether at these tight `btn-sm` sizes and matches what Tailwind UI and Shadcn already do.

## 3. `gap` vs. icon margins — recommendation: move to `gap`

Current: `button.html:32,47,50` puts `mr-2`/`ml-2` directly on the `<c-icon>` element, inside a `.btn` container that is `inline-flex items-center justify-center` (`tailwind.components.css:164`) but declares **no `gap`**.

Moving the spacing to the container (`.btn { gap: 0.5rem }` / `gap-2`, dropping `mr-2`/`ml-2` from the icon) is the correct direction:
- It's the idiomatic Tailwind v4 pattern (Tailwind UI and Shadcn both do exactly this — see §2).
- It fixes compounding cases the margin approach gets wrong today: `dropdown-menu.html` items and the `loading` state (`button.html:47-48`) both slot an icon *and* text as siblings — with `gap`, spacing "just works" between whichever children are actually present (icon-only, icon+label, label+icon, or icon+icon for a loading spinner + label), whereas margin has to be re-specified per icon per position and breaks if a future variant adds two icons (e.g. a leading status icon plus a trailing chevron) since only one of them would carry the correct margin direction.
- `gap` naturally collapses to zero extra space when only one child renders (e.g. `icon_left` set but no slot content) — margin-based spacing always reserves the margin even with nothing on the other side of it, producing lopsided single-icon buttons today.

**What breaks if `mr-2`/`ml-2` are simply deleted without adding `gap`:** icon and label would touch with zero space between them. Grep confirms every consumer goes through `<c-button icon_left="…">`/`icon_right="…"` — none of the 115 files matching `c-icon|size-5` inject a raw `<c-icon>` directly into a button's slot expecting the *component's* margin to separate it from adjacent text (`base/templates/cotton/header-button.html`, `content_engine/templates/cotton/accordion.html`, `base/templates/cotton/callout.html`, `base/templates/partials/_toast.html`, `learner_interface/templatetags/course_icon_tags.py` etc. are all independent, non-`c-button` contexts using their own `size-*`/margin classes — none of them reuse `button.html`'s icon margin). So the only breakage risk is confined to `button.html` and `dropdown-menu.html`'s inline "icon + slot" markup (`button.html:32,47,50`) — both must be edited together (margins removed, `gap-2` added to the `.btn` / dropdown `computed_class` container) in the same change, since they are the only two places the margin currently does load-bearing work.

## 4. A concrete recommended spec

| Token / utility | Current FLS value | Recommended value | Rationale |
|---|---|---|---|
| `.btn` default padding | `px-6 py-3` (theme) / `px-6 py-2` (base) | keep `px-6 py-3` (unchanged) | Not the defect; default-size buttons aren't in the screenshot. |
| `.btn.btn-sm` padding | `px-2 py-1.5` | `px-3 py-2` | 8px/6px is below comfortable hit-target territory once a 20px icon shares the box; 12px/8px keeps the "small" size distinct from default while giving the icon room. |
| Icon size (all buttons) | `size-5` (20px), fixed regardless of `size=` | keep `size-5` on default, drop to `size-4` (16px) inside `btn-sm` | A 20px icon inside a `py-2` (8px) box forces ~32px+ height; a 16px icon matches Shadcn's own small-button icon scale-down and keeps `btn-sm` visibly "small." |
| Icon-to-label gap | `mr-2`/`ml-2` (8px) on the icon | `gap-2` (8px) on `.btn` container; **remove** icon margins | Modern idiom (§3); fixes icon-only / multi-icon cases for free. |
| Trailing-icon end-padding adjustment | none (symmetric `px-2` both sides) | N/A once on `gap` — end padding no longer needs a manual asymmetric reduction, because `gap` cleanly separates "space to sibling" from "space to container edge"; both edges keep the *same* padding value (`px-3`) and read balanced because the icon is no longer sharing a box with a folded-in margin | Removes the arithmetic in §2 entirely rather than hand-tuning an asymmetric padding pair. |
| `.btn-secondary` border | `border-2` (first_class only) | keep | Real but minor (2px/side) contributor to the "Previous looks better" read; not worth touching in isolation. |
| Minimum hit target | ~32px tall at `btn-sm` (8px/6px padding + 20px icon) | ~36-40px tall at `px-3 py-2` + `size-4` icon | Still short of Apple/WCAG-AAA's 44px, but clears WCAG 2.2 AA's 24px floor with margin; going further (e.g. `min-h-11`) is a separate, bigger decision than this pass. |

## 5. Where the fix lives

Everything enumerated above is inside `submodules/Freedom-LS`, which this project must never edit:
- `.btn.btn-sm` padding, `.btn` gap: `submodules/Freedom-LS/tailwind.components.css:163-213` — a `@layer components` CSS rule.
- Icon margins (`mr-2`/`ml-2`) and the icon-size-doesn't-shrink-with-`btn-sm` behaviour: `submodules/Freedom-LS/freedom_ls/base/templates/cotton/button.html:32,47,50` and its dropdown twin at line 20/32 — a component **template**, not CSS.

Per `submodules/Freedom-LS/docs/how tos/theme-fls.md`, this project's own theming surface splits cleanly along that same CSS/template line:

- **Reachable now, no upstream needed (Tier 2 CSS override):** the `.btn.btn-sm` padding fix and adding `.btn { gap: 0.5rem }` are pure `@layer components` rules. This project's active theme is `first_class` (`config/customisation.py:30`, `FLS_THEME=first_class` in `.env.example`), resolved from `submodules/Freedom-LS/freedom_ls/themes/first_class/…` — this project has **no** `themes/first_class/` directory of its own, so it cannot shadow-and-edit that theme's `theme.css` without duplicating the entire theme bundle (the FLS resolver only wires in the *one* directory matching `FLS_THEME`, taken whole — see `configure_theme` in `docs/how tos/theme-fls.md:56-79`). The scaffolded `themes/custom/static/themes/custom/theme.css` in this project (`themes/custom/static/themes/custom/theme.css:1-41`) is **not currently imported anywhere** in `tailwind.input.css` and `FLS_THEME` is not set to `custom`. The clean fix: add `@import "./themes/custom/static/themes/custom/theme.css";` to `tailwind.input.css` immediately after the existing first_class import (`tailwind.input.css:52`) — the Tailwind-side active-theme import list is hardcoded and independent of Django's `FLS_THEME` runtime resolution (docs: "downstream projects own their own `tailwind.input.css`… they edit the import directly"), so this works as a pure CSS Tier-2 add-on without touching `FLS_THEME` or fabricating a `themes/first_class/` shadow directory. Put the `.btn.btn-sm { @apply px-3 py-2; }` and `.btn { gap: 0.5rem; }` overrides in that file.
- **Not reachable without an upstream hand-over (Tier 3 template):** removing `mr-2`/`ml-2` from the icon and shrinking the icon to `size-4` under `btn-sm` require editing `cotton/button.html` itself. Overriding it via this project's own Tier-3 mechanism would require the *active* `FLS_THEME` slug's template directory to exist under this project's `themes/<slug>/templates/cotton/button.html` — but the active slug is `first_class`, and creating `themes/first_class/` here would shadow (not merge with) the *entire* submodule theme bundle, forcing a full duplication of `theme.css` too just to patch one template. That's not a reasonable Tier-3 use (the docs describe Tier 3 as "an escape hatch," not a mechanism for forking an entire upstream theme). **Recommendation: file the icon-margin→gap change as an FLS upstream PR/hand-over** against `submodules/Freedom-LS/freedom_ls/base/templates/cotton/button.html` (and the matching dropdown-menu icon markup), then `git -C submodules/Freedom-LS pull` once merged.

## Summary of recommendation
1. Ship a Tier-2 CSS-only fix now: import `themes/custom/theme.css` from `tailwind.input.css` after the `first_class` import, and put `.btn.btn-sm { @apply px-3 py-2; }` plus `.btn { gap: 0.5rem; }` in it.
2. The deeper fix (icon `mr-2`/`ml-2` → `gap-2`, icon `size-5`→`size-4` under `btn-sm`) lives in FLS's `cotton/button.html` template and is out of reach from this project without forking the whole `first_class` theme directory — hand it upstream.
3. `.btn-secondary`'s `border-2` (first_class Tier-2 override) is a genuine but small (2px/side) contributor to "Previous looks better than Next" and does not need independent action.

status: ok
