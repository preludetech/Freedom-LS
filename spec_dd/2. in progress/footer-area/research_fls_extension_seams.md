# Research: how FLS already advertises template extension seams

Goal: establish the exact pattern the `{% block footer %}` / `partials/footer.html` seam must
match, using the `{% block header %}` / `partials/header_bar.html` seam as the precedent, and
surface anything that would make the footer seam behave differently.

## 1. The `header_bar.html` seam, in full

`freedom_ls/base/templates/_base.html:99-102`:

```
{% block header %}
    {% include "partials/header_bar.html" %}

{% endblock header %}
```

Note the block name (`header`) and the included partial's filename (`header_bar.html`) already
differ — the block names the landmark, the partial's filename can be more specific. That is the
precedent a `{% block footer %}` / `partials/footer.html` pair follows exactly: same relationship,
generic block name, specifically-named partial.

**`freedom_ls/base/templates/partials/header_bar.html`** — the partial itself:

- Root element is a semantic landmark tag (`<header class="header" ...>`), not a `<div>`. A footer
  partial should root on `<footer>`.
- Uses Alpine via `x-data="headerScroll"` / `x-bind:data-scrolled="scrolled"` for its own local
  behaviour (a JS-driven scroll state) — this is chrome-specific and not something a footer needs
  to copy, but establishes that a chrome partial is free to carry its own `x-data`.
  `{% load static %}` at the top is only needed because of the logo `<img>`.
- Branches on `user.is_authenticated` and includes a further partial for each case:
  `partials/header_bar_user_menu.html` (authenticated) vs `partials/login_prompt.html`
  (anonymous). A footer partial that needs to differ by auth state should follow the same
  branch-and-include shape rather than inlining both cases.
- No `id` or `data-testid` hook on the `<header>` element itself. `header_bar_user_menu.html` and
  `login_prompt.html` also carry none (they use `c-button`, `c-dropdown-menu`, `c-icon` for their
  interactive surface instead). **This is the load-bearing convention for the footer partial**:
  FLS's own chrome partials do not pre-emptively wire test hooks; hooks appear only where a
  concrete need exists (see §6 on the conformance suite / structural-hooks table, which is a
  different, opt-in mechanism, not something `header_bar.html` itself does).
- Tailwind role tokens used: `text-on-header` (header title), and (in
  `header_bar_user_menu.html`) `bg-header-action` / `text-on-header-action` for the avatar chip.
  These are the `--color-header*` component-tier tokens documented in
  `docs/how tos/theme-fls.md` ("Header and side-panel component-tier tokens", lines 218-230). A
  footer partial has no equivalent `--color-footer*` token today — see the Tailwind-tokens gap
  noted in §3(d) below.
- Cotton usage: `header_bar_user_menu.html` is built entirely from cotton components
  (`<c-dropdown-menu>`, `<c-slot name="trigger">`, `<c-button>`, `<c-icon>`), and
  `login_prompt.html` uses `<c-button>`. **A new `partials/footer.html` should reach for cotton
  primitives (`c-button`, `c-icon`, etc.) for any interactive element, rather than hand-rolling
  markup**, matching this precedent.
- `partials/messages.html` (included separately at `_base.html:104`, immediately after the header
  block, not inside it) is the toast/message partial — not part of the header seam, but shows the
  same "small, focused partial with its own doc comment" convention. Its long `{% comment %}` block
  at the top (documenting render modes and severity routing) is the house style for a non-trivial
  partial; a footer partial with any conditional behaviour should carry the same kind of comment.
- `partials/page_title.html` shows the same convention again: a one-paragraph `{% comment %}`
  explaining *why* the wrapper exists (stable `id="page-title"` for HTMX OOB-swaps) before the
  markup. It also shows the pattern for an `oob=True` include kwarg used only by one caller
  (`_base_interface.html`) — not needed by the footer, but confirms the house convention of an
  `{% if oob %}` include-time flag rather than a separate template.

**Conventions a new `partials/footer.html` must follow, stated concretely:**

