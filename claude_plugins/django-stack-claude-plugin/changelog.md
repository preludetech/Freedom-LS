# Changelog

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
