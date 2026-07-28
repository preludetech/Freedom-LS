# Changelog

## 2026-07-28 — Cotton is the top of the reuse ladder

- **`resources/frontend_styling.md`'s Critical Rule now starts at cotton.** The ordered list ran
  read-the-stylesheets → cotton → component class → utilities, so the reuse ladder's top rung sat at
  position 2. It is now a three-item ladder — cotton, component class, utilities — and item 1 says
  outright that a component the project has already built for the job is the thing to use, not
  something to re-derive inline.
  - _Why:_ a reader skimming a numbered list treats item 1 as the primary instruction. The one thing
    that should be checked first was the one thing that wasn't first.
- **Reading the stylesheets is a precondition, not a list item.** It has its own emphatic section
  immediately above the list; it is now a clause in the list's lead-in rather than a restatement of
  that section.
  - _Why:_ same "say each thing once" pass as the entry below — a rule stated twice within fifteen
    lines reads as two rules.

## 2026-07-28 — `alpine-js` routes, the build files own the mechanics

- **`skills/alpine-js/SKILL.md` no longer contains CSP-build content.** The file claimed "everything
  below this line is build-agnostic" and then spent 250 lines on the CSP form: a full
  `Alpine.data()` registration example, the per-app `alpine-components.js` convention, and a `## Patterns`
  section that opened "all patterns below use the registered-component form". The registration section
  and every JS-shaped pattern (`data-*` passing, `localStorage` + `$watch`, simple toggle, computed
  classes, auto-dismiss, `matchMedia`, click-away/escape) are gone from the skill.
  - _Why:_ under `CSP build: disabled` that guidance is not merely irrelevant, it is the wrong idiom —
    a reader routed to `alpine_no_csp.md` was still being shown mandatory registration by the file that
    routed them. A build flag either partitions the guidance or it doesn't.
- **What stays in the skill is what is byte-for-byte identical under both builds**: transitions
  (CSS classes), `x-cloak`, the `x-collapse` plugin gate, icon toggling via wrapper `<span>`s, the
  `_base.html` plugin check, and Alpine-vs-HTMX. Every surviving code block contains only CSS class
  strings, bare property references (`x-show="open"`), or directive modifiers. The `x-collapse` example
  lost its `x-data="expandablePanel"` / `x-on:click="toggleExpanded"` wrapper, and rules 6–8 now state
  the requirement (clean up listeners, `click.away`, `keydown.escape.window`) without a build-shaped
  example.
- **Two dangling cross-references are fixed.** `alpine_csp_build.md` and `alpine_no_csp.md` both told
  the reader to go back to "the main skill's Registering components section" for the shape — a
  reference that no longer resolves, and shouldn't have: the shape now appears in each build file,
  phrased for that build (mandatory under CSP; one of four promote-from-inline triggers under standard).
  - _Why:_ README already promised these resources are mutually exclusive and self-contained. They now
    are — each is readable start to finish with the other two absent.
- **`alpine_no_csp.md` gained the standard-build forms it never had**: inline toggle, inline ternary
  classes, template values interpolated into `x-data` (with `data-*` + `$el.dataset` as the rule for
  anything string-valued or per-loop-item), and `x-init="setTimeout(…)"` for auto-dismiss — the exact
  construct `alpine_csp_build.md` lists as forbidden.
- **Echo site**: `fls-dev-claude-plugin/skills/alpine-js/SKILL.md` line 9 said the ds skill's
  "CSP-build restrictions apply only when configured"; the ds skill no longer carries any, so it now
  points through to the build resource file. Resource count is unchanged at 11 — no new files.

## 2026-07-28 — Name the entry file, state the layer convention, say each thing once

- **`tailwind.input.css` is named outright.** The instruction was a two-step lookup — open
  `package.json`, find the `tailwind_build` script, read its `-i` flag — for a filename that is
  `./tailwind.input.css` on every project on this stack. It is now "read `./tailwind.input.css` and
  every project file it `@import`s", with a single parenthetical fallback for a project that names its
  entry file differently.
  - _Why:_ a procedure for discovering a constant is three steps of ceremony before any styling work
    starts. Naming it costs one clause of portability and saves the lookup every time.
