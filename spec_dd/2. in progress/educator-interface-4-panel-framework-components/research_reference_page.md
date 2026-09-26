# Research: the component reference page

For spec 4 (`educator-interface-4-panel-framework-components`). The idea's "A reference page"
paragraph offers two starting points — behind `DEBUG`, or in the framework's test templates — and
spec 12 (`educator-interface-12-docs-and-polish`) needs it as the target of a Playwright visual
check. This resolves the choice.

## What the codebase already does

- **`panel_framework` has no `urls.py` today.** It is a library of views, panel/table classes and
  cotton templates that `educator_interface` mounts through its own `urls.py` and
  `SectionConfigBase` registry (`freedom_ls/panel_framework/views.py`). Nothing currently gives a
  downstream project a URL to include straight from `panel_framework`.
- **`config/urls.py` already has the DEBUG-gated convention**, one block, real precedent:
  ```python
  if settings.DEBUG:
      from debug_toolbar.toolbar import debug_toolbar_urls
      urlpatterns += [
          path("__reload__/", include("django_browser_reload.urls")),
          path("qa/", include("freedom_ls.qa_helpers.urls")),  # QA-TEMP
      ]
  ```
  `freedom_ls/qa_helpers` (toast playground, `toast_views.playground`) is the closest existing
  thing to a "component demo page": a `DEBUG`-only view rendering a template with every toast
  state. But `qa_helpers` is installed only in `config/settings_dev.py`'s `INSTALLED_APPS`
  (`freedom_ls.qa_helpers`), which is **this repo's own dev settings, not something a downstream
  project's `INSTALLED_APPS` picks up**. Its own comment calls it "QA-TEMP... remove once the toast
  spec QA is complete" — manual QA scaffolding, not a shipped, permanent developer-facing artifact,
  and **no Playwright test exercises it** (checked: zero references outside `qa_helpers/` itself).
  It is not a model to copy wholesale for a permanent, downstream-visible reference page.
- **`panel_framework/tests/` already has a complete isolated test-URL/test-template rig**, built for
  exactly this framework's own Playwright suite:
  - `tests/root_urls.py` — a standalone `ROOT_URLCONF` with one include, `tests/urls.py`.
  - `tests/urls.py` — real views (`panel_framework_view`) wired at test-only paths against
    `STUB_CONFIG` and a test-only template (`panel_framework/test_interface.html`).
  - `conftest.py`'s two autouse fixtures: `_use_panel_test_urls` overrides
    `settings.ROOT_URLCONF` to `tests.root_urls` for every test under this directory;
    `_use_panel_test_templates` **prepends** a test-only directory to `TEMPLATES[0]["DIRS"]`
    (`copy.deepcopy`, not mutated in place, so it resets), used only for the outer wrapper
    templates that don't belong in the shipped app.
  - `tests/playwright/test_data_table_panel_htmx.py` shows the pattern this depends on: the
    pytest-django `live_server` fixture serves whatever `ROOT_URLCONF` the autouse fixture set,
    and `page.goto(f"{live_server.url}/test-panel/framework/...")` drives it with Playwright.
  Critically: **prepending test-only `DIRS` does not stop cotton components from resolving
  normally.** `<c-panel-stat-tile/>` still resolves `cotton/panel-stat-tile.html` through the
  ordinary per-app template loader (app-directories, a different loader than the prepended
  `DIRS` entry), so a theme override at the same loader path is picked up **regardless of which
  URLconf or outer wrapper template is being used to reach the page**. Theme-override fidelity is
  a property of how the *component templates* are referenced (by cotton tag, normal resolution),
  not of the *outer page's* URL or template location.
