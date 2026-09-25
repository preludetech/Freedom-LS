# Research: the template contract

For spec 1 (`idea.md`'s settled item "Template contract": panels declare a template name and
context, a container renders them, no `get_content() -> str`, no string concatenation in views, no
`escape()` in Python, the semgrep TODO closed or consciously accepted; a downstream project must be
able to replace **and** wrap/extend a panel template).

## 1. Codebase: where HTML is built in Python today

### The `-> str` API is the whole surface

Every render method in `panel_framework` returns `str`, not `HttpResponse`, and every leaf method
does so via `render_to_string(...)` with a template path and a context dict — `Panel.render`,
`DataTablePanel.get_content`/`render`, `InstanceDetailsPanel.get_content`
(`freedom_ls/panel_framework/panels.py:31-127`), `DataTable.render`/`get_rows`
(`freedom_ls/panel_framework/tables.py:64-90`), and every `PanelAction`/`FormPanelAction` render
and error path (`freedom_ls/panel_framework/actions.py:30-107`, `:283-317`, `:329-337`). The one
consumer override, `CohortCourseProgressPanel.get_content`
(`freedom_ls/educator_interface/views.py:717-812`, deleted by this spec per `idea.md` line 9), also
only ever calls `render_to_string`. So **no app code anywhere hand-builds a `<tag>` string** — the
`-> str` signature is a real constraint (`Panel.get_content(...) -> str` at
`freedom_ls/panel_framework/panels.py:26-29`), but nothing currently violates it by writing raw
markup byte-by-byte.

What the `-> str` contract *does* force, at the layer above a single panel, is string
**concatenation of already-rendered fragments** — the part idea.md means by "no string
concatenation in views":

- `InstanceView._render_flat` (`freedom_ls/panel_framework/views.py:90-102`):
  `title = f'<h1 id="instance-title">{escape(str(self.instance))}</h1>'`, then
  `panels_html = '<div class="space-y-6">' + "\n".join(rendered_panels) + "</div>"`, then
  `return title + "\n" + instance_actions_html + panels_html`.
- `InstanceView._render_tabbed` (`:104-141`) repeats the same `escape()` + f-string title, this
  time followed by a `render_to_string` call for the tab bar rather than a join.
- `panel_framework_view`'s out-of-band bundle (`freedom_ls/panel_framework/views.py:663-736`):
  six independently `render_to_string`'d fragments (`main_html`, `breadcrumb_html`, `sidebar_html`,
  `title_html`, `document_title_html`, `announcer_html`) plus
  `extra_oob_html = "".join(render_to_string(t, {"oob": True}, request=request) for t in
  getattr(request, "panel_extra_oob", []))` (`:718-721`), all finally `+`-concatenated into one
  `HttpResponse(...)` body (`:728-736`).

So the concatenation is always of *already-escaped-or-safe* fragments (each produced by
`render_to_string`, itself autoescaping its own context), never of raw field values — the one
exception being the direct `escape(str(self.instance))` calls, which are the two literal
`escape()`-in-Python call sites idea.md wants gone (`freedom_ls/panel_framework/views.py:100`,
`:131`). No `format_html` or `mark_safe` call exists anywhere in `panel_framework` or
`educator_interface`; every place a rendered string re-enters a template does so through
`{{ ... |safe }}` on the receiving end — `panel_container.html:8,14`, `main_content.html:2`,
`tab_container.html:26`, `tab_panels.html:3`, `instance_actions.html:4`, `list_refresh.html:10`.
That `|safe` chain is the real shape of today's contract: Python assembles a tree of pre-rendered
HTML strings and templates re-inject them unescaped, rather than a template ever including another
template *as a template*.

### The semgrep TODO, quoted in full

