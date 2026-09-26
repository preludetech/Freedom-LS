# `django.contrib.admin.utils` field helpers — what to vendor, and the home-grown resolver they'd replace

Researched against the idea's settled "field resolution" point: vendor the label and display
helpers from `django.contrib.admin.utils` into `freedom_ls/panel_framework` rather than import
them. Django source read from
`.venv/lib/python3.13/site-packages/django/contrib/admin/utils.py` (Django 6.0, matching this
project's pinned version).

## 1. Today's home-grown resolver

The resolver the idea refers to is `InstanceDetailsPanel._resolve_field`,
`freedom_ls/panel_framework/panels.py:98-114`. It is the only field/label resolver in the
framework — `DataTable` columns (`tables.py`) take an explicit `header` string per column, so
they never introspect a field for a label, and `base/templatetags/data_table_tags.py`'s
`getattr_str` filter resolves a table **cell value** (not a label) via a lenient
`getattr`-per-`.`-segment loop that swallows `AttributeError`/`TypeError` into `None` — a
different, more forgiving mechanism than `_resolve_field`, and out of scope for this vendoring
(no label work happens there).

```python
def _resolve_field(self, field_path: str) -> tuple[str, object]:
    parts = field_path.split(".")
    obj: Model = self.instance
    for part in parts[:-1]:
        related = getattr(obj, part)
        if not isinstance(related, Model):
            raise ValueError(f"Expected Model at '{part}', got {type(related)}")
        obj = related
    field_name = parts[-1]
    field = obj._meta.get_field(field_name)
    label = str(getattr(field, "verbose_name", field_name)).title()
    value = getattr(obj, field_name)
    return label, value
```

Behaviour, verified by reading the code and `panel_framework/tests/test_tab_panels.py`
(`TestInstanceDetailsPanel`, lines 102-137):

- **Dot notation, not `__`.** `"user.first_name"` traverses relations by splitting on `.`, and
  each intermediate segment must resolve to a `Model` instance or `_resolve_field` raises
  `ValueError` (`test_dot_notation_through_a_non_relation_raises`). This is the opposite
  convention from Django's own `__` (`LOOKUP_SEP`) used throughout the ORM, the admin, and this
  project's own `sort_field` derivation in `DataTable._prepare_columns`, which replaces `.` with
  `__` for that reason.
- **`obj._meta.get_field(field_name)` unconditionally.** This is a direct call to Django's model
  meta API, not wrapped in a `try`/`except FieldDoesNotExist`. It only succeeds for a real
  concrete model field (or a relation field). A `@property`, a plain method, or an annotation
  added via `.annotate()` all raise `django.core.exceptions.FieldDoesNotExist`, uncaught, which
  is a 500 — this is the "raises a 500 for a property, a method or an annotation" the idea names.
  Today's three call sites (below) only ever declare real concrete fields, so the bug is latent,
  not yet hit in production code, but any future `fields = [...]` entry naming a property or a
  method reproduces it immediately, and nothing validates the list ahead of a request (the idea's
  separate, related debt item: "Nothing validates a panel's declared fields until a request hits
  it").
- **`.title()` mangles acronyms and multi-word verbose names.** Python's `str.title()`
  capitalises the first letter of *every* word and lowercases everything else. Applied to a
  `verbose_name` of `"SAT score"` it produces `"Sat Score"`; applied to `"URL"` it produces
  `"Url"`; applied to `"first name"` (the normal case, and the only case exercised in this
  project's own fields today) it happens to produce the correct `"First Name"`, which is why the
  bug has not surfaced yet. `django.utils.text.capfirst`, by contrast, only upper-cases the first
  character and leaves the rest of the string untouched, so `"SAT score"` stays `"SAT score"`, and
  `"first name"` becomes `"First name"` (Django's own admin convention is sentence case, not
  title case — see §5).
- **No choices handling.** `value = getattr(obj, field_name)` returns the raw stored value. A
  `CharField(choices=...)` shows the stored code, not `get_FOO_display()`'s human label. Nothing
  in the framework calls `get_FOO_display()` or reads `field.flatchoices`.
- **No empty-value placeholder.** `instance_details_panel.html`
  (`freedom_ls/panel_framework/templates/panel_framework/partials/instance_details_panel.html`)
  prints `{{ field.value }}` raw in both the mobile `<dl>` and desktop `<table>` layouts. `None`
  renders as an empty cell; there is no placeholder (Django admin's default is an em dash,
  `EMPTY_VALUE_DISPLAY = "-"` / the `AdminSite.empty_value_display` override).
- **No type-aware formatting.** A `DateTimeField` value goes through Django's ordinary template
  auto-escaping and `str()`/repr formatting, not `django.utils.formats.localize`, so it will not
  respect `USE_L10N`/locale date formats the way the admin does. A `BooleanField` renders
  `"True"`/`"False"` as plain text, not the admin's tri-state icon convention.

### Call sites

Three subclasses declare `fields`, all of them real concrete model fields today (properties,
methods, and annotations are as-yet unexercised — the crash is real but untriggered):

- `LearnerDetailsPanel` (`freedom_ls/educator_interface/views.py:225-230`) —
  `["user.first_name", "user.last_name", "user.email"]`, three dot-path traversals through the
  learner's `user` FK.
- `CohortDetailsPanel` (`freedom_ls/educator_interface/views.py:248-251`) — `["name"]`, editable
  with `CohortForm`.
- `CourseDetailsPanel` (`freedom_ls/educator_interface/views.py:1032-1033`) —
  `["title", "dashboard_category"]`. `dashboard_category` is a `ForeignKey` to `CourseCategory`
  (`freedom_ls/content_engine/models/courses.py:151`), so `_resolve_field` returns the related
  model instance as `value` and the template renders its `__str__`; there is no choices field or
  boolean field among today's declared fields, so those gaps are also latent rather than
  currently visibly broken.

`InstanceDetailsPanel` itself is `freedom_ls/panel_framework/panels.py:78-127`; its only test
coverage is `freedom_ls/panel_framework/tests/test_tab_panels.py:102-137`, which asserts label
text and the dot-path `ValueError`, not choices, empty values, or type formatting (none of that
exists to test yet).

## 2. What Django's helpers actually do, function by function

All of the following are read from
`.venv/lib/python3.13/site-packages/django/contrib/admin/utils.py`.

### `label_for_field(name, model, model_admin=None, return_attr=False, form=None)` — lines 354-417

The function the idea is really asking to vendor. Order of resolution:

1. Try `_get_non_gfk_field(model._meta, name)` (see below). If it resolves to a real field,
   `label = field.verbose_name`, falling back to `field.related_model._meta.verbose_name` for a
   reverse relation (`ForeignObjectRel` has no `verbose_name`).
2. If that raises `FieldDoesNotExist`:
   - `name == "__str__"` → `label = str(model._meta.verbose_name)`, `attr = str`.
   - else, resolve `attr` in priority order: `callable(name)` (name is already a function) →
     `hasattr(model_admin, name)` → `hasattr(model, name)` (this is how a `@property` or a plain
     method defined on the model itself is found) → `form and name in form.fields` → finally
     `get_fields_from_path(model, name)[-1]` for a `__`-separated related-field path (this is
     what makes `"cohort__name"` work as a label source; it raises `FieldDoesNotExist` or
     `NotRelationField` for anything else, and only then does Django raise `AttributeError` with
     a message naming the model, the model_admin class if given, and the form class if given —
     i.e. Django's own failure mode for an unresolvable name is a clear `AttributeError`, not a
     bare `FieldDoesNotExist`/`500` with no message).
   - Once `attr` is resolved: `attr.short_description` wins if present (the `@admin.display`
     convention, see below); then `isinstance(attr, property) and attr.fget.short_description`
     (a property built the old way, by wrapping a function already carrying
     `short_description`, not the `@property` decorator syntax used in this codebase); then
     `callable(attr)` → `pretty_name(attr.__name__)` (`django.forms.utils.pretty_name`, which
     does `name.replace("_", " ").capitalize()` — capitalises only the first character, same
     spirit as `capfirst` but via `str.capitalize()`, which differs from `capfirst` in that it
     also *lowercases* the rest of the string, so `pretty_name("URLField")` → `"Urlfield"`; this
     matters only for callables/methods, not for `verbose_name`-backed fields, since those use
     `capfirst` only at render time via `contrib.admin`'s own templates, not inside
     `label_for_field` itself — `label_for_field` returns `field.verbose_name` **unmodified**,
     lower-case and all; capitalisation happens later, in the admin's `result_headers()`/
     `admin_list.py` templatetags, not in `utils.py`); a lambda gets the literal label `"--"`.
   - Otherwise `label = pretty_name(name)`.
3. `_get_non_gfk_field` can also raise `FieldIsAForeignKeyColumnName` (an `<fk>_id` attname) — in
   that branch `label = pretty_name(name)`, `attr = name` (the raw string, not a resolved
   attribute).
4. Returns `label` alone, or `(label, attr)` if `return_attr=True`.

**Imports/dependencies:** `django.forms.utils.pretty_name`,
`django.core.exceptions.FieldDoesNotExist`, this module's own `_get_non_gfk_field`,
`get_fields_from_path`, `NotRelationField`. **No import of anything under `contrib.admin`
itself** other than the `model_admin` and `form` *parameters*, which are optional and only
consulted via `hasattr`/`getattr` — nothing about `label_for_field`'s logic requires a
`ModelAdmin` instance; it degrades gracefully to `None`. This is the one function safe to vendor
essentially verbatim, dropping only the `model_admin`/`form` parameters (see §2 rewrite notes)
since the framework has no `ModelAdmin` or Django `Form` to consult — panels resolve against a
model and an instance only.

### `lookup_field(name, obj, model_admin=None)` — lines 290-322

Given an already-fetched **instance** `obj` (not a model class), resolves `(field, attr, value)`:

1. `_get_non_gfk_field(obj._meta, name)` succeeds → `f = field`, `attr = None`,
   `value = getattr(obj, name)`.
2. Otherwise: `callable(name)` → call it with `obj`; `hasattr(model_admin, name)` → call the
   admin's method with `obj`; else `getattr(obj, name, sentinel)` — if that's callable, call it
   with no args (a bound method on the instance, e.g. `obj.get_absolute_url`); if it's a
   dot-path-like string that isn't found directly, walks `name.split(LOOKUP_SEP)` (i.e. `__`, not
   `.`) against `obj`, returning `(None, None, None)` if any segment is missing (Django's
   graceful "field vanished, skip it" case, used by the admin changelist when a lookup 404s
   rather than 500s) rather than raising.
3. If `model_admin` has a `model` attribute and that model has the attribute `name`, `attr` is
   re-pointed at the *class* attribute (used later by `label_for_field`-adjacent code to find
   `short_description` on an unbound method/property).

This is the counterpart the vendored code needs for **value** resolution to match
`label_for_field`'s **label** resolution — same `_get_non_gfk_field` gate, same `__`-vs-`.`
convention, same "missing means `None`, not an exception" behaviour for anything past the first
`_get_non_gfk_field` failure. No `contrib.admin` import beyond the optional `model_admin`
parameter, used only via `hasattr`/`getattr`.

### `display_for_field(value, field, empty_value_display, avoid_link=False)` — lines 432-470

Given a resolved `value` and the model `field` object (not name), and the site's placeholder
string:

- `field.name == "password" and field.model == get_user_model()` → renders the password as a
  hash via `django.contrib.auth.templatetags.auth.render_password_as_hash` (irrelevant to a
  general panel framework, and a `contrib.auth` import, not `contrib.admin`, but still
  admin-flavoured behaviour worth deliberately dropping rather than vendoring).
- `field.flatchoices` truthy → `dict(field.flatchoices).get(value, empty_value_display)`, with a
  `TypeError` fallback for unhashable choice values via `django.utils.hashable.make_hashable`.
  This is the choices-to-display-label behaviour the idea calls out as currently missing.
- `isinstance(field, models.BooleanField)` → `_boolean_icon(value)`, imported **inside the
  function** from `django.contrib.admin.templatetags.admin_list` — this is the one genuinely
  `contrib.admin`-coupled branch: `_boolean_icon` renders an `<img>` tag pointing at
  `admin/img/icon-yes.svg` / `icon-no.svg` / `icon-unknown.svg`, static files that ship inside
  `django.contrib.admin`'s own `static/admin/img/` directory and are only collected if
  `django.contrib.admin` is in `INSTALLED_APPS`. A distributable framework cannot depend on those
  assets existing.
- `value in field.empty_values` → `empty_value_display` (uses the field's own `empty_values`
  class attribute, e.g. `NOT_PROVIDED`/`None`/`""` depending on field type — this is the "empty
  values show a placeholder" behaviour, keyed off the *field's* definition of empty, not a
  hard-coded list).
- Type dispatch for `DateTimeField` (→ `formats.localize(timezone.template_localtime(value))`),
  `DateField`/`TimeField` (→ `formats.localize(value)`), `DecimalField` (→
  `formats.number_format(value, field.decimal_places)`), `IntegerField`/`FloatField` (→
  `formats.number_format(value)`), `FileField` (→ an `<a href>` to `value.url` unless
  `avoid_link`), `URLField` (→ an `<a href>` unless `avoid_link`), `JSONField` (→
  `json.dumps(..., cls=field.encoder)`, falling back to `display_for_value` on `TypeError`).
- Everything else falls through to `display_for_value(value, empty_value_display)`.

### `display_for_value(value, empty_value_display, boolean=False)` — lines 473-491

The value-only counterpart (used when there is no `Field` object — a callable's return value, a
property, an annotation): same `_boolean_icon` import for `boolean=True`; `value in
EMPTY_VALUES` (from `django.core.validators`, a broader constant than a specific field's
`empty_values`) → placeholder; `bool` → `str(value)`; `datetime`/`date`/`time` → localized via
`formats`; `int`/`Decimal`/`float` → `formats.number_format`; `list`/`tuple` → `", ".join(str(v)
for v in value)`; else `str(value)`.

This is the function that matters most for **properties, methods, and annotations**, since none
of those have a `Field` object to dispatch on — `display_for_field` is only reachable when
`lookup_field` returned a real field (`f is not None`); the admin's own rendering code
(`django.contrib.admin.templatetags.admin_list.items_for_result`, not in this file) branches on
`f is None` to call `display_for_value` instead. A vendored copy needs to preserve that same
branch, not just port `display_for_field`.

### `help_text_for_field(name, model)` — lines 420-429

Trivial: `_get_non_gfk_field` then `getattr(field, "help_text", "")`; empty string (not
`empty_value_display`) if the field can't be found or has none. No admin coupling at all.

### `_get_non_gfk_field(opts, name)` — lines 325-351

The shared gate for `label_for_field`, `lookup_field`, and `help_text_for_field`.
`opts.get_field(name)` (Django's ordinary `Model._meta.get_field`), then two admin-specific
exclusions layered on top:

- Generic foreign keys and reverse (`one_to_many`) relations are treated as **not found**
  (`raise FieldDoesNotExist()`) — "for historical reasons," per the docstring, the admin wants
  these routed through the callable/attribute fallback path in `label_for_field`/`lookup_field`
  rather than treated as a concrete field.
- An `<fk>_id`-style attname (`field.attname == name` for a non-m2m relation) raises the
  module's own `FieldIsAForeignKeyColumnName` rather than resolving to the relation field, so
  `"user_id"` is deliberately *not* treated the same as `"user"`.

Both exceptions are needed by any vendored copy that wants the same "properties, methods,
annotations, and `<fk>_id` attnames behave sensibly instead of crashing" outcome the idea asks
for — dropping either exclusion changes behaviour, not just implementation detail.

### `get_fields_from_path(model, path)` — lines 536-553

Splits `path` on `LOOKUP_SEP` (`__`, `django.db.models.constants.LOOKUP_SEP`), calls
`_meta.get_field` down the chain via `get_model_from_relation` (`field.path_infos[-1].to_opts.
model`, raising the module's `NotRelationField` if a non-final segment isn't a relation). This is
what makes `"cohort__name"` resolvable as a *label* source in `label_for_field`'s fallback branch
(step 2 above) — it is **not** consulted by `lookup_field`/`display_for_field` for the *value*,
which uses `LOOKUP_SEP`-split `getattr` chaining directly inline instead. No admin coupling; pure
`_meta` traversal.

### The `@admin.display` / `short_description` convention

`label_for_field` checks `attr.short_description` first (a plain attribute set on a function or
method — historically via manual assignment, `method.short_description = "..."`, and since
Django 2.1 also settable via the `@admin.display(description=..., boolean=..., ordering=...,
empty_value=...)` decorator, which is defined in `django/contrib/admin/decorators.py`, not
`utils.py`, and only sets these same plain attributes — `short_description`, `boolean`,
`admin_order_field` (Django's name for what the decorator argument calls `ordering`), and
`empty_value` — on the function object. `label_for_field` in this file only ever reads
`short_description`; it does not read `boolean`, `ordering`, or `empty_value` itself — those are
read elsewhere, by `display_for_value(..., boolean=...)`'s caller
(`admin_list.items_for_result`, outside this file) and by `ModelAdmin.get_ordering_field` (also
outside this file). A vendored copy that wants to honour `@admin.display(boolean=True)` on a
panel's declared method must read `getattr(attr, "boolean", False)` itself and route to a
boolean-style renderer; `utils.py` alone does not do this wiring, `contrib.admin`'s changelist
code does.

## 3. Size and rewrite scope for a faithful vendored copy

The full file is 623 lines, but most of it (`get_deleted_objects`, `NestedObjects`,
`construct_change_message`, `quote`/`unquote`, `lookup_spawns_duplicates`,
`build_q_object_from_lookup_parameters`, `model_format_dict`/`model_ngettext`) is changelist-
filter and delete-confirmation machinery irrelevant to field display. The functions actually
needed — `label_for_field`, `help_text_for_field`, `_get_non_gfk_field`,
`FieldIsAForeignKeyColumnName`, `get_fields_from_path`, `reverse_field_path` (only needed if
`get_fields_from_path` is reused as-is and `NotRelationField` propagates through it),
`get_model_from_relation`, `NotRelationField`, `lookup_field`, `display_for_field`,
`display_for_value` — total roughly **230-260 lines** including docstrings (lines 290-503 plus
the class/exception declarations at the top), i.e. well under half the file. `pretty_name` itself
is not in this file (`django.forms.utils`) and does not need vendoring — it is stable Django
public-surface-adjacent code (`name.replace("_", " ").capitalize()`), safe to import directly
since it carries no `contrib.admin` dependency.

What must be rewritten, not just copied:

- **The two `_boolean_icon` imports** (`display_for_field`, `display_for_value`). The vendored
  boolean rendering needs its own true/false/unknown representation that does not reference
  `django.contrib.admin.templatetags.admin_list` or admin's static SVGs. Since the framework
  already has a template-and-context contract (the idea's settled point: "Panels declare a
  template name and provide context... No `get_content() -> str`") rather than returning raw
  HTML strings, the natural rewrite is to return a plain boolean-ish value from the vendored
  display function and let the framework's own template layer choose how to render it (e.g. via
  `c-icon`, which the idea says the shell layer already uses) — that is a bigger behavioural
  departure from the original `_boolean_icon(value)` (which returns an `<img>` HTML string
  directly) than the other functions need, since every other branch of `display_for_field`/
  `display_for_value` returns a plain string or a `format_html` value, not something requiring a
  static asset.
- **The `model_admin` and `form` parameters** thread through `label_for_field` and `lookup_field`
  purely so the admin can look up a `short_description`/callable on the `ModelAdmin` class itself
  (not the model) or on a bound form field. A panel framework has neither concept — it has a
  `Panel` instance bound to a model instance, and (per this spec) no `ModelAdmin`-equivalent.
  Dropping these parameters is safe *and* is exactly what avoids the failure mode Wagtail's own
  `wagtail-modeladmin` package hit when it imported `label_for_field` directly rather than
  vendoring/adapting it: issue
  [wagtail/wagtail#6076](https://github.com/wagtail/wagtail/issues/6076) is a `list_export`
  method producing `AttributeError: Unable to lookup 'city' on Contact` because the call site
  never passed `model_admin`, so `hasattr(model_admin, name)` failed and the method fallback
  chain immediately fell through to `get_fields_from_path`, which also fails for a plain method
  name — this project's own resolver has an even blunter version of the same gap, since it does
  not have `model_admin`/`hasattr(model, name)` fallbacks *at all*. Vendoring gives the chance to
  make the model/instance-method fallback (`hasattr(model, name)`, already present in
  `label_for_field`'s step 2) the load-bearing path instead of a `model_admin`-shaped one that
  the framework has nothing to plug into.
- **Annotated querysets.** None of `_get_non_gfk_field`, `label_for_field`, or `lookup_field`
  know anything about `.annotate()` — an annotated attribute exists as a plain Python attribute
  on the fetched instance (Django attaches it via `__dict__`, not as a `Field` on `_meta`), so
  `opts.get_field(name)` always raises `FieldDoesNotExist` for it, and both `label_for_field` and
  `lookup_field` fall through to their attribute/callable branches exactly as they would for a
  `@property` — `hasattr(model, name)` is `False` for an annotation (it's not a class-level
  attribute, only an instance-level one after `.annotate()` + fetch), so `label_for_field` for a
  bare annotation name with no `model_admin`/`form` ends up in the final `else: label =
  pretty_name(name)` branch, and `lookup_field`'s fallback `getattr(obj, name, sentinel)` finds
  it as an ordinary instance attribute and returns it as `value` with `f = None`. This is
  **already exactly what a vendored copy gets for free**, since Django's own functions treat an
  annotation identically to a property once `_get_non_gfk_field` has rejected it — no extra
  branch is required for annotations specifically. Where the home-grown `_resolve_field` diverges
  is that it calls `obj._meta.get_field(field_name)` **unconditionally** and lets
  `FieldDoesNotExist` propagate uncaught, so an annotation crashes it exactly the same way a
  property or method does; the fix is catching that exception and falling through, which is the
  entire shape of what `label_for_field`/`lookup_field` already do.
- **Callables.** Both `label_for_field` and `lookup_field` accept `name` as an actual callable,
  not just a string — a panel could declare `fields = [some_function]` and both functions handle
  it (`callable(name)` is the very first check in each fallback branch). The home-grown resolver
  only ever accepts a string (`field_path: str` and `field_path.split(".")` assumes `str`), so
  supporting a bare callable in `fields` would be new surface, not a drop-in.
- **`django.contrib.auth` password-hash special case** in `display_for_field` — harmless to keep
  (it's a `contrib.auth`, not `contrib.admin`, import, and this project already has a custom
  `AUTH_USER_MODEL`) or harmless to drop; not core to the ask.

## 4. Licence and attribution — how other projects handle vendoring these helpers

Django is BSD-3-Clause, copyright "Django Software Foundation and individual contributors"
([LICENSE](https://github.com/django/django/blob/main/LICENSE)). The three conditions that bind
a vendored copy: retain the copyright notice and the license's list of conditions and disclaimer
in the vendored file's source distribution, do the same for any binary/packaged redistribution,
and do not use "Django" or its contributors' names to imply endorsement. In practice for a
vendored `.py` file this means: a header comment in the vendored module stating it is adapted
from `django/contrib/admin/utils.py`, under Django's BSD-3-Clause licence, with the copyright
line reproduced (or a pointer to Django's `LICENSE` file, which is the more common pattern below)
— there is no requirement to publish a separate `LICENSE` file per vendored module, but the
notice needs to travel with the source.

What comparable projects actually do, checked directly:

- **django-tables2** does not vendor or import `django.contrib.admin.utils` at all for its
  column-label logic. `BoundColumn.verbose_name`
  ([source](https://django-tables2.readthedocs.io/en/latest/_modules/django_tables2/columns/base.html))
  reimplements the "find the field, read its `verbose_name`, else derive from the accessor name"
  logic independently, using `django.utils.text.capfirst` on the fallback name — `capfirst`, not
  `.title()` — and explicitly does **not** apply `capfirst` when the source `verbose_name` is
  already `SafeData`/pre-formatted, to avoid double-mangling a value the model author already
  capitalised deliberately. No Django admin import, no licence-attribution burden beyond Django's
  ordinary "installed as a dependency" terms.
- **Wagtail**'s own generic admin table renderer
  (`wagtail/admin/ui/tables/__init__.py`) does the same independent reimplementation:
  `BaseColumn.__init__` sets `self.label = capfirst(name.replace("_", " "))` when no explicit
  label is given — again `capfirst`, not `.title()`, and again no import of `label_for_field`/
  `display_for_field`/`lookup_field`. Wagtail's `wagtail/admin/utils.py` imports nothing from
  `django.contrib.admin` at all; a different Wagtail module (`wagtail/admin/ui/tables/...`, table
  URL building) imports only `quote` from `django.contrib.admin.utils`, for primary-key URL
  escaping, not for labels or display values.
- **`wagtail-modeladmin`** (the package that carries what used to be
  `wagtail.contrib.modeladmin`, since Wagtail 3.0 split it out) is the one place in this survey
  that *does* import `label_for_field` from `django.contrib.admin.utils` directly rather than
  reimplementing it — and it hit exactly the class of bug this project's own resolver has, for
  the same underlying reason: the call site didn't carry the `model_admin` context
  `label_for_field` optionally wants, so a plain method name resolved via the model-attribute
  fallback broke. See
  [wagtail/wagtail#6076](https://github.com/wagtail/wagtail/issues/6076). This is direct evidence
  that a thin, unmodified `import label_for_field` (the alternative to vendoring that the idea
  explicitly rejects) is fragile in exactly the property/method-crash way already seen here, and
  that adapting the call site's arguments matters more than the vendoring-vs-importing choice by
  itself.
- **django-import-export**'s `Field` class
  ([`import_export/fields.py`](https://github.com/django-import-export/django-import-export/blob/main/import_export/fields.py))
  takes an explicit `column_name` and does not derive it from `verbose_name`/`capfirst` at all —
  a different design point (export columns are always explicitly named), not directly comparable
  to this project's "derive a label automatically" requirement, but a third confirmation that
  none of the surveyed CRUD-adjacent packages import Django's admin label helpers as their
  primary mechanism.

The pattern across all three real reimplementations (django-tables2, Wagtail's generic tables,
and this project's own `_resolve_field`) is the same instinct — "don't depend on
`contrib.admin`, derive the label yourself" — but only the home-grown one in this project got the
capitalisation function wrong (`.title()` instead of `capfirst`) and skipped the
`try`/`except FieldDoesNotExist` that both `label_for_field` and `lookup_field` rely on to fall
through to the callable/property/annotation branch instead of raising.

## 5. Drift risk across Django versions, and keeping a vendored copy honest

`admin/utils.py`'s git history
([github.com/django/django/commits/main/django/contrib/admin/utils.py](https://github.com/django/django/commits/main/django/contrib/admin/utils.py))
shows roughly half a dozen substantive commits a year, not a churn-heavy file, but not frozen
either. Changes found that land inside the 4.2→6.0 window and touch the functions this vendoring
cares about:

- **Django 5.1** (2024): related-field lookups (`"cohort__name"`-style `__` paths) became usable
  directly in `ModelAdmin.list_display`, exercising `label_for_field`'s
  `get_fields_from_path`/`NotRelationField` fallback branch far more than before (previously that
  branch existed but was rarely hit by ordinary admin configs, since `list_display` conventionally
  named plain fields or methods). A side effect documented independently by a third party
  ([loopwerk.io, "Changing the way Django 5.1 generates admin list labels"](https://www.loopwerk.io/articles/2024/changing-django51-lookup-labels/)):
  a related-field path label is built from the **entire path** (e.g. `"account_settings__pace_
  account_id"` labels as "Account Settings Pace Account Id", not just the final field's own
  `verbose_name`), which the article's author found surprising enough to patch around locally.
  This is exactly the "related-field paths (`cohort__name`)" pitfall the idea flags in §5 below —
  a vendored copy that supports `__`-path labels inherits this same "label = full path, not just
  the leaf field" behaviour unless it deliberately overrides it.
- **Django 5.2 / early 5.x (ticket #10743, landed 2024-02-05):** "Allowed lookups for related
  fields in `ModelAdmin.list_display`" — the underlying change that made the above possible;
  ordering for such lookups followed in a related commit.
- **2024-01-10, ticket #28404:** "Made displaying values in admin respect Field's `empty_values`"
  — changed `display_for_value`'s (and by extension `display_for_field`'s) empty-value check to
  use the specific field's `empty_values` rather than a single hard-coded emptiness test; this is
  the behaviour a vendored copy should replicate (field-specific emptiness, e.g. a
  `DecimalField`'s `0` is not necessarily "empty" the way `None`/`""` are) rather than a single
  blanket falsy check.
- **2025-01-10, ticket #36032** and **2025-01-08, ticket #36063:** `display_for_field` gained
  link-rendering for `URLField` values and FileField navigation behaviour — both are the kind of
  admin-changelist-specific convenience (clickable links inside a read-only list) that a
  panel-framework display helper may or may not want; worth a conscious decision either way
  rather than blind inheritance.
- **2026, CVE-2026-15920:** a security fix made `display_for_field` validate URLs before
  rendering them as links — evidence that this file is squarely in Django's security-patch
  surface, not just a stable utility grab-bag; a vendored copy that keeps the URL-link rendering
  branch inherits responsibility for that validation itself, since it will not receive Django's
  patch automatically.

A way to keep a vendored copy honest, given this drift rate: a test that imports **both** the
vendored functions and Django's own `django.contrib.admin.utils` functions (already present in
the environment as a transitive dependency of `django.contrib.admin`, even if `contrib.admin` is
never added to `INSTALLED_APPS` — importing the module does not require the app being installed,
only *using* admin-site-registration features does) and asserts they agree on a fixed matrix of
inputs (a plain field, a choices field, a boolean field, a nullable field with `None`, a
`__`-path across a relation, a property, a method, and — separately, since Django's functions
don't need `INSTALLED_APPS` admin registration to be called directly — an annotated queryset
value). Such a test would need to explicitly encode the places the vendored copy is *meant* to
diverge (dropping `_boolean_icon`'s HTML/static-asset output, dropping the `model_admin`/`form`
parameters, any decision on link-rendering) so that a Django upgrade's `git diff` against
`admin/utils.py` is the trigger for revisiting the test's expected-divergence list, rather than
the test silently drifting out of sync with a moving target.

## 6. Acronym and label pitfalls, concretely

- **`capfirst` vs `.title()`.** `capfirst` (`django.utils.text.capfirst`) is
  `s[0].upper() + s[1:]` in spirit (one-character change); `.title()` re-cases the *entire*
  string word by word, lower-casing every character that isn't the first of a word. Any
  `verbose_name` containing an acronym, an already-capitalised proper noun, or mixed case is
  mangled by `.title()` and preserved by `capfirst`. This project's live example that would
  surface it: `CohortDetailsPanel`'s `fields = ["name"]` and `LearnerDetailsPanel`'s `user.
  first_name`/`last_name`/`email` all happen to be single lower-case words, so `.title()` and
  `capfirst` agree today — the bug is real but has had no acronym-bearing field to expose it yet.
- **`verbose_name` already set.** Neither Django's `label_for_field` nor the home-grown resolver
  apply *any* capitalisation to a field's own `verbose_name` — `label_for_field` returns
  `field.verbose_name` untouched (Django's admin templates apply `capfirst` later, at render
  time, in `django/contrib/admin/templatetags/admin_list.py`'s `result_headers`, not in
  `utils.py`). If a model declares `verbose_name = "SAT score"` explicitly, Django's approach
  (defer capitalisation to a single `capfirst` call at the point of display) preserves the
  acronym; a resolver that runs `.title()` on every label regardless of source, as the home-grown
  one does, mangles a hand-authored `verbose_name` just as readily as an auto-derived one. A
  vendored copy should apply its capitalisation step once, at render/template time on the final
  string, mirroring where Django itself does it, rather than baking `capfirst`/`.title()` into
  the per-field resolution function.
- **Related-field paths (`cohort__name`).** Two independent pitfalls compound: (1) as found in
  §5, Django 5.1's own `label_for_field` labels a `__` path using the **entire path**
  (`pretty_name` of the joined-and-underscored string, capitalised as one label), not just the
  leaf field's `verbose_name` — `"cohort__name"` labels as "Cohort Name" only because
  `pretty_name` replaces `_` with space and capitalises, which happens to look reasonable for a
  two-segment path but degrades for a longer one (the loopwerk example: "Account Settings Pace
  Account Id" for a three/four-segment path); (2) this project's own dot-notation convention
  (`"user.first_name"`) is the *opposite* separator from Django's `__`, so a vendored copy that
  wants to reuse `get_fields_from_path`/`_get_non_gfk_field` as-is either needs to accept `__`
  paths going forward (a behaviour change for `fields = [...]` declarations, since today's are
  `.`-separated) or needs to translate `.` to `__` before delegating to the vendored functions —
  a decision this research surfaces but does not make, per the instruction not to propose
  implementation.

## Sources

- [`django/contrib/admin/utils.py` at `main`](https://github.com/django/django/blob/main/django/contrib/admin/utils.py) — current Django source, read alongside the project's own installed copy.
- [Django `LICENSE`](https://github.com/django/django/blob/main/LICENSE) — BSD-3-Clause text and copyright holder.
- [django/contrib/admin/utils.py commit history](https://github.com/django/django/commits/main/django/contrib/admin/utils.py) — drift/change frequency.
- [django-tables2 `columns/base.html` source](https://django-tables2.readthedocs.io/en/latest/_modules/django_tables2/columns/base.html) — `BoundColumn.verbose_name`, `capfirst` usage, no admin import.
- [`wagtail/admin/ui/tables/__init__.py`](https://github.com/wagtail/wagtail/blob/main/wagtail/admin/ui/tables/__init__.py) — `BaseColumn` label derivation via `capfirst`.
- [`wagtail/admin/utils.py`](https://github.com/wagtail/wagtail/blob/main/wagtail/admin/utils.py) — no `contrib.admin` imports.
- [wagtail/wagtail issue #6076](https://github.com/wagtail/wagtail/issues/6076) — `label_for_field` `AttributeError` for a ModelAdmin method when `model_admin` context isn't threaded through, in `wagtail-modeladmin`'s `list_export`.
- [django-import-export `import_export/fields.py`](https://github.com/django-import-export/django-import-export/blob/main/import_export/fields.py) — explicit `column_name`, no admin-utils dependency.
- [Loopwerk: "Changing the way Django 5.1 generates admin list labels"](https://www.loopwerk.io/articles/2024/changing-django51-lookup-labels/) — Django 5.1 related-lookup label behaviour and its full-path labelling quirk.
- [Django ticket #10743](https://code.djangoproject.com/ticket/10743) — "Allowed lookups for related fields in `ModelAdmin.list_display`," the change behind the above.

---
status: ok
