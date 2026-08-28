# Research: what this project can restyle itself, and what must go to FLS upstream

## 1. The theming contract

Source: `submodules/Freedom-LS/docs/how tos/theme-fls.md` (not `docs/theme-fls.md` — that path in the
brief doesn't exist; the file lives under a `how tos/` subdirectory with a space in the name). There
is a second, differently-scoped tier scheme in `submodules/Freedom-LS/docs/product/configuration-and-extension.md`
— see the "two tier schemes" note at the end of this section, it matters for vocabulary only.

FLS's three-tier model (`how tos/theme-fls.md:3-9`):

| Tier | What it changes | Mechanism |
|---|---|---|
| 1 — CSS tokens | Colours, radii, fonts | Redeclare `--color-*` / `--fls-*` custom properties in a theme's `theme.css`, inside `@theme { }`. |
| 2 — Component classes | Button shape/size, chip style, alert colour, surface appearance | Re-open an FLS component class (`.btn`, `.chip`, `.surface`, …) inside `@layer components { }` in the theme's `theme.css`. Because the active theme's `theme.css` is imported *last* in the cascade, its declarations win over the FLS defaults with no `!important` needed (`how tos/theme-fls.md:274`). |
| 3 — Template overrides | Cotton component markup, page-shell blocks, full HTML structure | Escape hatch. Drop a same-path template under a theme's `templates/` dir. |

**What Tier 2 is permitted to change:** only the *declarations inside an existing class selector* —
padding, border, font-weight, radius, colour, box-shadow, etc. — via `@apply` or plain CSS, scoped to
`@layer components`. It is CSS-only. The moment you need to add/remove an HTML element, change which
attributes exist on it, or alter cotton `<c-vars>` — that is Tier 3, not Tier 2. The contract explicitly
draws that line: Tier 2 is "the token values are right but a component's structure needs adjusting"
(`how tos/theme-fls.md:8`) — "structure" here means CSS box-model structure, not DOM structure. The
reference implementation is `freedom_ls/themes/first_class/static/themes/first_class/theme.css`, which
reopens `.btn`, `.btn-secondary`, `.chip`, `.chip-*`, `.surface`, `.course-card`, `.signup-panel`,
`.alert-*`, `.header` (`how tos/theme-fls.md:276`).

**Role tokens available** (all declared in
`submodules/Freedom-LS/freedom_ls/themes/default/static/themes/default/theme.css`, reproduced in
`how tos/theme-fls.md:116-252`):

- Brand: `--color-primary`/`-on-primary`, `--color-secondary`/`-on-secondary`, `--color-accent`/`-on-accent`
- Status: `--color-success|warning|error|info` + `-on-*` pairs, plus `-light` tint variants + their `-on-*-light` pairs
- Surfaces/structural: `--color-surface`, `--color-surface-2`, `--color-on-surface`, `--color-border`, `--color-muted`
- Focus: `--color-focus-ring` — an `@theme inline` **alias** to `--color-primary`, not standalone. Overriding
  `--color-primary` moves the focus ring automatically; a theme wanting a *different* focus colour must
  redeclare `--color-focus-ring` explicitly (`how tos/theme-fls.md:172-182`). This is directly relevant to
  the harsh side-panel focus-outline defect — the fix, if done via tokens, is exactly this token.
- Hover-mix knobs: `--fls-hover-mix-color`, `--fls-hover-mix-amount` (auto-derive `-hover` variants)
- Header/side-panel aliases: `--color-header`, `--color-on-header`, `--color-header-action`,
  `--color-on-header-action`, `--color-sidepanel` (defaults to `--color-surface`)
- Shape: `--fls-radius-sm|md|lg|pill` → aliased to Tailwind's `--radius-*` (`rounded-md` etc.)
- Type: `--fls-font-sans`, `--fls-font-display`, `--fls-font-mono` → `font-sans`/`font-display`/`font-mono`
- Course-card accents: `--fls-course-accent-N-from/-to/-icon` (N=1-5) + optional `-pattern`
- Course-card shape: `--fls-card-radius`, `--fls-card-hero-height`, `--fls-card-padding` — directly
  relevant to the misaligned-card-action defect if the fix is spacing-only.

**Two different "Tier" vocabularies exist in FLS's own docs** — do not conflate them. `how tos/theme-fls.md`'s
Tier 2 = CSS component-class overrides (what this research is about). `docs/product/configuration-and-extension.md:27-35`
uses "Tier 2 — component slots" for a *different* concept (cotton named slots like `eyebrow`/`footer` on
course-card/course-row, filled from a downstream template without forking). Both documents' Tier 3 =
whole-file template shadowing, and they agree on that point. For CSS-only visual defects (padding, focus
ring, alignment), the relevant ladder is the `how tos/theme-fls.md` one: tokens → component classes →
templates.

## 2. The cascade, concretely

`tailwind.input.css` (project root) imports in this order:

```
1  @import "tailwindcss"                                                                    (:1)
2  @import default theme tokens                                                              (:37)
   ./submodules/Freedom-LS/freedom_ls/themes/default/static/themes/default/theme.css
3  @import tailwind.components.css, tailwind.base_interface.css, tailwind.picture_spotlight.css (:42-44)
   (all at the FLS repo root — .btn, .header, .surface, .chip, .alert, .course-card, …)
4  @import first_class theme tokens + Tier-2 overrides                                        (:52)
   ./submodules/Freedom-LS/freedom_ls/themes/first_class/static/themes/first_class/theme.css
5  @theme { /* empty */ }                                                                     (:54-56)
```

**Confirmed, not refuted: `themes/custom/static/themes/custom/theme.css` (this project's own file) is
not imported anywhere in `tailwind.input.css`.** Grepped for the literal string `custom` in that file —
zero matches. The file exists, has a real header comment claiming it "is imported by tailwind.input.css
and compiled into tailwind.output.css" (`themes/custom/static/themes/custom/theme.css:3`), but that
claim is false as the build is currently wired. Every token line in it is also commented out
(`themes/custom/static/themes/custom/theme.css:23-40`), so even if it were imported it would currently
change nothing — but it isn't imported, so editing it right now has **zero effect on the compiled CSS**,
uncommented or not.

This is compounded by a second inconsistency: `README.md:119-125` tells a developer "this project ships
a 'custom' theme at `themes/custom/`... edit token variables... rebuild CSS" as if it's the active,
built theme — but `config/customisation.py:30` sets `FLS_THEME = os.environ.get("FLS_THEME", "first_class")`,
defaulting to `first_class`, not `custom`. So three things disagree right now: the README (implies
`custom` is live), `FLS_THEME`'s default (says `first_class`), and `tailwind.input.css`'s hardcoded
import (also says `first_class`, matching `FLS_THEME` — but not matching the README). The Tailwind
build and the Django runtime theme selection *do* agree with each other (`first_class`); only the
README's narrative is stale/aspirational.

**What it would take to put `custom` in the build**, and what that does to `first_class`'s Tier-2
overrides:

1. Change the `@import` at `tailwind.input.css:52` to point at
   `./themes/custom/static/themes/custom/theme.css` instead of the `first_class` theme.css — or add it
   as a further import *after* the `first_class` import.
2. Set `FLS_THEME=custom` (env var, or change the default in `config/customisation.py:30`) so the
   Django-runtime half agrees with the Tailwind-build half — `configure_theme` in
   `config/settings_base.py:224-229` will otherwise raise `ImproperlyConfigured` at startup looking for
   `themes/custom/` — actually it exists, so it would resolve, but note it currently has no
   `templates/` subdirectory, so no Tier-3 wiring changes; only `STATICFILES_DIRS` gains
   `themes/custom/static/`.
3. Ordering matters for the CSS cascade (`how tos/theme-fls.md:274`): whichever `theme.css` is imported
   **last** wins its `@layer components` declarations, because Tailwind's `@layer` ordering is
   determined by first-appearance of the layer name, but rules *within* the same layer follow normal
   source order, last-wins. If `custom` is imported after `first_class`, `custom`'s Tier-2 rules
   (currently none — its `@layer components` block doesn't exist in the file at all, only a bare
   `@theme` block) would override `first_class`'s Tier-2 `.btn`/`.chip`/`.surface`/etc. But since
   `custom/theme.css` has no `@layer components` block, importing it after `first_class` would only
   affect **Tier-1 tokens** (colours/radii/fonts) — `first_class`'s Tier-2 component-class overrides
   (button padding, chip shape, card radius, etc.) would still stand, because nothing in `custom`
   redeclares those selectors. If `custom` were imported **before** `first_class` instead, it would have
   no effect at all (its tokens would be overridden right back by `first_class`'s own token block).
   Net: enabling `custom` today, without adding a `@layer components` block to it, only lets you retint
   colours/radii/fonts on top of (or instead of) `first_class` — it does not on its own let you fix the
   three CSS-level defects (card alignment, focus outline, button padding) unless `custom` also grows a
   Tier-2 block, at which point it's functionally a fork of `first_class`'s Tier-2 rules with a few
   properties changed.

**Practical implication for this idea:** the three defects are Tier-2/Tier-1 CSS problems inside
`first_class`'s own `theme.css` (imported at `tailwind.input.css:52`) or `tailwind.components.css`
(imported at `:42`). The inert `custom` theme is not a live lever for fixing them today — it would first
need to be wired into the build and given its own `@layer components` overrides, which is strictly more
work than editing `first_class`'s theme.css in place (except that `first_class/theme.css` lives under
`submodules/` and is off-limits per `CLAUDE.md`). This is the crux of the fix-here vs hand-over decision:
see §6.

## 3. Template shadowing

Mechanism, from `config/settings_base.py:142-174` and `submodules/Freedom-LS/spec_dd/3. done/2026-05-30_themable-implementations-master-decomposed-into-phases/research_django_template_overrides.md:8-34`:

- `TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]` (`config/settings_base.py:146`)
- `OPTIONS.loaders` is a `cached.Loader` wrapping, **in order**: `django_cotton.cotton_loader.Loader`,
  `django.template.loaders.filesystem.Loader`, `django.template.loaders.app_directories.Loader`
  (`config/settings_base.py:149-158`).
- `filesystem.Loader` searches `TEMPLATES[0]["DIRS"]` (a flat list) in order, first match wins.
  `app_directories.Loader` then searches each `INSTALLED_APPS` entry's own `templates/` subdirectory,
  in `INSTALLED_APPS` order, first match wins — but it only runs if `filesystem.Loader` found nothing.
- `configure_theme()` (`config/settings_base.py:224-229`) **prepends** the active theme's
  `<theme>/templates/` directory to `TEMPLATES[0]["DIRS"]`, if that directory exists
  (`how tos/theme-fls.md:78`). `first_class` currently ships no `templates/` dir
  (`how tos/theme-fls.md:404`), so nothing is prepended today.

Resolution order today, most-specific first: **active theme's `templates/` (none currently) → project's
`BASE_DIR/templates/` → FLS apps' own `templates/` dirs, in `INSTALLED_APPS` order** (`cotton_loader.Loader`
delegates the actual file lookup to this same chain — it isn't a separate search path, it just
translates `<c-button>` into a lookup for `cotton/button.html` and hands that name to the same loader
chain, confirmed by `research_django_template_overrides.md:60`).

**Yes, this project can shadow a cotton component.** `filesystem.Loader` runs before
`app_directories.Loader`, and `BASE_DIR/templates` is in `DIRS`. A file at
`templates/cotton/button.html` (project root) is found before FLS's own
`freedom_ls/*/templates/cotton/button.html` — same mechanism, same priority, as the one existing example
(app-partial override, not cotton, but identical resolution path):
`templates/learner_interface/partials/anonymous_hero.html`, which shadows FLS's default hero at the same
relative path.

**Yes, this project can also shadow a theme-level template** — but only by placing the override at
`themes/first_class/templates/...` *inside the submodule* (forbidden by `CLAUDE.md`), or by pointing
`FLS_THEMES_DIRS` at a project-owned theme directory of the same slug (`config/settings_base.py:34-36`:
"a downstream project can shadow the FLS-package defaults by dropping a theme at
`BASE_DIR / "themes" / <slug> /`" — i.e. `themes/first_class/templates/...` at the project root, NOT
under `submodules/`). Since `FLS_THEMES_DIRS = [BASE_DIR / "themes", FREEDOM_LS_PACKAGE_DIR / "themes"]`
and the project's own `themes/` dir is searched **first**, a project-root `themes/first_class/templates/`
would win over the submodule's `first_class` theme templates without touching `submodules/` at all. This
project doesn't currently have a `themes/first_class/` directory (only `themes/custom/` exists) — so
today, theme-level template shadowing for `first_class` isn't wired, but the settings already support it
if a `themes/first_class/templates/cotton/button.html` were added at the project root.

Practically, for this idea: **project-root `templates/cotton/*.html` and project-root
`themes/first_class/templates/cotton/*.html` are functionally equivalent escape hatches** — both resolve
before the submodule's version, both require zero edits under `submodules/`. The `templates/` path is
simpler (no theme-slug indirection); the `themes/first_class/templates/` path is more semantically
"this is theme code" and travels with a theme rename automatically if `FLS_THEME` is later changed. Given
this project's existing pattern (`anonymous_hero.html` lives directly under `templates/`, not under a
theme dir), `templates/cotton/...` is the path of least surprise here.