```
# TODO: Fix or figure out if we should worry
# Semgrep Finding: python.django.security.audit.xss.direct-use-of-httpresponse.direct-use-of-httpresponse
# Detected data rendered directly to the end user via 'HttpResponse' or a similar object. This bypasses Django's built-in cross-site scripting (XSS) defenses and could result in an XSS vulnerability. Use Django's template engine to safely render HTML.
# Semgrep OSS
```
(`freedom_ls/panel_framework/views.py:723-726`, immediately above the `HttpResponse(main_html +
breadcrumb_html + ... + extra_oob_html)` return at `:728-736`.) The rule is generic
(`direct-use-of-httpresponse`) and fires on the *pattern* — building an `HttpResponse` body by
string concatenation outside the template engine — not on a proven injection, since every
concatenated piece already passed through `render_to_string` autoescaping. Closing it "for real"
means the OOB bundle becomes one `render_to_string` call over one template that includes the six
fragments as *context variables* rendered through `{{ }}` (autoescape on) rather than pasted in as
already-safe strings, or is accepted with a comment recording why the concatenation is of trusted,
already-rendered fragments only — either satisfies idea.md's "closed or consciously accepted".

### Templates a downstream might have overridden

Everything under `freedom_ls/panel_framework/templates/panel_framework/partials/`:
`action_button.html`, `announcer.html`, `breadcrumbs.html`, `delete_confirmation.html`,
`document_title.html`, `instance_actions.html`, `instance_details_panel.html`, `list_refresh.html`,
`list_view.html`, `main_content.html`, `modal_form.html`, `panel_container.html`,
`sidebar_nav.html`, `tab_container.html`, `tab_panels.html` — plus the consumer's own
`freedom_ls/educator_interface/templates/educator_interface/interface.html`,
`partials/organisation_switcher.html`, `partials/course_progress_panel.html` (deleted by this
spec) and its `data-table-cells/*.html`.

One finding worth flagging directly: `freedom_ls/educator_interface/templates/educator_interface/`
already contains `partials/panel_container.html`, `partials/instance_details_panel.html` and
`partials/list_view.html` — near-identical copies of the three `panel_framework` templates of the
same base name, but namespaced under `educator_interface/` instead of `panel_framework/`. A repo
grep finds **zero** `render_to_string`/`{% include %}` references to any of the three
(`freedom_ls/panel_framework` and `freedom_ls/educator_interface` both searched). They are dead —
not a working override (wrong namespace to shadow anything; `panel_container.html`'s loader path is
literally `panel_framework/partials/panel_container.html`, so a same-named file under
`educator_interface/partials/` shadows nothing) and not currently wired to anything. Read
charitably, they are a stub of exactly the "consumer wants to tweak the container markup" case this
spec's template contract needs to answer for real, abandoned because there was no path to do it.
Whether to delete them or resolve what they were for is worth a line in the spec.

### Theme shadowing by template path (how "replace" already works)

`TEMPLATES[0]` (`config/settings_base.py:175-208`) uses a single cached loader wrapping, in order,
`django_cotton.cotton_loader.Loader`, `filesystem.Loader` (searches `TEMPLATES[0]["DIRS"]`), then
`app_directories.Loader` (searches every `INSTALLED_APPS` entry's `templates/` in
`INSTALLED_APPS` order). `configure_theme()` (`freedom_ls/base/theming.py:46-95`, wired at
`config/settings_base.py:258-263`) resolves `FLS_THEME` against `FLS_THEMES_DIRS` (downstream's
own `BASE_DIR / "themes"` listed *before* the FLS package's own `themes/`,
`config/settings_base.py:54-57`) and **prepends** the active theme's `templates/` dir to
`TEMPLATES[0]["DIRS"]`. Since the filesystem loader runs before `app_directories`, a theme file at
the *same relative path* as an app template wins unconditionally — full replacement by path, not
composition. This is namespace-aware but flat: cotton components resolve to `cotton/<name>.html`
with no app prefix, but "pages and partials keep their app namespace"
(`claude_plugins/fls-dev/resources/templates_and_cotton.md:19-20`), so a theme (or a downstream app
placed earlier in `INSTALLED_APPS`) shadows `panel_framework/partials/panel_container.html` by
shipping a file at that exact path.