- **`settings.DEBUG` is forced `False` for the whole pytest run.** `config/settings_dev.py` says so
  explicitly about `dev_tools`: "Django's own test environment forces settings.DEBUG to False for
  the duration of the suite, regardless of the True set above." This is standard Django/
  pytest-django test-environment behaviour (`DJANGO_SETTINGS_MODULE = "config.settings_dev"`, no
  override in `conftest.py`). **Any URL gated by `if settings.DEBUG:` at urlconf-import time,
  including one added to `config/urls.py` the way `qa_helpers` is, will not exist during a pytest
  run** — the include is simply never appended to `urlpatterns`. Spec 12's Playwright check cannot
  reach such a URL without deliberately flipping `settings.DEBUG` and reloading the urlconf mid-test
  (`django.urls.clear_url_caches()` and friends) — brittle, and not how `panel_framework`'s own
  Playwright tests work today. This is the single fact that decides the shape of the answer below.
- **`fls-dev:playwright-tests` / `ds:playwright-tests`**: every browser test lives under
  `tests/playwright/`, is marked `@pytest.mark.playwright` (the marker a downstream excludes with
  `-m "not playwright and not fls_internal and not ci_only and not weasyprint"`), uses the
  `live_server` and `page` fixtures, `expect()` matchers, and a session-scoped `storage_state` login
  fixture so most tests skip the login flow.

## Prior art (web)

