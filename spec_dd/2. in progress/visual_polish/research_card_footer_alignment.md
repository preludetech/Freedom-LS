# Research: bottom-aligning the "Details" action inside equal-height course cards

## 1. Exact mechanism of the misalignment

Confirmed against the screenshot (`spec_dd/1. next/visual-polish/dashboard cards.png`): the "Introduction to the Drone Industry" card has a two-line title and its Details link sits ~32px lower than the two one-line-title cards beside it.

The shell, `cotton/course-card-shell.html:19-29`:

```html
<article class="course-card ... h-full relative p-0 overflow-hidden flex flex-col ...">
    <div class="course-accent-... course-card-hero flex items-center justify-center">...</div>
    <div class="course-card-body flex-1 space-y-2">
        {% if eyebrow %}{{ eyebrow }}{% endif %}
        {{ slot }}
        {% if footer %}{{ footer }}{% endif %}
    </div>
</article>
```

`<article>` is `flex flex-col`, so `course-card-hero` and `course-card-body` are its two flex-column children. `flex-1` on `course-card-body` only says *how the body item is sized relative to its sibling (the hero) inside the article's flex column* — it makes the body stretch to fill the article's remaining height. It does **not** make `course-card-body` itself a flex container. `course-card-body` has no `display: flex` of its own (`tailwind.components.css:306` only adds `padding: var(--fls-card-padding)` to the `.course-card-body` class, and the template adds `flex-1 space-y-2`, not `flex flex-col`). So its own children — eyebrow, title `<h3>`, optional "Next up" `<p>`, the Details `<div class="flex justify-end">` (`learner_interface/partials/course_card.html:62`), optional footer — lay out as ordinary block boxes stacked with `space-y-2` margins.

Consequence: any *extra* height that `flex-1` adds to `course-card-body` (to make the card match the tallest sibling in the grid row) lands **after the last block child** — below the footer if present, or below the Details row if not — because block layout has no mechanism to redistribute that slack among earlier children. The Details link's vertical position is therefore determined purely by the summed height of everything above it (eyebrow + title), which varies with title line count. That is exactly the observed defect.

## 2. Candidate fixes

### (a) `mt-auto` on the Details row inside a `flex flex-col` body

Requires two things: `course-card-body` must actually become a flex container (`flex flex-col`), and the Details wrapper div (`course_card.html:62`, `<div class="flex justify-end">`) needs `mt-auto`.

**The `space-y-2`/`mt-auto` interaction, verified against this project's own compiled CSS** (not assumed from memory): `static/vendor/tailwind.output.css:1153-1158`

```css
.space-y-2 {
  :where(& > :not(:last-child)) {
    --tw-space-y-reverse: 0;
    margin-block-start: calc(calc(var(--spacing) * 2) * var(--tw-space-y-reverse));
    margin-block-end: calc(calc(var(--spacing) * 2) * calc(1 - var(--tw-space-y-reverse)));
  }
}
```

Two things fall out of this that contradict the naive v3-era assumption:

1. In this installed Tailwind v4, `space-y-2` sets **`margin-block-end` (margin-bottom)** on every non-last child (with `--tw-space-y-reverse: 0`, `margin-block-start` collapses to 0). It is **not** `margin-top` on non-first children (that was the Tailwind v3 behaviour, `.space-y-2 > * + * { margin-top: 0.5rem }`; see the [Tailwind v4 upgrade guide, "Space-between selector"](https://tailwindcss.com/docs/upgrade-guide), which documents the switch from `margin-top` to `margin-bottom` on `:not(:last-child)`). So `mt-auto` (margin-**top**) on the Details row is a different CSS property from what `space-y-2` writes — there is no property collision at all.
2. Even if there were, the selector is wrapped in `:where(...)`, which has **zero specificity**. A plain utility class like `.mt-auto { margin-top: auto }` (specificity 0,1,0) always beats a `:where()`-wrapped rule (specificity 0,0,0) regardless of source order. This zero-specificity wrapper is Tailwind v4's deliberate mechanism for letting per-child margin utilities override `space-y`/`space-x` — see the [space-y upgrade discussion](https://github.com/tailwindlabs/tailwindcss/discussions/14322) and [issue #15699](https://github.com/tailwindlabs/tailwindcss/issues/15699) on the v4 `space-y-*` + per-child margin interaction.

So **`mt-auto` and `space-y-2` do not fight each other in this codebase**, on either axis (property or specificity). The only real prerequisite is giving `course-card-body` `display: flex; flex-direction: column` so `mt-auto` has a flex context to push against.

**Survives "Next up" line / progress-bar footer?** Yes, and cleanly, because of how the dashboard actually groups cards: `learner_interface/partials/course_list.html` renders four *separate* grids (`current-courses`, `recommended-courses`, `available-courses`, `learning-history`), each fed a single `course.listing_status` population. Within any one grid, every card has the same footer/next-up shape:
- `current-courses` (registered_courses): every card is `registered` or `in_progress`, and — per `test_course_cards.py`'s `test_registered_card_shows_empty_progress_bar` — a `registered` (0% progress) card **always** renders the progress-bar footer too, specifically so it "visually anchors next to in-progress cards in a mixed grid row." So every card in this grid has a footer.
- `recommended-courses` / `available-courses` / `learning-history`: no footer, no "Next up" line, in every card (these statuses never satisfy the `registered`/`in_progress` footer condition at `course_card.html:66`).

So `mt-auto` pushes Details to sit directly above the same-shaped footer (or directly at the card's bottom edge when there is no footer) *consistently across every card in a given grid* — which is the actual observed defect's scope. It does not achieve pixel alignment for a hypothetical mixed grid containing both footer and non-footer cards, but no such mixed grid exists in this codebase today.

**Where does it need to change?** `course-card-body`'s `display:flex; flex-direction:column` is shared with `course-row-shell.html:46` (the "all courses" row also uses the `course-card-body` class) — so this part is a shell-level (shared) change. The `mt-auto` on the Details wrapper only needs to change in `course_card.html:62` (the card leaf), since the row variant already right-aligns Details in the eyebrow slot and needs no change (see §4).

### (b) Make the *title* block the flex-grow element instead

E.g. wrap eyebrow+title in a `flex-1` block and leave Details/footer outside it. This achieves the same visual result as (a) but requires restructuring `course_card.html`'s markup into an explicit two-region split (grow region / pinned region), which is a bigger diff than adding one `mt-auto` class, and still needs `course-card-body` to be `flex flex-col` for the inner `flex-1` to mean anything. No real advantage over (a); strictly more invasive for the same outcome.

### (c) CSS Grid `subgrid` across sibling cards

`grid-template-rows: subgrid` would let each card's title/details/footer rows align to shared row tracks across the whole grid row, independent of `flex`. Rejected: it requires turning the grid container in `course_list.html` **and** the shell's internal structure into cooperating grid/subgrid definitions, touching multiple submodule files, and — critically — the different card variants have a *different number of internal rows* (some have a "Next up" line and a footer, some have neither), which defeats naive subgrid row-matching (subgrid alignment assumes the same row count/order per item). Much higher blast radius for no better outcome than (a), given the grids are already status-homogeneous.

### (d) A dedicated `actions` slot in the shell, styled `mt-auto` by the shell itself

Cleaner from a component-design perspective (the shell would own "pin this slot to the bottom" the same way it owns `footer`), but this requires editing `cotton/course-card-shell.html` itself — a Tier-3 cotton-component shadow that must replicate the *entire* `<c-vars>` contract (`accent_slot_key, icon, icon_fallback, title, clickable, class`) per `docs/how tos/theme-fls.md`'s Tier-3 warning ("Removing a prop or changing a default is a breaking change"). That is a materially larger, more fragile fork than shadowing the small `course_card.html` leaf partial in (a), for the same visual result. Rejected in favour of (a).

## 3. Recommendation

**Fix (a): make `course-card-body` a real flex column (Tier-2 CSS) and add `mt-auto` to the existing Details wrapper (small Tier-3 shadow of the one leaf template that needs it).** It is the smallest possible diff that fixes the reported defect exactly where it's reported, does not touch the shared cotton shell's prop contract, does not require restructuring markup, and — as shown above — has no actual conflict with `space-y-2` in this Tailwind v4 install (different property, and even under a hypothetical collision, `:where()` zero specificity resolves in `mt-auto`'s favour). The one real risk (widening `course-card-body` to `flex flex-col` is a shared-class change that also touches the row shell) is a low-risk, easily screenshot-verified no-op, since the row's children already stack in document order with no float/percentage-height assumptions that flex-column layout would disturb.

## 4. Blast radius

| Template | Uses shell / details link? | Effect of the recommended fix |
|---|---|---|
| `cotton/course-card-shell.html` | Shell; `.course-card-body` gets `display:flex;flex-direction:column` via Tier-2 CSS | No visible change by itself (children still stack top-to-bottom); it's the prerequisite that makes `mt-auto` work in the shadowed `course_card.html` |
| `cotton/course-row-shell.html:46` | Shares the `.course-card-body` class for its right-hand column | Also becomes `flex flex-col` — should be visually identical (plain block-stacked children have no float/negative-margin/percentage-height dependency on being a block container), but is the one item to screenshot-diff before shipping, since it's an incidental side effect, not the intended target |
| `learner_interface/partials/course_card.html:62` | The Details wrapper `<div class="flex justify-end">` | This is the file being shadowed; gets `mt-auto` added — the intended fix. Loader resolves the downstream copy first because `BASE_DIR / "templates"` precedes the FLS app template dirs in `TEMPLATES[0]["DIRS"]` (`config/settings_base.py:145-147`, further prepended-to by `configure_theme` for the active theme, `config/settings_base.py:224-229`) |
| `learner_interface/partials/course_row.html:55` | Includes `course_details_link.html` inline inside the `eyebrow` slot's own `flex items-center justify-between` row (top-right of the row), *not* inside `course-card-body`'s block flow | Already immune to this defect by construction (its own docstring: "details -> course_details_link.html, right-aligned inline with the status in the eyebrow slot"); unaffected by the `course_card.html` shadow; only indirectly touched by the shared `.course-card-body` flex-col change (see row above) |
| `learner_interface/partials/course_details_link.html` | The `<c-button>` itself | Untouched — no class or markup change |
| `learner_interface/partials/course_list.html` | Includes `course_card.html` per course, 4 separate grids (`current-courses`, `recommended-courses`, `available-courses`, `learning-history`) | Not touched directly; benefits from the fix everywhere it includes `course_card.html`, since each grid is status-homogeneous (see §2a) so `mt-auto` produces a consistent baseline within every grid |
| `course_applications/templates/course_applications/partials/dashboard_applications.html` | Uses `space-y-2` but not the course-card shell or Details link | Unaffected — irrelevant to this fix, included above only because it matched an earlier grep for `space-y-2` |

## 5. Where the fix lives

Every file discussed as the *shared* mechanism (`cotton/course-card-shell.html`, `cotton/course-row-shell.html`, `tailwind.components.css`'s `.course-card-body` rule) is inside `submodules/Freedom-LS`, which this project must never edit per `CLAUDE.md`. **The fix is nonetheless fully achievable from the downstream project**, using the theming mechanism already documented in `submodules/Freedom-LS/docs/how tos/theme-fls.md` and already exercised once in this repo:

1. **Tier 2 — CSS component-class override.** Reopen `.course-card-body` in `@layer components` inside `themes/custom/static/themes/custom/theme.css` (currently a near-empty stub with only commented-out token examples):

   ```css
   @layer components {
       .course-card-body {
           @apply flex flex-col;
       }
   }
   ```

   Per `theme-fls.md`'s cascade description, the active theme's `theme.css` is imported *last*, so this wins over the FLS default `.course-card-body { padding: ... }` rule without `!important`.

2. **Tier 3 — small template shadow.** Add `templates/learner_interface/partials/course_card.html` at the project root, an exact copy of the FLS partial with `mt-auto` added to the one line at `course_card.html:62` (`<div class="flex justify-end mt-auto">`). This is the same shadowing pattern the project already uses for `templates/learner_interface/partials/anonymous_hero.html`, which its own comment marks as a "Project override of the FLS default hero." Django resolves this before the FLS app's copy because `configure_theme()` prepends the active theme's `templates/` dir, and `BASE_DIR / "templates"` is already first in `TEMPLATES[0]["DIRS"]` (`config/settings_base.py:142-151`).

No upstream FLS change is required to ship this. The one downstream cost of Tier 3 is a maintenance fork: if FLS later changes `course_card.html` upstream, this project's shadow will not pick up that change automatically and must be manually re-diffed after `git -C submodules/Freedom-LS pull`. Given how small the diff is (one class on one line), this is a low but non-zero ongoing cost — worth also raising as an upstream FLS issue/PR (fix `course-card-shell.html` + `course_card.html` directly in FLS) so every FLS-based project gets it for free and this project's shadow can eventually be deleted.

## 6. Best practice: equal-height cards with a pinned footer action

Standard flexbox pattern, and what fix (a) implements: card = `flex flex-col` (`h-full` already present here), content-that-can-vary-in-length = normal flow, pinned element = `mt-auto` (equivalently, an earlier `flex-1` spacer). This is documented broadly, e.g. Cruip's ["Stick Elements at the Bottom of Cards with Equal Heights"](https://cruip.com/stick-elements-at-the-bottom-of-cards-with-equal-heights/) and the CSS-Tricks forum thread ["Problem with same height flex boxes with bottom aligned footer"](https://css-tricks.com/forums/topic/problem-with-same-height-flex-boxes-with-bottom-aligned-footer/). CSS Grid `subgrid` is the alternative worth knowing about when siblings need row-for-row alignment (not just a single pinned bottom row) but is unnecessary complexity here since only one row (Details) needs pinning and grids in this app are already status-homogeneous (§2c).

status: ok
