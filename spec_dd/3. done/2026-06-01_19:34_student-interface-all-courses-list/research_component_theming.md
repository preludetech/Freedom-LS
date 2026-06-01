# Research: Theming/overriding the course-card components

Goal: let downstream/concrete FLS implementations easily restyle the **LOOK** of
course cards while the **behaviour** (registration logic, modal vs deep-link,
progress, completion semantics, accessibility) stays put. This is input for a
high-level idea doc, not a full spec.

The big idea from every source below is the same: **separate structure from
skin.** Keep a thin structural skeleton, push all colour/shape/type decisions
into design tokens, and expose a small number of named slots for content
swapping. Avoid baking presentation into deeply nested conditional templates.

---

## 1. How FLS makes cards themeable TODAY

There are already three override layers in place, which is good. They map
cleanly onto the three industry mechanisms (tokens / slots / template override).

### a. Theme tokens (the skin layer) — strong
- `freedom_ls/themes/default/static/themes/default/theme.css` defines role
  tokens (`--color-primary`, `--color-surface`, `--color-muted`,
  `--color-success-soft`, …) plus a **dedicated card palette**
  `--fls-course-accent-{1..5}-from/-to/-icon`, with `-gradient`/`-soft`
  composites auto-derived via `color-mix()` (lines 86-102).
- `first_class/theme.css` shows the intended override path: it redeclares only
  the **values** (`--fls-course-accent-*-from/-to/-icon`, radii, fonts) and
  inherits the composite/`-soft` recipes. This is exactly the Tailwind v4
  "override the token, not the markup" pattern (see §2 web refs).
- The card never references a raw hex or a Tailwind palette colour. The hero
  tile and progress bar resolve through `.course-accent-N` / `.course-progress-N`
  classes in `tailwind.components.css:267-293`, which read the `--fls-course-accent-*`
  vars. So **a theme can fully recolour cards by editing one CSS file** — no
  template edits. This is the system's best feature; keep it.

### b. Cotton shell + slot (the structure layer) — partial
- `cotton/course-card-shell.html` is the shared skeleton: `<article>` wrapper +
  accent hero (`.course-accent-{{ accent_slot_key }}`) + centred icon +
  `{{ slot }}` body. Variants pass body content through the default slot.
- Good: one place owns the card frame, hover/focus affordances, and the
  stretched-link `relative` context.

### c. Icon indirection — good
- `{% course_icon %}` (`templatetags/course_icon_tags.py` →
  `student_interface/course_icon.py`) encapsulates icon resolution; templates
  never branch on icon-name shape. A theme/impl can change the glyph colour per
  accent slot via `--fls-course-accent-N-icon`.

### d. Template override (the whole-file layer) — available but undocumented
- `tailwind.input.css` already globs `freedom_ls/themes/*/templates/**/*.html`
  ("Tier 3" overrides), and Django's loader lets a downstream project shadow any
  packaged template by path. So overriding `course_card.html` wholesale is
  possible, just not written down (`docs/how tos/incorperate into another
  project.md` leaves urls/settings as TODO).

---

## 2. Where the card templates are over-complicated for overriding

The skin layer is clean; the **structural/content templates are not.** Specific
problems:

1. **`course_card.html` mixes three concerns in one file** (read of
   `partials/course_card.html`): registration branching (`is_registered`),
   responsive **behaviour** branching (desktop modal vs mobile deep-link, lines
   60-106), and **presentation** (eyebrow text, progress bar markup, headings).
   A downstream that just wants the not-started card to *look* different must
   copy the whole file — including the modal/Alpine wiring it does not want to
   touch. Structure and skin are entangled.