The repo already relies on the `INSTALLED_APPS`-order variant of this same mechanism, not just
theme dirs: `allauth` is placed at the very end of `INSTALLED_APPS`
(`config/settings_base.py:139-141`) "because we need to override many of its templates", and
`freedom_ls/base/templates/allauth/layouts/{base,manage,entrance}.html` and
`allauth/elements/button.html` shadow allauth's own templates at those same paths. That is the
project's live precedent for "replace a third-party template by same-path shadowing" — and it is
exactly the mechanism that cannot also *extend* the shadowed original (see §3): a file at
`allauth/layouts/base.html` cannot `{% extends "allauth/layouts/base.html" %}` to reach allauth's
own version, because the loader resolves that name to the shadow itself again.

Contrast `freedom_ls/base/templates/_base_interface.html` (the shell `panel_framework` renders
into, shared with the learner interface — the open question at `idea.md` line 60), which is not
name-shadowed by anything but is already built the *other* way: one template with named
`{% block %}` regions (`sidebar_content`, `sidebar_presentation`, `header_extra`, `content`,
`footer`, etc., `freedom_ls/base/templates/_base_interface.html:150-261`) that a consumer extends
and overrides selectively. That is the idiom already in use elsewhere in this codebase for
"downstream wraps/extends, does not have to replace wholesale" — see §3.

## 2. Prior art: "object declares template + context, container renders"

### Wagtail's `laces` `Component` (the idea.md-endorsed prior art, PyPI: `laces`)

