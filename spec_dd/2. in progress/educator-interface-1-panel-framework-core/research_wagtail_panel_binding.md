# Wagtail's panel API as prior art

Sources are Wagtail's `stable`/`main` docs and source (current major series, v6/v7 era, September
2026). Wagtail is read here as prior art only — nothing below proposes installing it or naming FLS
things after it.

## 1. `Panel` / `BoundPanel`: definition-time vs render-time binding

Wagtail went through exactly the split this idea commits to, and gives it a name: **panel
*definition*** (`Panel`, built once at class-definition/import time, holds `heading`, `classname`,
`help_text`, `base_form_class`, `icon`, `attrs`) versus **panel *binding*** (`Panel.BoundPanel`,
built fresh per request, holds `instance`, `request`, `form`, `prefix`).
(https://docs.wagtail.org/en/stable/reference/panel_api.html)

Definition-time (`Panel`):

```python
def __init__(self, heading="", classname="", help_text="",
             base_form_class=None, icon="", attrs=None): ...

def bind_to_model(self, model):
    new = self.clone()
    new.model = model
    new.on_model_bound()
    return new

def on_model_bound(self):
    """subclass hook, called once model is known"""

def get_bound_panel(self, instance=None, request=None, form=None, prefix="panel"):
    if self.model is None:
        raise ImproperlyConfigured(
            "%s.bind_to_model(model) must be called before get_bound_panel"
            % type(self).__name__
        )
    if not issubclass(self.BoundPanel, Panel.BoundPanel):
        raise ImproperlyConfigured(
            "%s.BoundPanel must be a subclass of Panel.BoundPanel" % type(self).__name__
        )
    return self.BoundPanel(panel=self, instance=instance, request=request,
                            form=form, prefix=prefix)

def clone(self):
    return self.__class__(**self.clone_kwargs())

def clone_kwargs(self):
    return {"icon": self.icon, "attrs": self.attrs, "heading": self.heading,
            "classname": self.classname, "help_text": self.help_text,
            "base_form_class": self.base_form_class}
```
(https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/panels/base.py)

Render-time (`BoundPanel`, itself a `laces.Component`):

```python
def __init__(self, panel, instance, request, form, prefix):
    self.panel = panel
    self.instance = instance
    self.request = request
    self.form = form
    self.prefix = prefix
    self.heading = self.panel.heading
    self.help_text = self.panel.help_text

def is_shown(self):
    """Whether this panel should be rendered; if false, it is skipped in the
    template output."""
    return True

def show_panel_furniture(self):
    return self.is_shown()

def get_context_data(self, parent_context=None):
    context = super().get_context_data(parent_context)
    context["self"] = self
    context["attrs"] = self.attrs
    return context
```
(https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/panels/base.py)

`Panel` is deliberately model-agnostic until `bind_to_model` runs: a panel definition is written
once (often at import time, on a class-level `panels = [...]` list) and reused across every
request. `bind_to_model` never mutates the original — it clones first, so the same declared panel
list can be bound to more than one model/purpose without cross-talk. That immutability is the
whole reason `clone()`/`clone_kwargs()` exist: **every** `Panel.__init__` override must be paired
with a `clone_kwargs()` override that round-trips its new constructor arguments, or `clone()`
silently drops them the next time the panel is cloned (which happens on every `bind_to_model`
call, i.e. every model class that reuses the panel list). This is the sharpest subclass footgun in
the API and is exactly what a third party ran into live in Wagtail's own GitHub Discussions when
porting a custom `RegexPanel` to 3.0 (had to update both `clone_kwargs()` and move
`on_form_bound()` logic into a `BoundPanel.__init__`) — https://github.com/wagtail/wagtail/discussions/8362.

Container panels (`PanelGroup` — abstract base for `ObjectList`, `TabbedInterface`,
`MultiFieldPanel`, `FieldRowPanel`) bind their children as part of `on_model_bound`, not eagerly:

```python
class PanelGroup(Panel):
    """Abstract class for panels that manage a set of sub-panels.
    Concrete subclasses must attach a 'children' property"""

    def __init__(self, children=(), *args, **kwargs):
        permission = kwargs.pop("permission", None)
        super().__init__(*args, **kwargs)
        self.children = children
        self.permission = permission

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs["children"] = self.children
        kwargs["permission"] = self.permission
        return kwargs

    def on_model_bound(self):
        from .model_utils import expand_panel_list
        child_panels = expand_panel_list(self.model, self.children)
        self.children = [child.bind_to_model(self.model) for child in child_panels]
```
(https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/panels/group.py)

At render time, `PanelGroup.BoundPanel` builds one `BoundPanel` per child by calling
`child.get_bound_panel(instance=self.instance, request=self.request, form=self.form, prefix=...)`
— i.e. the container passes its own render-time context down to every child rather than each
child re-deriving it. `TabbedInterface` and `ObjectList` are both thin `PanelGroup` subclasses that
add nothing but a `BoundPanel.template_name`
(`wagtailadmin/panels/tabbed_interface.html`, `wagtailadmin/panels/object_list.html`);
`MultiFieldPanel` and `FieldRowPanel` likewise only add a template
(`multi_field_panel.html`, `field_row_panel.html`). Composition is genuinely uniform: a tab set is
"a `PanelGroup` with a different template", not a distinct concept — which is the same design
choice this idea makes ("A tab set is a container panel with children").

**What the split buys:** one declared panel tree serves every request and every model reuse
safely; permission/visibility/context all belong to the per-request `BoundPanel` and never leak
back into the shared definition; nested composition (tabs containing field-row panels containing
field panels) needs no special-casing because containers and leaves share one interface
(`get_bound_panel`, `is_shown`, `render_html`).

**What it costs:** two classes per concept (a `Panel` and a nested `Panel.BoundPanel`) for even
the simplest custom panel; a mandatory, easy-to-forget `clone_kwargs()` override for any new
constructor argument; and the general subclass-authoring overhead of remembering which state lives
on which half (put render-time state on `BoundPanel.__init__`, not `Panel.__init__` — the latter
runs once at import time and is shared/cloned across every request).

## 2. Permission / visibility

Most panel types, including the leaf `FieldPanel` and the container `MultiFieldPanel` /
`FieldRowPanel` / (via `PanelGroup`) `TabbedInterface` / `ObjectList`, accept a `permission` kwarg:
"a permission codename such as `'myapp.change_blog_category'`" — if the current user lacks it, the
panel (or, for a group, the whole group and its children) is omitted from the form. Superusers
pass automatically, so an arbitrary nonsense codename such as `'superuser'` is the documented
idiom for "admin only." (https://docs.wagtail.org/en/stable/reference/pages/panels.html,
"Panel customization" → "Permissions")

`PanelGroup.__init__` pops `permission` out of kwargs and stores it on the definition; visibility
resolves on the bound side:

```python
# PanelGroup.BoundPanel.is_shown (paraphrased from source):
# 1. if self.panel.permission and not self.request.user.has_perm(self.panel.permission): return False
# 2. return any(child.is_shown() for child in self.children)
```
and:
```python
visible_children = [child for child in self.children if child.is_shown()]
show_panel_furniture = any(child.show_panel_furniture() for child in self.children)
```
(https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/panels/group.py)

Two consequences follow directly from `any(child.is_shown() ...)`: a tab (an `ObjectList` inside a
`TabbedInterface`) whose every child panel is hidden by permission is itself not shown — the tab
strip does not render an empty tab, it disappears. And `show_panel_furniture` — separate from
`is_shown` — lets a group render its children's content without its own wrapper chrome (heading,
border) when none of the children need furniture, which is how Wagtail avoids a container that is
"visible" but visually empty scaffolding.