- **`## Base Styles` → `## Where new CSS goes — the layer convention`.** The old section described what
  "many projects" do with `@layer base`; it never said where to put a *new* rule. It is now a table:
  tokens → `@theme {}`, element selectors → `@layer base {}`, reusable classes → `@layer components {}`,
  new utilities → `@utility`. Plus the rule that makes it non-negotiable: **never write an unlayered
  rule.**
  - _Why:_ this is not a style preference. Tailwind v4 declares `@layer theme, base, components,
    utilities;`, and in the CSS cascade unlayered declarations beat every layered one — so a bare
    `h1 { font-size: 3rem }` written outside a layer silently overrides `text-2xl` on that heading and
    no class in the markup can win. Unlayered CSS is a bug, and the doc now says so.
- **The reuse order is stated once instead of four times.** "Cotton component → component class → raw
  utility" appeared in the Critical Rule, again in the Design Tokens closer, again as
  `## Reusable Components`, and again in `## Usage Rules` (itself a recap of every section above it).
  `## Reusable Components` and `## Usage Rules` are deleted; their unique content — the
  `@layer components` home for component classes, utilities-are-for-one-off-styling, and
  promote-when-repeating — folded into Critical Rule steps 3 and 4.
  - _Why:_ four wordings of one rule is four chances to drift apart, and the two deleted sections were
    where the surviving hedges lived ("one (or both) of two ways", "whichever this project actually
    has", "often named…"). The resource drops ~30 lines and every claim now has exactly one owner.
- **Echo sites aligned**: `skills/frontend-styling/SKILL.md` (entry file named, layer rule added),
  `resources/templates_and_cotton.md` (workflow step 4 and Key Rule 1), `skills/htmx/SKILL.md` (the
  `.htmx-request` snippet now says which layer it belongs in), `skills/alpine-js/SKILL.md` (`[x-cloak]`
  goes in `@layer base`).

## 2026-07-28 — One name for browser tests: `playwright`

- **Browser tests live under `tests/playwright/`**, matching the `@pytest.mark.playwright` marker.
  Previously the marker said `playwright` and the directory said `e2e`, so the docs carried a paragraph
  explaining that the marker is *not* renamed to `e2e` and that no `e2e` marker exists. That paragraph
  is deleted along with every other `e2e` mention: `resources/playwright-testing.md` (title, portability
  section, commands, directory tree), `skills/playwright-tests/SKILL.md`, `skills/testing/SKILL.md`, and
  `resources/testing.md`.
  - _Why:_ two names for one concept meant the docs had to keep reconciling them. Fixing the
    disagreement removes the need to describe it — the name is the name.
  - `E2E` survives in exactly one place: the `playwright-tests` skill `description`, whose job is to
    match the words a user might type. It documents no convention.
- The "keep the marker and don't rename it" instruction became "mark every browser test, without
  exception" — the same portability guarantee stated as a rule about what to do rather than a rule
  about naming.

## 2026-07-28 — Read the Tailwind entry file; stop special-casing `tailwind.components.css`

- **The mandatory step is now "read the Tailwind entry stylesheet and every project file it
  `@import`s"**, stated once in `resources/frontend_styling.md` and referenced from the Critical Rule,
  Design Tokens, Base Styles, and Usage Rules sections. The `@import "tailwindcss"` library import is
  explicitly excluded from the walk. (Superseded below: the entry file is now named outright rather
  than looked up via `package.json`'s `-i` flag.)
- **`tailwind.components.css` is no longer a step.** It went from 8 references — most of them a
  conditional `cat`, hedged with "if the project has one" — to 2 purely descriptive mentions ("a file
  often named…"). Same substitution in `skills/frontend-styling/SKILL.md` and the two spots in
  `resources/templates_and_cotton.md`.
  - _Why:_ the file is a convention, not a guarantee, so every reference needed a hedge, and a reader
    who found no such file was left unsure whether something was missing. Worse, singling it out
    implied the entry file and that one file were all that mattered: in this repo the entry stylesheet
    imports **five** project stylesheets, so three of them — including base styles — were invisible to
    anyone following the old instruction. Following the imports is both unconditional and strictly more
    thorough. A project with everything inline (like the second consumer project) simply finds one file
    and stops, with no missing-file caveat and no dead step.

- **`resources/admin_interface.md` → three self-contained files**, one per configuration:
  `admin_standard.md` (plain Django admin), `admin_unfold.md` (django-unfold theme), and
  `admin_guardian.md` (object permissions). `skills/admin-interface/SKILL.md` became a router: read
  `.claude/ds/config.md` → `## Admin`, load **exactly one** theme file, and add the guardian file only
  when guardian is `enabled`.
  - _Why:_ the single file made every project read all three configurations — including the two it
    doesn't use — to find the one that applies. Worse, the shared "Common Patterns" section was written
    in standard-admin imports with a note telling Unfold projects to mentally substitute
    `unfold.admin`; that kind of indirection gets half-applied, and a wrong base class here fails
    silently (the page renders unstyled rather than raising). Each theme file now spells out its own
    imports throughout, so there is nothing to substitute. The duplication between the two theme files
    is deliberate: they are alternatives, never read together.
  - `admin_guardian.md` also picked up the concrete options for the Unfold/guardian MRO clash, which
    the old file only mentioned as a one-line caveat.
- `README.md` resource inventory updated (9 → 11) and now notes which resource sets are
  mutually exclusive (`admin_standard` **or** `admin_unfold`; `alpine_csp_build` **or**
  `alpine_no_csp`).
- Downstream: `fls-dev`'s admin overlay and README now point at `admin_unfold.md` + `admin_guardian.md`
  specifically, since that is the pair FLS's config selects.

## 2026-07-28 — Portability pass, part 2 (review follow-up)

Reviewing part 1 against **both** consumer projects surfaced assumptions the first pass missed, one
outright breakage in projects without a root `.mcp.json`, and some internal drift.

### Design tokens — `ds` now names none

- **Removed the role-token table** (`primary` / `on-primary` / `surface` / `error` / …), the
  `text-on-X` contrast rule, the `*-hover` `color-mix()` derivation, and the `*-bold` note from
  `resources/frontend_styling.md`. In their place, a "read the theme, never assume it" section: open the
  Tailwind entry stylesheet, follow its `@import`s, read the `@theme {}` blocks, and style with those
  tokens only. `skills/frontend-styling/SKILL.md` leads with the same instruction.
  - _Why:_ that table was one project's theme presented as the token system. A second project's theme
    defines an entirely different set (`limelight`, `ink`, `paper`, `mist`), so `bg-primary` there is a
    class that silently does nothing — the worst kind of wrong, because the markup looks right. Token
    names are per-project data, not stack convention, so `ds` now teaches how to find them instead.
  - The full role-token contract was **moved**, not deleted, into the downstream `fls-dev` plugin
    (`resources/frontend_styling.md` + its skill), which is where that theme actually lives.

### Component libraries and Alpine plugins are no longer assumed

- **`skills/htmx/SKILL.md`** — the loading-indicator section prescribed `<c-loading-indicator>` /
  `<c-button>` and asserted `.htmx-hide-on-request` / `.htmx-show-on-request` are "defined in
  `tailwind.components.css`". Rewritten around HTMX's own `.htmx-request` / `.htmx-indicator` classes,
  with project components as an "if it exists" check. Added a note at the top that every `<c-*>` in the
  file is a placeholder.
  - _Why:_ it directly contradicted part 1's decision to make `tailwind.components.css` optional, and
    prescribed components from a library `ds` doesn't ship. The underlying mechanism is pure HTMX and
    works everywhere; the component is a convenience some projects have.
- **`resources/templates_and_cotton.md`** — flagged the `<c-button>` / `<c-loading-indicator>` /
  `<c-modal>` example block as illustrative names, with the command to list what actually exists.
- **`skills/alpine-js/SKILL.md`** — stopped asserting that Alpine's Collapse plugin is loaded and
  Persist is not. The Setup section now says to read `_base.html` for the `@alpinejs/*` scripts the
  project loads; `x-collapse` is explicitly gated on `@alpinejs/collapse` with an `x-show` +
  `x-transition` fallback; the `x-cloak` CSS rule is something to check for rather than assume.
  - _Why:_ a project loading plain Alpine gets nothing from `x-collapse` — the directive is inert
    without its plugin, so "prefer `x-collapse` over `x-show`" produced markup that silently didn't
    animate. Which plugins are loaded is per-project and cheap to check.
- **`resources/alpine_no_csp.md`** — same correction in the standard-build file's Setup and rules.
- **`resources/alpine_csp_build.md`** — now opens conditionally ("applies when `CSP build: enabled`"),
  mirroring `alpine_no_csp.md`, instead of stating "This project uses the CSP build" as fact; the
  example script block's hardcoded `base/js/alpine-components.js` became an `<app>/js/…` placeholder.
  - _Why:_ the unconditional opener made a file that only sometimes applies read as universal, and
    `base/` was the origin project's app name.

### Playwright MCP — fixed a real breakage

- **`skills/use-playwright/SKILL.md`** — removed the `allowed-tools` whitelist and documented that the
  server appears as `mcp__plugin_ds_playwright__*` (plugin-supplied) and/or `mcp__playwright__*` (when
  the project also declares it at the root).
- **`templates/settings.json`** — added `mcp__plugin_ds_playwright__*` alongside `mcp__playwright__*`.
  - _Why:_ `ds` supplies the Playwright server through its own `.mcp.json`, so its tools are namespaced
    `mcp__plugin_ds_playwright__*`. The whitelist listed only the unprefixed names, so in any project
    that doesn't *also* declare a root `playwright` server, the skill's own frontmatter blocked every
    browser tool it needs. The origin project only worked by accident, because it happens to declare the
    server twice. The whitelist also still named two tools that no longer exist (`browser_run_code`,
    `browser_install`) — a standing argument against pinning tool lists in frontmatter.

### Internal drift closed

- **`commands/init.md`** — Step 8 now validates the `## Admin` section it writes in Step 2 (both keys),
  and the closing summary names the admin flags, warning that the defaults are wrong for any project
  already on django-unfold or object permissions.
  - _Why:_ part 1 added the keys to the writer but not the validator or the summary, so a project could
    finish `init` with a silently missing/incomplete admin section and no prompt to review it.
- **`README.md`** — corrected "Resources (7)" to 9 (both Alpine files were missing from the inventory)
  and added a table of the four `.claude/ds/config.md` keys, who reads each, and their defaults.
  - _Why:_ the config surface had grown to four keys across three skills with no single place to see it.

### Downstream (`fls-dev`, outside `ds`)

- Absorbed the role-token contract into `fls-dev`'s frontend-styling skill + resource, which previously
  only pointed at the `ds` table.
- Corrected two overlay sentences that still described `ds:admin-interface` as "the generic Unfold
  configuration" — it is theme-configurable now, and FLS selects Unfold via its config.
- Set `Admin theme: unfold` / `Object permissions (django-guardian): enabled` (and the dev base URL) in
  the FLS project's own `.claude/ds/config.md`.
  - _Why:_ part 1 made the admin skill default to `standard`, but that project's admin is entirely
    `unfold.admin` + django-guardian — without the config it would have been told to write plain
    `admin.ModelAdmin` into a codebase that uses none.

## 2026-07-28 — Portability & consistency pass

Made the plugin genuinely portable (no product-specific leakage), configurable where projects
legitimately differ, and internally consistent.

### Configurable

- **Admin is now configurable instead of Unfold-only.** `skills/admin-interface/SKILL.md` and
  `resources/admin_interface.md` now read two flags from `.claude/ds/config.md` → `## Admin`:
  - `Admin theme` — `standard` (plain Django admin, the portable default) or `unfold`.
  - `Object permissions (django-guardian)` — `enabled` / `disabled` (default `disabled`).
  Standard Django admin is documented as the baseline; Unfold and django-guardian are opt-in sections.
  - _Why:_ Unfold and django-guardian are project-level tool choices, not universal Django best
    practices, so a portable plugin must not hard-mandate them. The plugin previously forced Unfold,
    which conflicts with any project (like this one) on vanilla admin — so each project now chooses.
- **`commands/init.md`** now seeds those admin defaults into the generated `.claude/ds/config.md`
  (`Admin theme: standard`, `Object permissions (django-guardian): disabled`).
  - _Why:_ so a freshly-initialised project already has the admin flags present with safe, portable
    defaults, and the new configurable skill has values to read without prompting the user.

### Alpine.js — clean CSP split

- `skills/alpine-js/SKILL.md` restructured to route on the `## Alpine.js → CSP build` config flag and
  hold only build-agnostic patterns. `Alpine.data()` registration is now **required under the CSP
  build** and **optional (recommended) under the standard build** — previously it was mandated
  unconditionally.
  - _Why:_ mandating registration unconditionally over-constrained standard-build projects that
    legitimately use inline expressions. Registration is only *technically* required by the CSP build,
    so the requirement is now gated on the same flag that determines the build.
- Added **`resources/alpine_no_csp.md`** documenting the standard build (inline `x-data` expressions
  allowed; when to still register components).
  - _Why:_ to give the standard (CSP-off) build its own home so each build's conventions live in
    exactly one file — a clean split — rather than being interleaved with, or buried inside, the
    CSP rules.
- `resources/alpine_csp_build.md` continues to own the CSP-build rules; fixed a stale section
  cross-reference.
  - _Why:_ the cross-reference pointed at a skill section that was renamed during the restructure, so
    it would have sent readers to a heading that no longer exists.
- The inline-Alpine example in `resources/templates_and_cotton.md` is now filed explicitly under the
  CSP-off path (with both variants shown), resolving the previous contradiction with the CSP guidance.
  - _Why:_ the example sat in general guidance yet showed inline expressions the CSP build forbids — a
    direct contradiction. It is valid only under the standard build, so correct placement (not deletion)
    resolves it.

### Frontend styling — generalized

- `skills/frontend-styling/SKILL.md` and `resources/frontend_styling.md` no longer assume a
  `tailwind.components.css` exists. The Tailwind entry file (commonly `tailwind.input.css`) is the
  theme source; `tailwind.components.css` is treated as **optional ("if it exists")**; **django-cotton
  components are recognized as a valid reuse mechanism** alongside (or instead of) CSS component classes.
  - _Why:_ the previous hard rule ("ALWAYS check `tailwind.components.css`") assumed a file many
    projects — including this one — don't have; they express reuse through django-cotton components.
    Forcing CSS component classes would have introduced a second, competing UI abstraction next to the
    cotton components.

### Templates / Cotton — location flexibility

- `skills/template/SKILL.md` and `resources/templates_and_cotton.md` now permit **project-level
  `templates/cotton/`** for shared/design-system components in addition to app-local
  `<app>/templates/cotton/`.
  - _Why:_ the app-local-only rule didn't fit projects that keep a shared design-system component
    library at the project level (as this one does). Both layouts are valid for django-cotton, so
    allowing both avoids forcing a needless move.

### Portability fixes (removed product-specific leakage)

- **`scripts/db_clear.sh`**: removed the hardcoded `~/.lms_postges_dev_data` default (LMS-project leak
  + `postges` typo). It now requires `DB_DATA_PATH` and skips the wipe with a warning if unset, and only
  removes `media/` when it exists.
  - _Why:_ the default embedded the origin project's identity (`lms`), which breaks the plugin's
    portability promise (README: "zero product-specific domain knowledge"). It also carried a typo and
    blindly deleted `media/`; requiring `DB_DATA_PATH` refuses to guess another project's data path
    rather than deleting the wrong directory.
- **Removed all `/plan_structure_review` references** (a command not shipped by this plugin) from
  `commands/app_map.md` and `scripts/generate_app_map.py`.
  - _Why:_ they pointed at a command this plugin doesn't provide, contradicting its "depends on no
    other plugin" claim and leaving a dangling instruction that would confuse Claude in any downstream
    project that installs ds alone.
- **Neutralized LMS/course-domain examples** to generic placeholders across `resources/playwright-testing.md`,
  `skills/playwright-tests/SKILL.md`, `skills/htmx/SKILL.md`, `skills/alpine-js/SKILL.md`, and
  `resources/templates_and_cotton.md` (e.g. course/enrollment → article/comment flows; `dashboard:home`
  → `home`; synthetic login uses `user@example.test`).
  - _Why:_ the LMS/course identifiers revealed the plugin's origin domain and were inconsistent with
    its stated neutrality (other examples already use generic placeholders). Concrete foreign-domain
    names read as real conventions and can mislead in an unrelated project.