A `Component` subclass sets `template_name` and optionally overrides
`get_context_data(parent_context)`, which receives the calling template's context dict/`Context`
and returns the dict to render `template_name` with — subclasses call
`super().get_context_data(parent_context)` and augment rather than replace it, so context building
composes across a subclass chain. `render_html(parent_context=None)` is the render entry point and
must return a `SafeString` if it returns markup (autoescaping is not implicit — the component author
opts in). Wagtail's own `{% component %}` tag (`wagtailadmin_tags`) is the container: it takes an
*object* and forwards the calling context, so the container doesn't need to know the component's
concrete type. Crucially, **the interface is duck-typed, not inheritance-gated** — "any object
implementing this API is valid" — so a downstream project's own class can stand in for a panel
without subclassing anything panel_framework ships. Extension for a single component happens the
ordinary Django way: `template_name`'s own template is free to `{% extends %}` any other template
by a *different* name, and `get_context_data` composing through `super()` is how a subclass adds to
what it renders without re-declaring the whole template.
[docs.wagtail.org/en/stable/extending/template_components.html](https://docs.wagtail.org/en/stable/extending/template_components.html)

### django-components

Split the same way: `get_template_name()` (or a `template_name` attribute) selects the template,
`get_context_data()` (renamed from `get_template_data()`/`context` across versions — 0.17 renamed
`Component.context`/`Component.template` to `get_context_data`/`get_template_name`) supplies its
data. Slots are the composition primitive beyond plain block-override: a component declares named
slot holes in its template, and a caller (including a subclassing consumer) fills them per-render
rather than only at definition time, which is a strictly more dynamic version of Django's
block-at-extend-time model. [django-components.github.io](https://django-components.github.io/django-components/latest/overview/welcome/)
— fetch of that exact page 404'd during this research; the API above is corroborated by
[pypi.org/project/django-components](https://pypi.org/project/django-components/0.60/) and search
results citing the 0.17 rename.

### Django's own form/widget renderer — the closest prior art already in the stack

`Widget.template_name` (a class attribute, e.g. `django/forms/widgets/text.html`) and
`Widget.get_context(name, value, attrs)` are exactly the split idea.md wants: template selection is
a class attribute, context is a method, and a subclass overrides one or the other independently —
`class MyCustomWidget(forms.TextInput): template_name = "my_custom_templates/my_input.html"` needs
no change to `get_context`. Project-wide override-by-path (the theme-shadow move in §1) is possible
here too, but only with `FORM_RENDERER = "django.forms.renderers.TemplatesSetting"`, which routes
widget template lookup through the *project's* `TEMPLATES` engine instead of a renderer-owned,
isolated template directory (`django/forms/templates`) that ignores project `TEMPLATES` settings
entirely by default. That default isolation is notable: Django's own framework code deliberately
does **not** let a project's ordinary template loaders reach into form-widget templates unless the
project opts in — the opposite default from `panel_framework`, where every fragment already lives
in the ordinary app-templates search path and is shadowable today.
[docs.djangoproject.com/en/6.0/ref/forms/renderers/](https://docs.djangoproject.com/en/6.0/ref/forms/renderers/)

### django-cotton: components are not the right unit for a *panel*

`<c-component is="...">` / `:is="var"` gives cotton a dynamic-name escape hatch, but the ordinary
`<c-name>` tag form resolves `name` to a literal file at `cotton/<name>.html` at **parse time** —
there is no cotton-native way for `panel_framework` to say "render whichever component this Panel
instance names" without either the `is=` dynamic form (which the project's own tooling — the
`cotton-props` VS Code extension referenced in search results — explicitly cannot index/validate)
or falling back to `render_to_string`/`{% include %}` with a Python-computed template name, which is
what `panel_framework` already does. Cotton's `cotton/` namespace is also flat (§1), so it cannot
express the app-namespaced override path (`panel_framework/partials/...`) the rest of the framework
relies on. This is consistent with `idea.md`'s framing: cotton is right for presentational widgets
(`c-data-table`, `c-modal`, `c-button-group`) that panel templates *call into*, not for the panel
dispatch layer itself, which needs a Python-side registry of name → template/class exactly because
the name is only known at request time (which panel, which tab, which action).
[django-cotton.com/docs/components](https://django-cotton.com/docs/components),
[pypi.org/project/django-cotton](https://pypi.org/project/django-cotton/)

## 3. The "extend a template of the same name" problem

### The problem, stated against this codebase

A downstream file at `panel_framework/partials/panel_container.html` (shadowing
`freedom_ls/panel_framework/templates/panel_framework/partials/panel_container.html` by path, per
§1) cannot `{% extends "panel_framework/partials/panel_container.html" %}` to reach the *original* —
the loader resolves that name to the same shadow file again, either infinite-recursing or (with the
cached loader) hitting the already-parsed shadow. The project's own `allauth` shadows
(`freedom_ls/base/templates/allauth/layouts/base.html` etc., §1) are full rewrites for exactly this
reason — there was no original to extend from that path.

### Known solutions, and what's idiomatic for a distributable app

- **Django's own documented trick** (`docs.djangoproject.com` "How to override templates"): the
  loader "does not consider the already loaded override template" when resolving `{% extends %}`
  *inside that same override*, so `templates/admin/base_site.html` can itself say
  `{% extends "admin/base_site.html" %}` and reach the app's original. This works but is
  loader/config-fragile — it depends on `DIRS` being searched before `APP_DIRS`
  (true here, since the cached loader puts `filesystem.Loader` before `app_directories.Loader`,
  `config/settings_base.py:181-189`) and on there being exactly one other candidate. It is a trick
  for *project-level* overrides of framework templates, not something a distributable app can rely
  on a downstream consumer discovering.
  [docs.djangoproject.com/en/6.0/howto/overriding-templates/](https://docs.djangoproject.com/en/6.0/howto/overriding-templates/)
- **`django-apptemplates`**: a third-party loader adding an `app_label:template/path.html` syntax
  to `{% extends %}`/`{% include %}`, so an override can name the *specific app's* copy
  unambiguously instead of relying on search order. Solves the ambiguity but adds an
  `INSTALLED_APPS`/`TEMPLATES` dependency a distributable app cannot assume a host project has
  installed. [github.com/bittner/django-apptemplates](https://github.com/bittner/django-apptemplates)
- **Django admin's actual pattern — a thin, dedicated leaf extending a same-package base under a
  *different* name**: `django/contrib/admin/templates/admin/base_site.html` is
  `{% extends "admin/base.html" %}` plus three near-empty block overrides (`title`, `branding`,
  `nav-global`); "every other template extends `base_site.html`", never `base.html` directly. A
  project overriding `admin/base_site.html` at its own `templates/admin/base_site.html` is
  overriding a file that was *designed to be thin and overridden*, and reaches all the real
  structure by extending `admin/base.html` — a different, non-shadowed name. No loader trick, no
  extra package: the indirection is baked into which name is "the one you override" versus "the one
  with the content". This is the idiomatic answer for a **shared/default** template many panels
  render through (e.g. `panel_container.html`): split it into a thin nominal leaf and a
  differently-named base carrying the real markup, so overriding the leaf's *name* still reaches
  the base's structure via an ordinary, unambiguous `{% extends %}`.
- **`template_name` as a per-class attribute (Wagtail `laces`, Django `Widget`, §2)**: solves a
  *different* case — one specific `Panel` subclass wanting its own look, not the shared default.
  Since `template_name` is data on the class, not something resolved by path convention, a
  downstream subclass just points it at a new file under its own app's namespace, and that new file
  is free to `{% extends %}` the *original* `panel_framework/partials/panel_container.html` (a name
  it never shadowed) to reuse the framework's structure and override one block. This composes with
  the base/leaf split above rather than replacing it: base/leaf answers "how do I extend the
  framework's shared default", `template_name` answers "how does one panel opt out of the shared
  default entirely".

`freedom_ls/base/templates/_base_interface.html` (§1) already demonstrates the block half of this
for the page shell — it is not itself a shadow target, but its `{% block sidebar_content %}` /
`{% block content %}` / `{% block header_extra %}` etc. are how `educator_interface/interface.html`
extends and fills it today, which is the same composition idiom the panel templates lack.

## 4. htmx fragment rendering and Django 6 template partials

Django 6.0 (current stack: "Python 3.13+, Django 6.x" per `CLAUDE.md`) merged
`django-template-partials` into core (GSoC project by Farhan Ali, mentored by Carlton Gibson,
ticket #36410). The Django Template Language now has `{% partialdef name %}...{% endpartialdef %}`
to define a named fragment inside a full template file, and `{% partial name %}` to render it
in-place. A partial can also be addressed from *outside* its defining template via
`template_name#partial_name`, accepted anywhere a template name is accepted:
`get_template()`, `render()` (the `django.shortcuts.render` shortcut), `{% include %}`, and other
template-loading tools — "enabling more modular and maintainable templates without needing to split
components into separate files." A migration guide covers moving off the third-party package.
[docs.djangoproject.com/en/6.0/releases/6.0/](https://docs.djangoproject.com/en/6.0/releases/6.0/)

This is directly relevant to the htmx fragment-refresh idiom idea.md names as "copy-pasted three
times" (the `HX-Target`-equals-`table_id` short-circuits in `DataTablePanel.render`
(`freedom_ls/panel_framework/panels.py:69-75`), `_render_list_view_content`
(`freedom_ls/panel_framework/views.py:423-432`), and `CohortCourseProgressPanel.render`
(`freedom_ls/educator_interface/views.py:814-817`, deleted with the rest of that panel)). Today each
of those three sites keeps two *separate* code paths — "just the fragment" vs. "the fragment plus
its surrounding chrome" — by calling the panel's `get_content`/render logic twice under different
conditions, because there is no way to name "the inner bit of this template" independently of the
outer wrapper. `template_name#partial_name` is exactly the primitive that removes that duplication
*if* panel templates are restructured as one file with a `{% partialdef %}` around the
targeted-refresh region: the outer render addresses the whole template, a targeted htmx refresh
addresses `panel_framework/partials/panel_container.html#body` (or similar). Whether panel templates
should expose such partials is a live design question this spec should answer — it would mean each
panel's `template_name` template *itself* declares which sub-region is independently refreshable,
which fits the "panel declares template + context" contract better than the current split-by-Python-
condition approach, and is more `{% extends %}`-friendly than a separate, differently-named
"refresh-only" template per panel kind. Django's own release notes and the `partialdef`
tag-reference page do not mention HTMX by name — the fit is inferred from the mechanics
(named-region-addressable-by-path), not documented Django guidance.

## 5. Pitfalls

- **Context leakage between nested panels — currently avoided, and worth keeping that way.**
  Every `render_to_string` call in `panel_framework` builds a **fresh** context dict
  (`{"title": ..., "content": ..., ...}`, never the caller's own context passed through), so one
  panel's render cannot see another's variables. The one exception:
  `modal_form.html`'s `{% include "partials/form.html" %}`
  (`freedom_ls/panel_framework/templates/panel_framework/partials/modal_form.html:13`) has no
  `only` and no explicit `with`, so it inherits the *ambient* context of the enclosing
  `render_to_string` call (`form`, `form_title`, `form_url`, `variant`, `label`, `submit_buttons`,
  `modal_open`) into `partials/form.html`, which only needs `form`. Harmless today because nothing
  in `partials/form.html` collides with those names, but it is inconsistent with the project's own
  established convention for isolating included-template context: `freedom_ls/reports/templates/`
  uses `{% include "..." with ... only %}` throughout (e.g.
  `reports/templates/reports/report.html:74-79`, `reports/templates/reports/partials/at_a_glance.html:33,39`) —
  precisely so a partial's inputs are enumerated at the call site rather than implied by whatever
  happens to be in scope. If the template contract moves toward panels including
  sub-templates directly (rather than each panel's content being computed as an independent
  Python string), `{% include %}` calls introduced by that shift should default to `only` to
  preserve the current no-leakage property, which is currently achieved by accident (fresh dicts
  per `render_to_string` call) rather than by an explicit rule.
- **Performance of many small renders.** Every panel, every action button, the instance title
  block, the tab bar, and the OOB bundle's six fragments are each an independent
  `render_to_string(..., request=request)` call. Passing `request=request` means each one re-runs
  every context processor in `TEMPLATES[0]["OPTIONS"]["context_processors"]`
  (`config/settings_base.py:191-202` — auth, messages, `site_config`, `signup_policy`,
  `can_access_educator_interface`, `analytics_enabled`, `posthog_config`, `google_tag_config`, CSP)
  once per fragment. A page with, say, four panels plus tabs plus the OOB bundle is on the order of
  ten-plus independent context-processor passes for one HTTP response. The `cached.Loader`
  (`config/settings_base.py:182-189`) means template *parsing* is cached, so this is a
  context-building cost, not a compilation cost — real but not obviously worth optimising away
  pre-emptively; worth a note if the contract's design multiplies the fragment count further (e.g.
  a `{% partialdef %}`-per-region approach, §4, would not add renders, but a "every block is its own
  `render_to_string`" approach would).
- **Autoescape is on throughout, and nothing currently turns it off.** No `{% autoescape off %}` in
  `panel_framework` or `educator_interface` templates (the one project-wide occurrence is
  `freedom_ls/accounts/templates/emails/base_email.txt`, an unrelated plain-text email context). The
  `|safe` filter is the mechanism the current contract relies on instead (§1) — every rendered
  fragment is trusted at the point it is spliced into its parent via `{{ content|safe }}`. That is
  safe *only* because the only producer of `content` is `render_to_string` against a fixed
  template, never raw string interpolation of user data. A template-object contract that lets a
  downstream `Panel` subclass supply an arbitrary `template_name` string does not change this risk
  shape (the string is a *path*, resolved by Django's loader, not markup), but it does mean the
  framework can stop needing `|safe` at all once panels are rendered as real nested templates
  (`{% include panel.template_name with ... %}`) rather than as pre-rendered strings passed through
  a `content` context variable — at that point Django's ordinary per-variable autoescaping inside
  the panel's own template is the only escaping mechanism in play, and the current `|safe` call
  sites in `panel_container.html`, `main_content.html`, `tab_container.html`, `tab_panels.html`,
  `instance_actions.html`, and `list_refresh.html` (six sites, §1) either go away or narrow to the
  genuinely-necessary cases.

status: ok