The base `Panel.BoundPanel.is_shown()` defaults to `True` and takes no arguments beyond `self`; a
leaf panel subclass overrides it to consult `self.request`/`self.instance` itself (there is no
separate `has_permission(request)` signature at the base — permission is folded into `is_shown()`
for groups, or left to a leaf's own override).

## 3. Rendering: `template_name`, `get_context_data`, `laces.Component`

`BoundPanel` (and `Panel` itself, historically) inherits from `laces.Component`
(https://docs.wagtail.org/en/stable/extending/template_components.html) — a small library Wagtail
extracted from itself starting at 6.0 "to make the concept of 'template components' available to
the wider Django ecosystem." Its contract:

- `render_html(parent_context=None)` — returns the string to insert into the calling template. It
  is *not* rendered with a fresh, empty context: it receives the parent template's context
  dictionary, specifically so a component's `get_context_data` can read ambient values it did not
  declare itself (e.g. `request`, `csrf_token`) without the caller having to thread them through
  explicitly.
- `template_name` — the preferred subclass contract: set `template_name` and override
  `get_context_data(parent_context)` to add variables; the base `render_html` renders that template
  with the augmented context. A subclass can point `template_name` at a template that
  `{% extends %}`/`{% block %}`s a shared parent template, which is how a `BoundPanel` subclass
  wraps common panel furniture (border, heading, actions) while injecting its own body — the same
  "provide a template + context, let the container render it" contract this idea specifies.
- `media` — a Django form-`Media`-shaped object (inner `Media` class or dynamic `media` property)
  declaring JS/CSS the component needs. Callers aggregate recursively: `media = Media(); for panel
  in panels: media += panel.media`, then emit the combined result once. This is how JS/CSS
  dependencies compose across an arbitrarily nested panel tree without each leaf template
  `{% static %}`-including its own assets redundantly.
- The `{% component %}` template tag (`wagtailadmin_tags`) exists specifically because a bare
  `{{ some_component }}` variable interpolation does not forward the calling context — `{% component
  my_panel %}` (with optional `with`/`only`/`as`) is the documented way to render a nested component
  from inside a template and have `parent_context` actually reach it.

## 4. System checks on declarative config

Wagtail's own admin app registers checks in `wagtail/admin/checks.py`
(https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/checks.py), tagged so they
run as part of `manage.py check`:

- `wagtailadmin.E002` (`get_form_class_check`, `@register(Tags.admin)`) — iterates every page
  model, calls `cls.get_edit_handler().get_form_class()`, and errors if the resulting form class
  does not subclass `WagtailAdminPageForm`:
  ```python
  Error(
      "{cls}.get_edit_handler().get_form_class() does not extend WagtailAdminPageForm".format(cls=cls.__name__),
      hint="Ensure that the panel definition for {cls} creates a subclass of WagtailAdminPageForm".format(cls=cls.__name__),
      obj=cls, id="wagtailadmin.E002",
  )
  ```
  This is a genuine **panel-tree-shape check that runs at `manage.py check` time**, by actually
  building the panel-derived form class for every registered model and inspecting its MRO — the
  same category of check the idea wants for model-bound panels.
- `wagtailadmin.W002` (`inline_panel_model_panels_check`, `@register("panels")`) — walks every page
  model's declared `content_panels`/`promote_panels`/`settings_panels` looking for `InlinePanel`s
  that reference a related model whose own edit handler is unset, and warns
  `"{}.{} will have no effect on {} editing"` — i.e. it catches a panel declaration that is
  syntactically fine but semantically inert, deduplicating repeated warnings for the same model.
- By contrast, a `FieldPanel` naming a field that does not exist on the bound model is **not**
  caught by a registered system check — it surfaces later, when Django's `modelform_factory`
  machinery builds the form fields (i.e. effectively at `bind_to_model`/form-construction time,
  which happens on first admin page load or whenever something forces the check, not necessarily
  at `manage.py check`). No dedicated `wagtailadmin.Exxx` exists for "unknown field named in a
  panel," per Wagtail's own checks module and the absence of one in searches of Wagtail's issue
  tracker.
- Django's own `contrib.admin` checks framework (not Wagtail, but the same "declarative config,
  validate at check time" idea and directly comparable to the `E001` precedent in
  `freedom_ls/base/app_settings.py`) has an analogous long-standing check, `admin.E108`: "The value
  of `list_display[n]` refers to `<name>`, which is not a callable, an attribute of
  `<ModelAdmin>`, or an attribute or method on `<model>`." It is raised by
  `ModelAdmin.check()`/`_check_list_display_item`, runs under `manage.py check`, and is reported
  with `obj=` set to the offending `ModelAdmin` class so the error message names exactly which
  admin class and which declared item is wrong.

## 5. Known complaints / upgrade pain

Wagtail 3.0 (2022) renamed the whole area: `wagtail.admin.edit_handlers` →
`wagtail.admin.panels`, `EditHandler` → `Panel`, `BaseCompositeEditHandler` → `PanelGroup`,
templates from `wagtailadmin/edit_handlers/` to `wagtailadmin/panels/`
(https://docs.wagtail.org/en/stable/releases/3.0.html). Beyond the rename, it introduced the
`Panel`/`BoundPanel` split itself (previously binding state lived directly on the one
`EditHandler` instance, mutated in place per-request — the opposite of this idea's "class-def-time
binding split from render-time binding," and a design Wagtail moved *away from* toward the split
this idea proposes). Concretely for subclass authors:

- `on_request_bound`, `on_instance_bound`, `on_form_bound` were deprecated/removed; equivalent
  logic must move into a `BoundPanel` subclass's own `__init__`, where `self.panel`, `self.request`,
  `self.instance`, `self.form` are available. Only `model` and `on_model_bound` remain on the
  unbound `Panel` side.
- `widget_overrides`, `required_fields`, `required_formsets` were deprecated in favour of one
  `get_form_options()` returning `{"fields": ..., "formsets": ..., "widgets": ...}` — i.e. Wagtail
  collapsed several parallel per-concern hook methods into one aggregate method, the inverse
  direction from the multiple-small-hooks style.
- The release notes state plainly: "It is no longer possible to vary or patch the form class in
  response to per-request information" — request-time customisation is meant to flow through the
  new `permission` kwarg or through overriding a form class's own `__init__`, not by mutating the
  edit-handler tree per request. That is a direct consequence of the split: the definition-time
  `Panel` tree is shared and must not carry per-request mutation.
- A real-world port (Wagtail Discussions #8362, a custom `RegexPanel`) confirms the two concrete
  failure modes: forgetting to update `clone_kwargs()` for a new constructor argument, and leaving
  request-binding logic in a now-removed hook instead of a `BoundPanel.__init__`.
  (https://github.com/wagtail/wagtail/discussions/8362)

## 6. Lessons for FLS

**Copy:**
- The two-sided contract — an immutable, reusable definition object plus a lightweight per-request
  bound object built by a single factory method (`get_bound_panel`/equivalent) — is the right shape
  for "class-definition-time binding split from render-time binding." Wagtail arrived at it *by
  moving away from* per-request mutation of one long-lived object, which is corroborating evidence,
  not just a starting design.
- Treating a container (tab set, panel stack) as "just another panel with a template and children,"
  where children are bound through the same one method the leaves use, is what makes composition
  uniform instead of tabs being a special case. It also makes "does this container have anything to
  show" fall out of a plain `any(child visible)` over children, rather than needing separate logic —
  applicable directly to "hidden children affect tabs."
- Running the check that actually builds/binds the declared tree against its model at `manage.py
  check` time (as `wagtailadmin.E002` does, and as `admin.E108` does for `ModelAdmin`) rather than
  only validating shape — i.e. binding for real and catching what binding throws — catches more than
  a shallow "is this a known field name" scan would.
- Passing the caller's context into a component's render call (`render_html(parent_context)`) is
  what makes "a subclass wraps a parent template" *and* ambient values (request, base URL) reach a
  panel without every leaf threading them through kwargs by hand.

**Avoid, given FLS panels render outside a form and are addressed by URL:**
- Wagtail's split exists largely to serve a `ModelForm` built once from the whole panel tree
  (`get_form_class`, `get_form_options` aggregating `fields`/`formsets`/`widgets` across every
  descendant). FLS panels are not assembling one form across a tree — there is no equivalent
  aggregate-then-build-a-form step to replicate, and importing that machinery (or its shape) would
  add a concept FLS's URL-addressed, independently-refreshable panels do not need.
- Wagtail's explicit 3.0 restriction — "no varying the form class per request" — is a real
  constraint *of building one shared form object*; it does not apply to FLS's model, where every
  panel is already resolved against a live `request` at render time (`get_queryset(request)` is
  the documented single scoping seam). Nothing here argues for adding a Wagtail-style prohibition
  on request-time variation — FLS's per-request binding already permits what Wagtail had to give up.
  freedom to gain.
- `clone()`/`clone_kwargs()` is the costliest piece of Wagtail's API for a subclass author and its
  proven failure mode (silently dropped constructor args on clone) is worth designing away from
  rather than reproducing: FLS's model, `manage.py check` binds each class *once* (validating field
  paths etc.), and instances are built fresh per request from the declared class rather than via a
  clone-and-mutate chain — so there is no forced spot where a maintainer must remember to update a
  second method every time they add a constructor argument to a `Panel` subclass, unless a clone
  step is deliberately introduced later.
- `is_shown()` folding visibility and permission into one boolean with no arguments (it reads
  `self.request` already stored on the bound instance) is a smaller, plainer surface than a
  same-named-but-differently-shaped `has_permission(request)`; the two are not interchangeable
  signatures and mixing the vocabulary between them in FLS's own docs would be worth avoiding.

## Sources

- https://docs.wagtail.org/en/stable/reference/panel_api.html
- https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/panels/base.py
- https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/panels/group.py
- https://docs.wagtail.org/en/stable/reference/pages/panels.html
- https://docs.wagtail.org/en/stable/extending/template_components.html
- https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/admin/checks.py
- https://docs.wagtail.org/en/stable/releases/3.0.html
- https://github.com/wagtail/wagtail/discussions/8362
- Django's `contrib.admin` system checks (`admin.E108`, `ModelAdmin._check_list_display_item`) —
  cited from established Django documentation/source knowledge as the direct precedent alongside
  Wagtail's own `wagtailadmin.E002`/`W002` for "validate declarative config at `manage.py check`
  time," matching the pattern in `freedom_ls/base/app_settings.py`'s `E001`.

status: ok
