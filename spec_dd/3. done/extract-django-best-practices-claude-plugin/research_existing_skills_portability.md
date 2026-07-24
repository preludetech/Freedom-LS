# Research: Existing FLS skills — what is portable, what is FLS-specific

This research catalogues each existing skill in `fls-claude-plugin/skills/` and assesses whether its content belongs in the new stack-generic `dc` plugin, stays FLS-only, or splits between the two.

The idea explicitly names these as portable: **testing, templates, cotton, htmx, factory boy, template partials, django tasks**, plus "any non-fls, stack specific setup".

## Per-skill assessment

### testing
- **Portable content**: pytest + pytest-django + factory_boy patterns; TDD cycle; AAA structure; tautological-test red flag; mock-only-at-boundaries rule; `pytest-randomly`; `pytest-socket`; `time-machine`; `client.force_login` over `request.user` patching; HTMX header tricks (`HTTP_HX_REQUEST="true"`, 422 on validation, `HX-Trigger` assertion); separate-test vs parametrize guidance.
- **FLS-specific bits to peel out**: `freedom_ls/<app_name>/tests/test_<module>.py` path; `mock_site_context` fixture (multi-tenant); reference to `fls:playwright-tests` skill; reference to `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md` (move that resource into dc).
- **Verdict**: extract bulk into `dc:testing`. FLS keeps a thin skill that adds the site-aware overlay (mock_site_context, freedom_ls/ paths) and otherwise defers to `dc:testing`.

### template (cotton + Django templates + partials)
- **Portable content**: cotton component conventions (`<c-vars>` with defaults, location under `templates/cotton/`), partials with `{% partialdef %}`, never-hardcode-URLs, `partial_` view-prefix convention, kebab-case partial names, page templates extending a base.
- **FLS-specific bits**: `freedom_ls/<app>/...` paths, the specific `_base.html`, FLS's specific component library.
- **Verdict**: extract templating + cotton + partials conventions into `dc:templates` (or split into `dc:cotton` + `dc:partials` + `dc:templates` if granularity matters). The init command can capture the project's apps directory and base template.

### htmx
- **Portable content**: global CSRF on `<body>`, `HX-Request` detection, dual rendering pattern, `partial_` naming, 422 for validation errors, always-pair `hx-target` + `hx-swap`, prefer `outerHTML`, debounced search pattern, URL-query-param state preservation, `hx-boost="false"` for full-page links, separation of HTMX (server) vs Alpine (client).
- **FLS-specific bits**: references to `<c-button>`, `<c-loading-indicator>`, the specific CSS utility classes `.htmx-hide-on-request` / `.htmx-show-on-request`.
- **Verdict**: extract bulk into `dc:htmx`. Cotton-component-specific examples can move to `dc:cotton` or be made generic.

### frontend-styling (Tailwind)
- **Portable content**: utility-classes-only philosophy, mobile-first responsive, `npm run tailwind_build` after adding new classes, palette/spacing-scale consistency.
- **FLS-specific bits**: the specific palette, spacing scale, components, brand guidelines — those stay FLS.
- **Verdict**: thin `dc:tailwind` skill covering the conventions; FLS keeps brand-specific guidance. Init command should ask for the Tailwind input file path (the idea explicitly flags this: *"Our tailwind input file might not always be in the same place"*).

### alpine-js
- **Portable content**: CSP-build constraint and the `Alpine.data()` pattern, when-to-use criteria, separation from HTMX.
- **FLS-specific bits**: specific script tags / `_base.html` setup, project's component file path.
- **Verdict**: extract conventions into `dc:alpine`. Init command can ask for the alpine-components.js path.

### playwright-tests
- **Portable content**: Playwright-only-when-needed rule, `@pytest.mark.playwright`, `live_server`/`page` fixtures, `expect()` matchers over manual waits, locator priority order.
- **FLS-specific bits**: `tests/e2e/` location can stay generic; site-aware test setup is FLS only.
- **Verdict**: extract into `dc:playwright-tests`. The MCP-driven `use-playwright` skill is more about exploratory browsing — also portable, possibly extract into `dc:use-playwright`.