- **[django-pattern-library](https://github.com/torchbox/django-pattern-library)** (Torchbox,
  [docs](https://torchbox.github.io/django-pattern-library/), [demo](https://torchbox.github.io/django-pattern-library/demo/)):
  ships as an installable app; the consuming project adds
  `path("pattern-library/", include("pattern_library.urls"))` itself and, in every project that
  uses it in the wild, wraps that under its own `if settings.DEBUG:` (or a dev-only urls module) —
  the package does not gate itself. Patterns are ordinary template files with YAML fixture data;
  nothing about the routing choice touches template resolution.
- **`wagtail.contrib.styleguide`**
  ([docs](https://docs.wagtail.org/en/stable/contributing/ui_guidelines.html)): added to
  `INSTALLED_APPS`, appears as a "Styleguide" item inside the Wagtail **admin**, so it inherits the
  admin's own staff-login gate rather than a `DEBUG` check — it is safe to leave installed in
  production because only staff can reach it, and it is static (components must be added to it by
  hand; "no specific hooks for other modules").
- **[storybook-django](https://github.com/torchbox/storybook-django)**: bridges
  django-pattern-library patterns into Storybook's own dev-only tooling, i.e. it doesn't run inside
  the Django deployment at all.
- **[django-cotton's own demo](https://github.com/SamuelJennings/daisy-cotton)** (`daisy-cotton`,
  a cotton + daisyUI kit): moved to make "the component gallery the whole demo" — a single page
  that is the reference for every component and state, with a theme switcher that restyles every
  preview live, which is the direct analogue of FLS's default/dark-mode requirement.

## Options

### A. A `DEBUG`-gated URL shipped by the framework

A real view + template in `panel_framework`, using its cotton components with static example
context (no DB queries), wired at a path a consuming project includes explicitly — the same shape
as `debug_toolbar_urls()` and the `qa_helpers` toast playground, but living in `panel_framework`
itself (an app already in the app structure list, unlike `qa_helpers`) so it ships to every
downstream install, not just this repo's dev settings.

- **Downstream visibility:** good — any downstream project that wires the include (documented,
  one line, `if settings.DEBUG:`) gets it on their own dev server, no fixture or test run needed.
- **Theme overrides:** good — an ordinary page using `<c-panel-*/>` tags resolves each component
  through the normal per-app/theme loader chain; a theme's override at the same loader path wins,
  exactly as in a real screen.
- **Security:** gated at the *include* point, never automatic — matches the existing
  `debug_toolbar`/`qa_helpers` convention this repo already trusts. Should **not** also gate inside
  the view with `if not settings.DEBUG: raise Http404`: that would be redundant given routing-level
  gating, and it is exactly the trap that breaks reachability under pytest, where `DEBUG` is forced
  `False` (see above). Recommend an additional `@staff_member_required` (or `is_staff` check) on
  the view itself as cheap defense in depth against a downstream accidentally including it
  unconditionally — consistent with the rest of the educator interface being staff-only, and with
  Wagtail's styleguide relying on admin-login rather than `DEBUG` alone.
- **Multi-tenant / site-aware:** no exposure, because the page takes no site-scoped querysets —
  every component's example data is static context, sidestepping `SiteAwareManager` entirely. It
  still passes through whatever site-resolution middleware is global, which is already satisfied
  in dev (every other page depends on it too).
- **Usable by spec 12's Playwright check:** **not directly**, because the URL literally does not
  exist while `settings.DEBUG` is forced `False` during the test run — see next option.

### B. An opt-in, contrib-style app/URL include (Wagtail-styleguide shape)

A separate installable sub-package (e.g. `panel_framework.contrib.reference` or a whole new app)
that a downstream adds to `INSTALLED_APPS` and its own `urls.py`, gated by staff-login rather than
`DEBUG`, so it can stay mounted in production the way Wagtail's styleguide does.

- **Downstream visibility:** good, and arguably better long-term (works even where a team wants a
  living reference in a staging deploy where `DEBUG` is off).
- **Theme overrides:** same as A — no difference, it is still ordinary cotton resolution.
- **Security:** relies entirely on the login/staff check rather than `DEBUG`; one more thing that
  can be misconfigured (forgetting to protect the view means it is reachable in production, full
  stop, unlike A where forgetting the `DEBUG` guard costs nothing because the framework's own
  `urls.py` still isn't included by an accidentally-permissive host — this only holds if the
  gating lives in the *view*, so B's risk surface is strictly larger than A's).
- **Usability by spec 12:** same reachability problem as A if gated by `DEBUG`; solves it if gated
  by login only, but that means writing and maintaining a whole extra installable surface (new app
  label, migrations if any exist, an entry in `docs/app_structure.md`) for one dev page — more
  ceremony than the spec's scope ("a dev-only page ... so a downstream developer can see the kit")
  asks for, and heavier than every other spec in this effort.

### C. A test-only URLconf used by pytest/Playwright

Exactly `panel_framework`'s existing rig: a view + template registered only in
`panel_framework/tests/urls.py` (or a sibling test-only module) and only reachable when the
autouse `_use_panel_test_urls` fixture points `ROOT_URLCONF` there — the pattern every other
`panel_framework` Playwright test already depends on.

- **Downstream visibility:** none. A downstream developer running `manage.py runserver` never sees
  it; it only exists inside a pytest process. Fails the idea's "so a downstream developer can see
  the kit" half of the requirement outright.
- **Theme overrides:** fine, for the same reason as A — the wrapper template's location doesn't
  change how `cotton/*.html` resolves.
- **Security:** no exposure at all, by construction — the strongest of any option, at the cost of
  the visibility goal above.
- **Usability by spec 12:** the only option that works today without extra plumbing —
  `live_server` + the existing `ROOT_URLCONF` override reach it exactly like every other
  `panel_framework` Playwright test.

### D. A management command rendering static HTML

`manage.py render_component_reference > out.html`, dumping every component/state to a flat file
(no Django request in the loop) for a developer to open locally or for CI to archive as an
artifact.

- **Downstream visibility:** works, but asks a developer to run a command and open a file rather
  than browse a URL — a step below A or B, and it is a step *outside* the running app, so it can go
  stale silently (nothing forces it to be regenerated).
- **Theme overrides:** works only if the command runs Django's template engine with the same
  `INSTALLED_APPS`/theme configuration as the real app (straightforward, since a management command
  shares settings) — no real disadvantage here.
- **Security:** no web exposure ever, the safest option by construction (like C).
- **Usability by spec 12:** weak. Several inventoried components are explicitly interactive
  (toolbar with filter chips, tab bar, skeleton loading states, HTMX swaps other specs will add
  around this framework) — a flat HTML dump can't demonstrate a live HTMX state, a dark-mode
  toggle, or a real request/response cycle, and Playwright's `page.goto("file://...")` on a static
  dump loses request context (`csrf_token`, context processors) that some components may need.
  This option is weaker than A/C for the actual inventory in scope.

## Recommendation

**Ship the page as ordinary `panel_framework` code (view + template + static example context per
component/state, no DB queries), and register it twice: once behind `DEBUG` at the include point
for real downstream dev servers (Option A), and once, unconditionally, in `panel_framework`'s
existing test-only `root_urls.py`/`urls.py` for spec 12's Playwright check (Option C).** One view
function, one set of templates, two thin routings — not two competing implementations.

- Add `freedom_ls/panel_framework/urls.py` (the app's first) exporting one path, e.g.
  `component-reference/` → a view rendering every component inventoried in spec 4's "What is
  settled" section, in every state, from static example data (mirroring how `daisy-cotton`'s
  gallery and Wagtail's styleguide both use fixed, hand-authored example props rather than live
  DB rows). Do **not** add an internal `if not settings.DEBUG` guard in the view — gating lives
  only at the include point, so the same view can be mounted unconditionally in the test urlconf
  without a `settings.DEBUG` flip mid-test. Do add an `is_staff` check for defense in depth,
  matching the rest of the (staff-only) educator interface.
- Document in spec 4 (and the effort's upgrade notes, per spec 12's schema) that a downstream
  project wires it in exactly like `debug_toolbar`/`qa_helpers` are wired into `config/urls.py`
  today:
  ```python
  if settings.DEBUG:
      urlpatterns += [path("panel-framework/reference/", include("freedom_ls.panel_framework.urls"))]
  ```
- Register the same view at a path in `freedom_ls/panel_framework/tests/urls.py` (no `DEBUG`
  condition needed there — it's only ever reachable when a test's autouse fixture points
  `ROOT_URLCONF` at `tests.root_urls`, which never happens outside pytest). Spec 12's Playwright
  test then does what `test_data_table_panel_htmx.py` already does: `live_server` fixture,
  `page.goto(f"{live_server.url}/test-panel/.../component-reference/")`, `@pytest.mark.playwright`,
  the existing `storage_state` staff-login fixture to satisfy the `is_staff` check, and `expect()`
  assertions per component/state (dark mode via a query param or a second route, matching the
  effort's default-theme-and-dark-mode requirement, and the `daisy-cotton` gallery's own live theme
  switcher as prior art).
- One long page over one route per component (Wagtail styleguide's shape, and where
  `daisy-cotton` ended up too), so the URL surface stays trivial and the "every component in every
  state" instruction maps to one scrollable page a downstream developer or a single Playwright test
  can walk top to bottom, with an anchor or `data-testid` per component/state pair for the visual
  check to target.

This is the only combination that gets both audiences the idea and spec 12 ask for — a real,
theme-respecting page a downstream developer can load in a browser, and a URL spec 12's Playwright
suite can actually reach given `DEBUG` is forced off for the whole pytest run — without inventing a
second implementation or a new installable app the spec's scope doesn't ask for.

## Open questions the spec should still settle

- Exact route name/path and where in `docs/product/panel-framework.md` (spec 12) it gets
  documented for a downstream developer.
- Whether dark mode is a `?theme=dark` query param, a second route, or an in-page Alpine toggle
  (closest to `daisy-cotton`'s live switcher) — spec 12's polish pass needs to drive both without
  reloading state.
- Whether `is_staff` is enough or the page should also require the same organisation-scoping
  request attributes `SectionConfigBase.required_request_attrs` uses elsewhere in the framework
  (likely not, since the page takes no instance and no organisation).

status: ok
reason: researched via idea/roadmap/spec-1/spec-12 reading, panel_framework test infra (root_urls.py, conftest.py, playwright tests), config/urls.py + qa_helpers precedent, settings_dev.py's documented DEBUG-forced-False-under-pytest behaviour, and web prior art (django-pattern-library, wagtail.contrib.styleguide, storybook-django, daisy-cotton gallery); produced options + recommendation