2. **Duplicated presentation across variants.** The eyebrow `<p>` ("In
   progress" / "Not started" / "Completed"), the stretched-link `<h3><a …
   before:absolute before:inset-0 …>` pattern, and the title block are
   re-typed in `course_card.html` (3×) and again in `course_card_complete.html`.
   The exact utility string `text-inherit no-underline before:absolute
   before:inset-0 before:content-[''] focus:outline-none` appears 3 times. Any
   restyle of "the card title link" is a 3-file, 4-site edit.

3. **Hard-coded utility classes inside the shared shell block overriding.**
   `course-card-shell.html:12` hard-codes radius (`rounded-2xl`), hero height
   (`h-28`), padding (`p-0`/`p-4`), and the full hover/focus recipe inline.
   These are not token-driven, so a theme that wants squarer cards or a taller
   hero must override the whole component file rather than flip a token —
   even though radius tokens (`--fls-radius-lg`, etc.) already exist and
   `first_class` already themes radius elsewhere. Per the headless-UI refs
   (§"Avoiding hardcoded classes"), structural skeletons should lean on tokens
   for the dimensions a theme is likely to change.

4. **Two dispatch seams that both branch.** `course_list.html` `dispatch-card`
   splits `history` vs everything else, then `course_card.html` *re-branches* on
   `is_registered`. The completed card is a separate file; the registered /
   not-registered cards are two arms of one file. Inconsistent: a downstream
   can't reason about "one card = one file."

5. **`accent_slot_key` interpolated into class names** (`course-accent-{{ key }}`,
   `course-progress-{{ key }}`). It works because the 5 classes are hand-authored
   (no safelist needed, noted in CSS), but it means the **count of accent slots
   is baked into CSS** and a theme can only recolour the existing 5, not change
   how many there are. Acceptable, but worth noting as a coupling point.

6. **Light data/presentation mixing in the template.** `course_card.html:25`
   decides "In progress vs Not started" from `progress_percentage > 0` in the
   template. Minor, but it's a presentational label derived from data inline;
   pushing the eyebrow label to the view/context object would let a theme
   restyle without re-deriving logic.

---

## 3. Best-practice patterns (web-sourced) and how each maps to FLS

### Pattern A — Override the SKIN via theme tokens (cheapest; prefer this)
Tailwind v4 `@theme` exposes every token as a `:root` CSS var, so a downstream
stylesheet re-skins components by **redeclaring token values only** — no markup
touched. You can override one token, a whole namespace (`--color-*: initial`),
or reference tokens with `@theme inline` to avoid var-resolution failures.
([Tailwind theme docs](https://tailwindcss.com/docs/theme),
[Tailwind v4 blog](https://tailwindcss.com/blog/tailwindcss-v4))

> FLS already does this well for **colour**. The gap is **shape/spacing**: hero
> height, card radius, hero/body padding are hard-coded utilities, not tokens.

Design-token guidance also recommends a 3-tier structure — **base → semantic →
component** tokens — so component tokens (e.g. a `--fls-card-radius`) can be
retuned without disturbing the brand palette.
([Mavik Labs](https://www.maviklabs.com/blog/design-tokens-tailwind-v4-2026/),
[MatchKit](https://www.matchkit.io/blog/design-tokens-tailwind-v4))

### Pattern B — Override via cotton slots / vars (medium cost)
django-cotton gives three knobs: the default `{{ slot }}`, **named slots**
(`<c-slot name="…">`), `<c-vars>` defaults, plus `{{ attrs }}` pass-through and a
mergeable `class` attribute. Keys declared in `<c-vars>` are stripped from
`{{ attrs }}`, so config (variant flags) and pass-through HTML attributes stay
cleanly separated. Consumers restyle by **passing classes / swapping slot
content**, never by editing logic.
([django-cotton components](https://django-cotton.com/docs/components),
[usage patterns](https://django-cotton.com/docs/usage-patterns))

> FLS uses only the default slot today. Adding a couple of **named slots**
> (e.g. `eyebrow`, `media`/hero, `body`/`footer`) to the shell would let an impl
> reshape card content without forking the registration logic. Letting the
> shell accept a `class` override (merged onto the `<article>`) covers most
> shape tweaks that aren't worth a token.

### Pattern C — Override the WHOLE template file (escape hatch; last resort)
Django's loader resolves `DIRS` before `APP_DIRS`, and `APP_DIRS` walks
`INSTALLED_APPS` in order — so a downstream project drops a same-path template
to shadow the packaged one. Reusable-app guidance: **namespace templates**
(already done: `student_interface/partials/…`) and treat project templates as
the authoritative override.
([Django: overriding templates](https://docs.djangoproject.com/en/6.0/howto/overriding-templates/))

> Works in FLS via the `themes/*/templates` glob + loader order. The smaller and
> more single-purpose each card file is, the less an overrider has to copy. This
> is the strongest argument for splitting structure from skin (§2.1).

### Pattern D — Separation of structure vs skin (headless UI)
"Headless / skinless" components separate the skeleton + logic from styling;
consumers style slots and tokens, the component owns behaviour. Pitfalls called
out: **over-abstraction / too much indirection** hurting readability, and
**hard-coded utility classes** blocking restyles. The sweet spot is a *minimal*
structural skeleton + a token-driven skin layer — not a parameter explosion.
([nerdy.dev: headless/boneless/skinless](https://nerdy.dev/headless-boneless-and-skinless-ui),
[Martin Fowler: headless component](https://martinfowler.com/articles/headless-component.html),
[Headless UI](https://headlessui.com/))

> Caution for FLS: don't "fix" the cards by adding 15 `<c-vars>` params. That
> trades one over-complication (nested conditionals) for another
> (parameter soup). Favour slots + tokens over a wide prop surface.

---

## 4. Recommendations for this project

Ordered by value/effort. All keep behaviour fixed.

1. **Tokenise the card's shape/dimension constants (Pattern A).** Introduce
   component-tier tokens used by the shell — e.g. `--fls-card-radius`,
   `--fls-card-hero-height`, `--fls-card-padding` — aliased so the shell uses
   them (via a `.course-card` component class in `tailwind.components.css`, like
   `.surface`/`.btn` already do). Default them to today's values
   (`rounded-2xl`, `h-28`, `p-4`). Then a theme reshapes cards by overriding
   tokens, matching the existing colour-token story. Lowest-risk, highest-leverage.

2. **Extract the repeated content bits into the shell or small partials
   (kills §2.2 duplication).** The stretched-link title (`<h3><a … before:inset-0
   …>`) and the eyebrow `<p>` are identical across all three variants. Move them
   into the shell as **named slots** (`eyebrow`, `title`/`title_url`) or a tiny
   `card-title-link` partial. One definition of "card title link" → restyle once.

3. **Add named slots to `course-card-shell.html` (Pattern B).** At minimum
   `eyebrow` and `footer` (badge/progress) alongside the existing body slot, and
   allow a `class` override merged onto the `<article>`. This lets an impl
   restyle/recompose card content **without touching** the registration or
   modal logic — the entanglement that currently forces a full-file copy.

4. **Make "one card state = one file," behaviour-only branching at the seam.**
   Consider lifting the `is_registered` split out of `course_card.html` up into
   the `dispatch-card` seam in `course_list.html`, so each leaf template
   (registered / not-registered / completed) is a thin, single-purpose,
   easily-overridable file. Keep the desktop-modal vs mobile-deep-link as the
   *only* internal branch in the not-registered card (it's behaviour, not skin).

5. **Keep the accent palette exactly as-is.** The `--fls-course-accent-*` +
   `color-mix` derivation is the model the rest of the card should follow. Don't
   regress it.

6. **Resist a `<c-vars>` parameter explosion (Pattern D pitfall).** Prefer
   tokens (shape/colour) + a few named slots (content) over many boolean/string
   props. Document the three override tiers so downstream knows which lever to
   pull: **token → slot/class → whole-file**.

7. **Write down the override story.** `docs/how tos/incorperate into another
   project.md` should state: re-skin via theme tokens first; recompose via cotton
   slots/class second; shadow the template file only as a last resort.

---

## Sources
- django-cotton — [Components](https://django-cotton.com/docs/components), [Usage patterns](https://django-cotton.com/docs/usage-patterns)
- Tailwind CSS v4 — [Theme variables](https://tailwindcss.com/docs/theme), [v4 announcement](https://tailwindcss.com/blog/tailwindcss-v4), [Adding custom styles](https://tailwindcss.com/docs/adding-custom-styles)
- Design tokens — [Mavik Labs](https://www.maviklabs.com/blog/design-tokens-tailwind-v4-2026/), [MatchKit](https://www.matchkit.io/blog/design-tokens-tailwind-v4)
- Django — [Overriding templates](https://docs.djangoproject.com/en/6.0/howto/overriding-templates/)
- Headless/skinless UI — [nerdy.dev](https://nerdy.dev/headless-boneless-and-skinless-ui), [Martin Fowler](https://martinfowler.com/articles/headless-component.html), [Headless UI](https://headlessui.com/), [MUI Base](https://mui.com/blog/introducing-base-ui/)