### admin-interface
- **FLS-specific**: `SiteAwareModelAdmin`, Unfold configuration, FLS-specific inlines.
- **Verdict**: stays in FLS. Could inspire a future `dc:django-admin` for vanilla `ModelAdmin` patterns, but out of scope for this idea.

### multi-tenant, registration, markdown-content, icon-usage
- **FLS-specific**: site-aware models, `SiteSignupPolicy`, `MarkdownContent`, FLS icon library.
- **Verdict**: stays in FLS.

### git-worktree-setup, request-code-review
- **Portable content**: git-worktree workflow, code-review request flow.
- **Verdict**: arguably portable but the idea scopes this work to **Django stack** topics. Defer — out of scope for this idea unless explicitly added.

### update-claude-project-settings
- **Portable**: yes — auditing/promoting `.claude/settings.local.json` entries is a Claude-Code housekeeping skill, not Django-stack.
- **Verdict**: out of scope for the dc plugin.

## Skills the idea names but FLS does not have today

The idea calls out **"factory boy"** and **"django tasks"** explicitly, plus **"template partials"** as a separate item.

- **factory boy** — currently a *resource* in FLS (`resources/factory_boy.md`) referenced from the testing skill. In `dc`, this should be either its own skill (`dc:factory-boy`) or a resource bundled with `dc:testing`. A standalone skill wins because it has its own triggers ("write a factory", "register factories with `register`", "use sub-factories", etc.).
- **django-tasks** — no existing FLS skill. Needs fresh content covering `django-tasks` queue conventions: defining tasks, idempotence, retry policy, testing tasks, naming conventions, where task modules live. Idea author confirms this is desired.
- **template partials** — currently folded into the FLS `template` skill. The idea lists it separately. Question for the author: split it out as `dc:partials`, or keep it bundled in `dc:templates`? The bundled approach is closer to the existing structure; splitting it is what the idea literally asks for. Bundled is probably right unless the partial conventions grow.

## Resources to move

Files under `fls-claude-plugin/resources/` that are stack-generic and should move into `dc/resources/` (referenced via `${CLAUDE_PLUGIN_ROOT}/resources/...`):

- `testing.md` (bulk — peel out site-aware sections)
- `factory_boy.md`
- `templates_and_cotton.md`
- `frontend_styling.md`
- `playwright-testing.md`

Files that stay FLS-only:

- `multi_tenant.md`, `markdown_content.md`, `email_templates.md`, `admin_interface.md`, `agent_memory_guidelines.md`

## Init-command inputs (so the plugin works "out of the box" in any project)

The idea says: *"If it needs an init command then create one. Our tailwind input file might not always be in the same place, and some other configuration might be necessary."* Likely inputs to capture in `/dc:init`:

- Apps root path (default `apps/`, FLS uses `freedom_ls/`)
- Base template path (default `templates/_base.html`)
- Tailwind input CSS file path
- Tailwind build command (default `npm run tailwind_build`)
- Test root convention (default `<app>/tests/`)
- Whether project uses cotton (yes/no)
- Whether project uses Alpine.js CSP build (yes/no)
- Whether HTMX is loaded globally with CSRF on `<body>` (yes/no)
- Where factories live (default `<app>/factories.py`)
- Whether project uses `django-tasks` (yes/no)

These get written to `.claude/dc/config.md` and skills read from there for project-specific paths.

## Open question for the author

The idea says the new plugin *"should still be useful for fls"*. Two ways to honour this:

- **Option A — extract and remove**: Move each portable skill from `fls-claude-plugin` into `dc`, delete the FLS copy, and have FLS depend on `dc`. Cleanest, but means installing FLS implies installing `dc`.
- **Option B — extract and override**: `dc` carries the portable bulk, FLS keeps thin overlays that add site-aware specifics. More flexible, more files. Closer to how FLS currently extends behaviour.

Recommend Option B — but flag for the author to choose during spec writing.