1. Root on the matching semantic tag: `<footer ...>`.
2. Keep the include one line inside the block, exactly like `{% include "partials/header_bar.html" %}` — no logic in `_base.html` itself.
3. No hardcoded `id`/`data-testid` on the root by default; only add one if a concrete consumer of the seam (a test, an HTMX OOB target) needs it — matching `header_bar.html`'s lack of one.
4. Use cotton components (`c-button`, `c-icon`, etc.) for any interactive content rather than raw `<a>`/`<button>` markup.
5. Any conditional rendering (e.g. differing by auth state, by site config) should branch with `{% if %}` and delegate to a further partial per branch, the way `header_bar.html` delegates to `header_bar_user_menu.html` / `login_prompt.html`, rather than inlining both cases in one file.
6. If the partial renders nothing today (per `from_concrete_implementation.md`'s recommendation), it should still carry the `{% comment %}` doc-header convention seen in `messages.html` / `page_title.html` explaining why it is a deliberate no-op, so a downstream project understands it is a seam and not dead code.

## 2. Who overrides `{% block header %}` today

Grepped `block header` across `freedom_ls/`:

| File | What it does |
|---|---|
| `freedom_ls/base/templates/_base.html:99` | Defines the block, includes `partials/header_bar.html`. |
| `freedom_ls/learner_interface/templates/learner_interface/_exam_runner_base.html:29-31` | Blanks it: `{% block header %}{% comment %}runner owns its own bar{% endcomment %}{% endblock header %}` |
| `freedom_ls/panel_framework/tests/templates/panel_framework/test_interface.html:18` | `{% block header %}{% endblock header %}` — a test fixture template, blanks it with no comment (not production precedent, just confirms the pattern of an empty override is syntactically normal). |
| `freedom_ls/base/templates/_base_interface.html` | Does **not** override `{% block header %}` at all — it only overrides `{% block body %}` (which sits *inside* `<main>`) and adds its own `{% block header_extra %}` (`_base_interface.html:233-234`) as a sub-block inside its sidebar layout. So `_base_interface.html` descendants (course-topic pages, the educator interface) still render `partials/header_bar.html` from `_base.html` unmodified. |

**Precedent for the footer's equivalent suppression:** `_exam_runner_base.html` is the one real
(non-test) example of a shell suppressing inherited chrome, and it does it with a one-line blank
override plus a one-line `{% comment %}` stating *why* ("runner owns its own bar"). The
`from_concrete_implementation.md` idea note (§3) proposes the same treatment for footer on the
runner base, since `course_form_page.html` already has its own "STICKY FOOTER" region
(`course_form_page.html:315-458`, confirmed by grep) that would visually collide with a global
site footer. That mirrors this precedent exactly.

`_base_interface.html` does **not** suppress `{% block header %}`, so by the same logic it will
**not** automatically suppress `{% block footer %}` either — a footer placed after `</main>` in
`_base.html` renders for every `_base_interface.html` descendant unless `_base_interface.html` is
given its own `{% block footer %}` override. `from_concrete_implementation.md` §4 flags this as
"the real decision" FLS has to make (full-bleed footer under the docked sidebar layout,
`_base_interface.html:126-131` for the sticky sidebar geometry) — confirmed still open, no
existing override resolves it.

## 3. The three-tier theming contract and template-resolution order

### Verified resolution order

`config/settings_base.py`:
- `TEMPLATES[0]["DIRS"]` starts as `[]` (line 176) in the FLS repo's own settings — `APP_DIRS` is
  commented out (line 177) but the loader list explicitly includes
  `django.template.loaders.app_directories.Loader` (line 185) alongside
  `django_cotton.cotton_loader.Loader` and `filesystem.Loader`, wrapped in a `cached.Loader`
  (lines 179-188).
- `RESOLVED_THEME_DIR = configure_theme(theme_slug=FLS_THEME, themes_dirs=FLS_THEMES_DIRS, templates=TEMPLATES, staticfiles_dirs=STATICFILES_DIRS)` (lines 254-259) runs **after** `TEMPLATES` is defined and **prepends** the resolved theme's `<theme>/templates/` to `TEMPLATES[0]["DIRS"]` if that directory exists (`docs/how tos/theme-fls.md:80`).
- `FLS_THEMES_DIRS = [BASE_DIR / "themes", FREEDOM_LS_PACKAGE_DIR / "themes"]` (`settings_base.py:53-56`) — `configure_theme` walks this list in order and uses the **first** directory containing a `<slug>/` subdirectory, so a project-root `themes/<slug>/` shadows the FLS-package theme of the same slug (`theme-fls.md:76`).

Per `from_concrete_implementation.md:27`, in a downstream/concrete project `BASE_DIR / "templates"`
is placed **first** in `TEMPLATES["DIRS"]`, ahead of `configure_theme`'s prepend and ahead of the
app-directories loader (cited there as `config/settings_base.py:164-166` of that concrete project,
not this FLS repo). This research unit did not have that concrete project's settings file to
re-verify directly, but it is consistent with the documented "Custom-App Extension Model" contract
in `docs/product/configuration-and-extension.md:88`: *"The host project's template directories are
searched first, so any FLS template can be replaced by providing a file at the same path."*

**So the full resolution order, most-specific first, is:**

1. Downstream/host project's own `templates/` dir (e.g. `BASE_DIR / "templates"`) — set by the
   host project itself, not by FLS.
2. The active theme's `<theme>/templates/` dir, if it exists — prepended by `configure_theme`
   (`freedom_ls/base/theming.py`, invoked at `settings_base.py:254`).
3. FLS app directories, via `app_directories.Loader` (each app's own `templates/` subfolder, e.g.
   `freedom_ls/base/templates/`).

**Two distinct override paths, and which wins:** a downstream project can override
`partials/footer.html` either (a) at the project level, `templates/partials/footer.html`, or (b)
at the theme level, `themes/<slug>/templates/partials/footer.html`. Tier order above means
**project-level (path 1) wins over theme-level (path 2)** if both exist — the host project's own
`templates/` dir is searched first. This is the same choice already documented for cotton
components in `theme-fls.md`'s Tier-3 section (lines 278-352): "Tier 3 — Template overrides" covers
both cotton-component overrides and "App template or partial override" at the same relative path
(`theme-fls.md:316-324`), and `partials/footer.html` is squarely an "app template or partial
override" (it lives under `freedom_ls/base/templates/partials/`, owned by the `base` app), not a
cotton component.

### (d) Gap noted while researching this

The Tier-1 token reference in `theme-fls.md` (lines 218-230) documents `--color-header`,
`--color-on-header`, `--color-header-action`, `--color-on-header-action`, `--color-sidepanel` as
the header/side-panel component-tier tokens. **There is no equivalent `--color-footer*` token
today.** If the shipped `partials/footer.html` is meant to carry any background styling of its
own (rather than being purely a downstream-filled empty slot), a parallel `--color-footer` /
`--color-on-footer` alias pair (defaulting to a brand or surface token, the way
`--color-header` defaults to `--color-primary`) would need adding to
`freedom_ls/themes/default/static/themes/default/theme.css` and documenting alongside the header
tokens in `theme-fls.md`. If the shipped partial stays an empty/near-empty seam (per
`from_concrete_implementation.md:17`'s "rendering nothing is the safer default"), this gap can be
deferred — but it should be a conscious decision, not a silent omission.

## 4. The theme-directory caveat — verified

`Glob` of `freedom_ls/themes/**` returns exactly:

```
freedom_ls/themes/default/theme.md
freedom_ls/themes/default/static/themes/default/theme.css
freedom_ls/themes/first_class/theme.md
freedom_ls/themes/first_class/static/themes/first_class/theme.css
```

**Neither shipped theme has a `templates/` directory.** `theme-fls.md:428` states this explicitly
for `first_class`: *"It has no `templates/` directory — Tier-3 overrides are not required and the
theme works fully without them."* The same is true of `default` (confirmed by the glob above — no
`templates/` entry under either theme).

This **confirms** the `from_concrete_implementation.md:29` claim rather than merely being
consistent with it: today, in the FLS repo itself, there is no `templates/` directory to shadow
under either theme, so the theme-level override path (path 2 in §3) is currently a documented
mechanism with **zero shipped examples exercising it** (also stated at `theme-fls.md:286`: *"No
shipped FLS theme uses Tier 3 today; the mechanism is the override path, not a shipping
example."*).

The specific claim that matters for this feature — *when FLS is installed as a read-only
submodule, `themes/<slug>/templates/` inside the submodule is not a usable override seam for the
installing project, because writing into it means writing into a git submodule you do not own* —
is not a claim this repo (which *is* FLS itself, not a downstream consumer) can directly falsify
or confirm from its own file tree. But `configure_theme`'s resolution order (§3) makes the
downstream project's real options explicit: it can either (a) create its **own**
`themes/<slug>/templates/partials/footer.html` in `BASE_DIR / "themes"` (which shadows the
FLS-package theme directory per `FLS_THEMES_DIRS` ordering, `settings_base.py:53-56`, and does
**not** require writing into the submodule) or (b) use the project-level
`templates/partials/footer.html` seam. Both are legitimate, submodule-safe paths — the concrete
project's choice of (b) in `from_concrete_implementation.md` is a preference (simpler, one file,
no theme-directory ceremony for a chrome partial that isn't tied to theme identity), not a
technical necessity forced by the submodule. Recommend documenting **both** paths, with
project-level as the recommended default, rather than asserting the theme path is unusable.

## 5. Tailwind's `@source` globs — the trap, confirmed live

`tailwind.input.css` (FLS repo root), grepped for `@source`/`@import`:

```
10: @source "./freedom_ls/**/templates/**/*.html";
12: @source "./freedom_ls/themes/*/templates/**/*.html";
```

These cover FLS's own app templates and FLS's own theme templates — **not** a downstream/concrete
project's `templates/` directory, because this file is FLS's own build input, not the downstream
project's. `docs/how tos/theme-fls.md` "Build pitfalls" (lines 356-382) already documents this
generally:

- `@source` honours `.gitignore`; a path excluded by an ancestor `.gitignore` (e.g. inside a
  vendored/submodule tree) is silently skipped — no build error, classes just don't appear
  (lines 358-360).
- Any new template introducing new utility classes must be covered by an explicit `@source` glob
  in the downstream's own `tailwind.input.css`, or those classes won't be generated
  (lines 374-382), with the worked example `@source "./themes/<theme_slug>/templates/**/*.html";`
  for theme-level overrides.

`docs/how tos/landing-pages.md` shows the concrete pattern for a downstream **project-level**
override in practice (lines 79-92): it lists three `@source` globs including
`@source "./your_project/landing/templates/**/*.html";` for the downstream project's own template
tree, alongside the two FLS-owned globs.

**Confirmed trap for the footer:** yes, a downstream project's own
`templates/partials/footer.html` — living outside FLS entirely, at the project level rather than
inside a theme — needs its own `@source` glob (e.g. `@source "./templates/**/*.html";` or
whatever covers the project's `templates/` root) in **that project's own `tailwind.input.css`**,
or any Tailwind utility class used only inside `footer.html` will be silently absent from the
compiled bundle. This is not a new trap invented for the footer — it is the existing, documented
`@source`/`.gitignore` pitfall — but the footer feature is a fresh, concrete trigger for it (a
brand-new template file, easy to add without touching `tailwind.input.css`), so the footer
documentation should point at this section explicitly rather than assume the reader already knows.

`package.json`'s `tailwind_build` script (`npm run _write_active_theme && npx @tailwindcss/cli -i
./tailwind.input.css -o ./static/vendor/tailwind.output.css`) confirms the two-step build
(`theme-fls.md:97-101`) — no footer-specific build step is needed, just re-running
`tailwind_build` after adding the override, per the existing instruction at `theme-fls.md:382`.

## 6. The conformance suite

`freedom_ls/contrib/conformance/` — modules found: `test_theme.py`, `test_admin_site.py`,
`test_urls.py`, `test_settings.py`, `test_migrations.py`, `tests/test_timestamped_models.py`,
`tests/test_app_labels.py`, `tests/test_conformance_meta.py`, plus `_registry.py` (the
`drop()`/`_is_dropped()` opt-out registry for downstream-customised internal-tier probes).

`test_theme.py` (read in full) is the closest analogue: `test_active_theme_resolves` calls
`freedom_ls.base.theming.resolve_theme_dir` directly and asserts the resolved path `is_dir()`;
`test_active_icon_set_resolves` asserts the configured icon set is a known key and that
`render_icon` produces an `<svg>`. Both are **resolution-correctness** probes (does the setting
point at something real), not content/markup probes.

Per `docs/product/configuration-and-extension.md:103-108`, the conformance suite confirms: page/feature
URL wiring (sitemap, robots), the course-access backend loads and can be created, the active theme
and icon set resolve, and the DB schema matches the code's model state (`test_migrations.py`). **A
new overridable chrome partial like `partials/footer.html` is not the kind of thing this suite
checks** — it has no settings-resolution failure mode analogous to `FLS_THEME`/`FREEDOM_LS_ICON_SET`
(an override that's simply absent renders as a no-op, not a startup or wiring failure), so it does
not belong in `contrib/conformance/`.

The mechanism that **does** apply to a chrome partial is the separate one documented in
`theme-fls.md` "Structural hooks an override must keep" (lines 326-349): a table of `id`/`data-*`
attributes that "FLS's own test suite ships to your project and asserts against" — i.e. FLS's
regular (non-`contrib.conformance`) test suite, made portable to downstream projects (see the
`fls-test-portability` spec history in `spec_dd/3. done/`), asserts these hooks exist regardless of
how a template's markup is restyled. If FLS ships a default `partials/footer.html` with any
structural hook worth guaranteeing (unlikely if it starts empty, per
`from_concrete_implementation.md:17`), that hook would be added to **this table**, not to
`contrib/conformance/`. If the shipped partial renders nothing, no hook is needed and no addition
to either mechanism is required at ship time.

## 7. Documentation surfaces that would need to change

Exact files and sections, named for where to go and act (no doc changes made here):

1. **`docs/how tos/theme-fls.md`**
   - "Tier 3 — Template overrides" section (starts line 278) — add `partials/footer.html` as a
     named worked example of an "App template or partial override" (the existing pattern shown at
     lines 316-324 uses `learner_interface/partials/course_card_registered.html`; a footer
     equivalent would show `base/templates/partials/footer.html`).
   - "Structural hooks an override must keep" table (starts line 326) — add a row only if the
     shipped partial ends up carrying a hook worth guaranteeing (see §6).
   - "Header and side-panel component-tier tokens" table (lines 218-230) — add a parallel
     `--color-footer` / `--color-on-footer` row only if the shipped partial gets its own themeable
     surface colour (see §3(d) gap).
   - "Build pitfalls → `@source` and `.gitignore`" (lines 356-382) — no edit needed to the section
     itself, but the footer feature's own docs (wherever they land, e.g. the idea/spec, or a future
     footer-specific how-to) should link here rather than restate it.

2. **`docs/product/configuration-and-extension.md`**
   - "Three-Tier Theming" section (line 28 onward) — Tier 3 bullet (line 36) currently gives no
     named example; could name `partials/footer.html` alongside the existing generic description.
   - "Custom-App Extension Model" section (line 83 onward) — the "Template priority" bullet
     (line 88) is the general statement this seam falls under; no new bullet strictly required,
     but naming the footer partial here as a concrete instance of the general rule would make it
     read as advertised rather than merely possible.

3. **`docs/product/README.md`** — no structural change required; the "Configuration and Extension"
   row (line 41) already summarises theming generically. Only touch if the footer becomes
   prominent enough to warrant its own bullet.

4. **The install guide, `docs/how tos/incorperate into another project.md`, referenced by
   `theme-fls.md:376` ("The downstream template example in the install guide already includes...")
   and `theme-fls.md:417` ("as shown in the install guide") — does not currently exist in the
   tree.** `Glob` of `docs/how tos/*.md` returns only `landing-pages.md` and `theme-fls.md`.
   Searching the whole repo for the phrase "install guide" turns up only planning history in
   `spec_dd/3. done/2026-05-30_.../` and `spec_dd/3. done/2026-06-18_.../`, which planned to
   *update* `docs/how tos/incorperate into another project.md` — but the file is absent today.
   This is a **pre-existing dangling reference in `theme-fls.md`**, not something the footer
   feature introduces, but it means the footer feature cannot "add an example to the install
   guide" as `from_concrete_implementation.md` implicitly assumes — that guide would need to be
   (re)created first, or the footer's downstream `@source`/override example should live in
   `theme-fls.md` itself instead (which does exist and already carries the closest analogous
   content, e.g. `landing-pages.md`'s own `@source` worked example at lines 79-92, and
   `landing-pages.md` is itself a plausible sibling doc if a footer how-to becomes substantial
   enough to need one).

5. **`freedom_ls/learner_interface/templates/learner_interface/_exam_runner_base.html`** — not a
   docs file, but per §2, if the footer block is suppressed here (mirroring the header
   suppression at lines 29-31), that is itself the "documentation" a future reader relies on (a
   one-line `{% comment %}` stating why), same convention as the existing header suppression.

## 8. The `footer` name-collision check

Grep for "footer" (case-insensitive) across `freedom_ls/` returns 32 files. Web-chrome-relevant
hits, read directly:

| Location | What "footer" already means there |
|---|---|
| `freedom_ls/base/templates/cotton/media-card.html:1,7,15,17` | `<c-vars footer="" ... />` — a **named cotton slot** ("`footer` slot renders in a bordered bar below it for captions and actions"). |
| `freedom_ls/base/templates/cotton/modal.html:2,75,77` | Same pattern — `<c-vars title footer class="" ...>`, a named slot for the modal's action-button row. |
| `freedom_ls/learner_interface/templates/cotton/player-footer.html` | A whole cotton **component** named `c-player-footer` — the course player's own bottom navigation bar (Previous/Next), included by topic, form-start and form-completion pages. Its own doc comment: *"The course player's footer bar."* |
| `freedom_ls/learner_interface/templates/learner_interface/course_form_page.html:315,458` | A hand-labelled region, `{% comment %}=== STICKY FOOTER ==={% endcomment %}` ... `{% comment %}End sticky footer{% endcomment %}` — the runner's own sticky action bar. |
| `freedom_ls/accounts/templates/emails/base_email.html:12-13,32-33` | `.email-footer` CSS class + `{% include "emails/includes/footer_links.html" %}` — the transactional email's legal/unsubscribe footer. |
| `freedom_ls/reports/templates/reports/report.html:39,46,53-57,69` + `freedom_ls/reports/static/reports/print.css` | `.footer-identity`, `.footer-org`, `.footer-doc`, `.footer-powered-by`, `.footer-logo` — the PDF cohort report's per-page footer band (organisation name, cohort/report name, platform attribution), drawn by `print.css` in the page margin box. |
| `freedom_ls/panel_framework/templates/panel_framework/partials/delete_confirmation.html:25` | `<c-slot name="footer">` — another cotton-slot usage, this time filling a modal's `footer` slot. |

**"Footer" is already a heavily taken word in FLS's vocabulary** — but consistently as *"the
bottom region/slot of one component"* (a modal, a media card, the course player, an email, a PDF
page), never as *"the site-wide page-chrome landmark."* `.claude/skills/domain-glossary/SKILL.md`
does not list "footer" in its "Words that are already taken" table (§"Words that are already
taken", lines 132-146) — that table is scoped to domain-model nouns (`grant`, `item`, `link`,
`slot`, `course item`, `collection`, `is_active`, `learner`), not UI-chrome vocabulary, so
"footer" is not a glossary violation in the sense that table guards against.

It **is**, however, a real readability/searchability collision: grepping the codebase for
"footer" today returns seven unrelated meanings before you'd find the new site-chrome one, and a
docs reader skimming for "footer" in `theme-fls.md` or `configuration-and-extension.md` needs the
prose to disambiguate on first use ("the site footer" / "site-wide footer chrome", not bare
"footer"). Two concrete options, not a mandate:

- **Keep `partials/footer.html` / `{% block footer %}`** (the settled design) and rely on prose
  disambiguation ("the site footer", by analogy the way `header_bar.html` is never confused with
  `cotton/player-footer.html`'s sibling concept, "the player's top bar," because none exists —
  header has no other claimant, footer has six). This matches the block-name-vs-partial-name
  precedent noted in §1 (block `header` names the landmark generically; the file can be more
  specific) — so `{% block footer %}` including `partials/footer.html` is internally consistent
  even though "footer" is overloaded elsewhere.
- **Rename the partial to `partials/footer_bar.html`**, mirroring `header_bar.html` literally
  (both are horizontal chrome bars) and reducing the string-search collision with
  `cotton/player-footer.html` specifically (the one other "-footer.html" filename in the tree,
  and the one most likely to be confused with it since both concern the learner-facing chrome).
  The block name (`{% block footer %}`) can stay generic either way, per the same
  block-name/partial-name split.

This is a naming call for the idea/spec stage, not something this research unit resolves — flagged
here as required by the brief with both options and their precedent, no recommendation forced.

---

## Summary of load-bearing facts for the spec

- **(a) Conventions to match** — §1: root on `<footer>`, one-line include inside the block, no
  default `id`/`data-testid`, cotton components for interactivity, `{% if %}`-branch-and-delegate
  for conditional rendering, doc-comment header explaining intent.
- **(b) Resolution order, verified** — §3: host project `templates/` → active theme
  `<theme>/templates/` (prepended by `configure_theme`) → FLS app dirs (`app_directories.Loader`).
  Project-level wins over theme-level. The theme-submodule caveat from
  `from_concrete_implementation.md` is **confirmed for the current lack of any shipped
  `themes/*/templates/`**, but the claim that the theme path is *unusable* for a downstream
  project is **overstated** — `BASE_DIR / "themes"` shadowing (§4) is a legitimate, submodule-safe
  alternative to the project-level path; recommend documenting both, project-level as default.
- **(c) Traps to record** — §5 Tailwind `@source` (confirmed live, needs a downstream
  `tailwind.input.css` glob covering the project's `templates/` tree); §6 conformance suite (does
  **not** need a footer probe — wrong mechanism; the "structural hooks" table in `theme-fls.md` is
  the right mechanism, only if a hook is added); §8 naming collision (real but scoped to UI-chrome
  vocabulary, not the domain glossary; two options given, no mandate); §7 item 4, a **dangling
  "install guide" reference** in `theme-fls.md` pointing at a doc that does not exist — pre-existing,
  not footer-caused, but blocks literally following `theme-fls.md`'s own instructions for where to
  add a downstream worked example.
- **(d) Documentation surfaces** — §7: `docs/how tos/theme-fls.md` (Tier-3 section, structural-hooks
  table conditionally, component-token table conditionally), `docs/product/configuration-and-extension.md`
  (Three-Tier Theming Tier-3 bullet, Custom-App Extension Model), optionally `docs/product/README.md`,
  and the suppression comment in `_exam_runner_base.html` itself if the runner blanks the block.

status: ok
reason: All eight investigation points completed against the live codebase (header_bar seam read in full, block-header overrides grepped, resolution order verified against config/settings_base.py and theme-fls.md, theme-directory caveat confirmed via freedom_ls/themes/** glob, @source trap confirmed live in tailwind.input.css/landing-pages.md, conformance suite read and scoped out, doc surfaces named, footer word-collision grepped across freedom_ls/). One pre-existing gap surfaced (theme-fls.md references a non-existent install guide) and one theme-submodule claim corrected (theme-level override path is usable, not just project-level) — both flagged inline for the spec stage.