## 4. The cost of shadowing

No FLS doc frames this as "shadowing = fork" in those words, but the mechanics say so, and one line makes
it explicit: "Removing a prop or changing a default is a breaking change — callers that rely on the
original signature will silently break" (`how tos/theme-fls.md:314`) — that's about *theme* overrides
breaking *callers*, but the same risk runs the other direction: once you shadow `cotton/button.html`,
you no longer see FLS's own edits to that file. An upstream fix, prop addition, accessibility patch, or
security fix to `cotton/button.html` lands in `submodules/Freedom-LS` on the next `git submodule update`
— but your shadow at `templates/cotton/button.html` keeps rendering the old markup, silently, forever,
until someone notices the divergence and manually re-applies the upstream change. There is no lint, no
test, no CI signal that a shadow has drifted from its source — `how tos/theme-fls.md` documents the
override mechanism in detail but nothing about detecting staleness.

`docs/product/configuration-and-extension.md:35` calls whole-file shadowing "Tier 3 ... Use this when
tiers 1 and 2 are not enough" — an explicit statement that it's the last resort, not a first move.
`README.md` has no guidance on the maintenance cost; `CLAUDE.md` only says the submodule itself is
read-only, it doesn't discuss overrides in the project's own tree at all.

**When it's worth paying:** the defect is genuinely presentational/local (branding, copy, spacing that
only this project cares about) and Tier 1/2 tokens can't reach it because it needs different markup
(new wrapper element, different attribute, a slot FLS doesn't expose) — i.e. true Tier-3 territory,
not a Tier-1/2 problem being reached for the wrong tool. **When it's not worth it:** the defect is a bug
in FLS's shared markup/CSS that every FLS consumer using that component would also hit — shadowing there
just moves the bug into your own permanently-diverging copy instead of fixing it once upstream. See §6.

## 5. The hand-over precedent

`spec_dd/for_freedom_ls/` currently has 20 directories (not ~22 — recount: `site-resolution-native-callers-500`,
`quiz-partial-attempt-resume-lost-answers`, `quiz-free-text-scoring-and-answer-echo`,
`survey-form-reuses-quiz-copy`, `deadline-lock-silent-redirect-no-message`,
`course-parts-part-status-locked-badge`, `deadline-tooltip-leaks-internal-override-phrasing`,
`discovery-pages-jsonld-structured-data`, `dashboard-next-up-missing-for-course-parts`,
`qa-registration-completion-scenario-command`, `admin-question-answer-selected-options-widget`,
`upgrade-notes-name-a-storage-class-that-does-not-exist`, `root-env-example-stale-after-prod-bucket-setup`,
`panel-framework-tests-reverse-a-url-they-isolate-away`, `anonymous-hero-test-asserts-fls-brand-copy`,
`asgi-and-wsgi-name-a-settings-module-that-does-not-exist`, `settings-base-template-dirs-points-at-a-scratch-path`,
`admin-app-sections-show-raw-app-labels`, `site-signup-policy-pluralises-as-policys`, `prepare-to-deploy`),
each with exactly one `idea.md`.

**House format** (consistent across all four read in full):

```markdown
# Idea: <one-line, specific defect description, often naming the symptom and its scope>

## The bug
Source: <where this was found — a QA report, a test run, an upgrade audit, a specific command>
<Narrative description of the observed defect, with concrete repro evidence: file:line references,
 actual error output/traceback pasted verbatim, or a described UI symptom. States *why* it's wrong,
 not just *that* it's wrong — usually ties back to a design intent FLS itself documents.>

## Expected fix
<Prescriptive, concrete fix — often naming the exact setting/line to change, sometimes offering an
 alternative ("if the intent is X instead, do Y"). Not a vague "investigate this" — it tells FLS
 maintainers what to do, citing existing FLS conventions/tests/skills as justification.>

[optional] ## Open question
<Used when the fix has a genuine design fork FLS maintainers need to decide, e.g. whether an admin
 field should become read-only rather than merely better-scoped.>

## Sources
- `path` — line numbers, for every file mentioned above
```

Notably:
- The defect is always attributed to a **specific file:line inside `submodules/Freedom-LS`**, or to a
  test/command/report that names one. Every one of the four read cites `submodules/Freedom-LS/...` paths
  with line numbers under "Sources".
- Prescriptiveness is high — these read as ready-to-implement patches, not open research questions. The
  `settings-base-template-dirs-...` one literally shows the two-line diff needed.
  The `admin-question-answer-...` one names the exact Django admin API (`autocomplete_fields`,
  `formfield_for_manytomany`) to use.
- When the project's own code is relevant as a *correct counter-example* (proving the downstream did the
  right thing and FLS is still wrong), the idea cites the project's own file too, as corroboration, not as
  the target of the fix — e.g. `anonymous-hero-test-asserts-fls-brand-copy/idea.md` cites this project's
  `templates/learner_interface/partials/anonymous_hero.html` as evidence the override mechanism works
  correctly and the test is what's wrong.
- Every idea is one defect, one file, atomic — no bundling of multiple unrelated issues into one hand-over
  (unlike this project's own `spec_dd/1. next/visual-polish/idea.md`, which currently bundles three).

**None of the 20 existing hand-overs cover button/card/focus/spacing/padding/outline styling.** Grepped
all 20 `idea.md` files case-insensitively for `button|focus|card|padding|outline`; only two incidental,
unrelated hits: `dashboard-next-up-missing-for-course-parts` (mentions "course cards" as the *location* of
a missing next-up hint, not a styling defect) and `quiz-partial-attempt-resume-lost-answers` (unrelated).
No existing hand-over addresses the `.btn` padding, `.course-card` action alignment, or focus-ring
styling that this idea's three defects concern — this would be new territory for `for_freedom_ls/`.

## 6. A decision rule

Grounded in §§1-5:

1. **Fix here** if the defect is purely CSS (colour/radius/spacing/typography on an existing selector)
   *and* is specific to this project's brand/layout choice rather than a defect in FLS's own shipped
   values — i.e. a genuine Tier-1/Tier-2 override case. Implementation path: edit
   `first_class/theme.css`'s Tier-2 block, but that file is **under `submodules/`, so it cannot be
   edited here either** — meaning for *this* project, "fix here" in practice only works for defects
   reachable from files this project owns: `themes/custom/theme.css` (once wired into the build per §2),
   a project-root `templates/cotton/*.html` shadow (§3), or `templates/` app-template overrides. If the
   only fix location is inside `submodules/Freedom-LS/freedom_ls/themes/first_class/...`, it is **not**
   fix-here by definition of `CLAUDE.md`'s submodule rule, regardless of how small the CSS change is.

2. **Hand over to FLS** if the defect lives in a file under `submodules/` (as all three of this idea's
   defects do, per the idea's own framing) **and** a local workaround would require either (a) shadowing
   a cotton template just to change padding/alignment (Tier-3 sledgehammer for a Tier-1/2 problem — the
   `how tos/theme-fls.md` tier ladder explicitly discourages this), or (b) is a bug that isn't
   brand-specific — every FLS consumer running `first_class` (or the affected component regardless of
   theme) would hit the same misalignment/harsh-focus/cramped-padding, meaning it's a defect in FLS's
   shared CSS, not a missing per-project override.

3. **Middle case — technically patchable downstream, but really an upstream bug every consumer shares:**
   hand over to FLS (so the fix lands for every FLS-powered project, not just this one), **and** consider
   a local Tier-2 stopgap only if:
   - the visual defect is user-visible and embarrassing enough that shipping now matters more than
     waiting for the next `submodules/Freedom-LS` pull, **and**
   - the stopgap is a genuine Tier-2 override (re-open the class in a project-owned `theme.css`, e.g.
     `themes/custom/theme.css` once wired per §2), never a Tier-3 template shadow, **and**
   - the hand-over idea explicitly says a local stopgap exists, so a future maintainer removes it once
     the upstream fix lands (otherwise the stopgap silently survives the submodule update and possibly
     fights the corrected upstream CSS — a second, self-inflicted divergence on top of the one in §4).
   Given `themes/custom` is currently inert (§2) and would need build-wiring work to use as a stopgap
   vehicle, the pragmatic call per defect is: hand over always; only add the stopgap if the defect is bad
   enough to justify first wiring `custom` into the build (a one-time cost paid once, benefiting all
   three defects and any future ones).

For this idea's three defects specifically (misaligned card action, harsh focus outline, cramped button
padding): all three originate in files under `submodules/Freedom-LS` per the idea's own framing, and none
of them read as this-project-only branding choices (a `.course-card` action alignment bug and a default
focus-ring harshness are structural CSS issues any `first_class`-themed FLS consumer would share, per
rule 2b above) — so by this rule they default to **hand-over**, in the shape documented in §5, one
`idea.md` per defect under `spec_dd/for_freedom_ls/`. Whether any warrants a local Tier-2 stopgap in
`themes/custom/theme.css` (once wired) is a per-defect severity call the other three research files in
this folder are better placed to make, now that the general mechanism and its cost are established here.

status: ok
