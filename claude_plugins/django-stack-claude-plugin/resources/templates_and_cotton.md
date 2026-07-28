# Templates and Cotton Components

## Template Locations

```
<app>/templates/
├── <app_name>/         # Page templates (app-namespaced)
│   └── partials/       # Template partials (also app-namespaced)
└── cotton/             # Cotton components (app-specific)

templates/              # project-level template dir (on TEMPLATES['DIRS'])
├── cotton/             # Shared / design-system cotton components
└── _base.html          # Base template
```

**Cotton components can live in either place** — django-cotton discovers `templates/cotton/` on any
template-loader path. Use a **project-level `templates/cotton/`** for shared, design-system components
used across apps (e.g. `<c-button>`, `<c-card>`), and an **app-local `<app>/templates/cotton/`** for
components specific to one app. Follow whichever layout the project already uses.

**Base template:** `_base.html`, typically at the project-level `templates/_base.html` (or a base
app's `templates/`).

## Naming Conventions

- **Pages:** `<app>/templates/<app_name>/<page>.html`
- **Cotton components:** `templates/cotton/<component>.html` (shared) or
  `<app>/templates/cotton/<component>.html` (app-specific)
- **Partials:** `<app>/templates/<app_name>/partials/<partial>.html`

## Standard Page Template

```django
{% extends '_base.html' %}

{% block title %}Page Title{% endblock %}

{% block content %}
    <div class="space-y-6">
        <h1>{{ page_title }}</h1>
        <!-- Content -->
    </div>
{% endblock %}
```

## Common Blocks

From `_base.html`:
- `{% block title %}` - Page title
- `{% block content %}` - Main content
- `{% block header %}` - Header section
- `{% block extra_head %}` - Additional head content
- `{% block extra_body %}` - After main content

## Cotton Components

Reusable UI components using `<c-component-name>` syntax.

### Creating a Component

**Location:** `templates/cotton/<name>.html` for a shared/design-system component, or
`<app>/templates/cotton/<name>.html` for an app-specific one.

```django
<c-vars
    prop1="default"
    prop2=""
    class=""
/>

<div class="{{ class }}" {{ attrs }}>
    {{ slot }}
</div>

{% comment %}
Usage:
<c-name prop1="value">Content</c-name>
{% endcomment %}
```

### Using Components

```django
<c-button>Click me</c-button>
<c-button variant="primary" href="/url">Link</c-button>
<c-loading-indicator id="loader" message="Loading..." />
<c-modal id="confirm" title="Confirm">Are you sure?</c-modal>
```

**These names are illustrative.** `ds` ships no component library and guarantees no component name —
`<c-button>`, `<c-loading-indicator>` and `<c-modal>` are just plausible examples. List what this
project actually defines (`ls templates/cotton/ */templates/cotton/`) before using any of them, and use
plain HTML where there is no component.

### Best Practices

1. Define all props in `<c-vars>` with defaults
2. Support `class` and `{{ attrs }}` for flexibility
3. Use `{{ slot }}` for content
4. Include usage examples in comments
5. Don't reimplement existing components

## Template Partials

### Separate Files

**Location:** `<app>/templates/<app_name>/partials/<name>.html` — namespace partials under the app
directory just like pages, so two apps can each have a `header.html` without colliding on the loader
path.

```django
<!-- Include in template -->
{% include "<app_name>/partials/header.html" %}

<!-- Load via HTMX -->
<div hx-get="{% url 'app:partial' %}" hx-trigger="load"></div>
```

### Inline Partials (Django built-in)

Inline partials are a Django 6+ built-in feature (`{% partialdef %}` / `{% partial %}` tags are part of the Django Template Language).

```django
{% partialdef "partial_name" %}
    <!-- content -->
{% endpartialdef %}

<!-- Use it -->
{% partial "partial_name" %}

<!-- Pass context -->
{% with foo=bar %}
    {% partial "partial_name" %}
{% endwith %}
```

**Note:** Use `{% with %}` to pass context, NOT `{% partial "name" foo=bar %}`

## HTMX Integration

HTMX loaded globally. CSRF token set in `_base.html` via `hx-headers`. Do not add CSRF tokens to individual requests.

### View Conventions

- Prefix view functions returning partials with `partial_` (e.g., `partial_comment_list`, `partial_article_row`)
- Return standard `render(request, template, context)` — no special HTMX response classes needed
- Return HTTP 422 for HTMX validation errors

### Partialdef Naming

- Use kebab-case names for `{% partialdef %}` blocks (e.g., `{% partialdef view-detail-button %}`)

### Common Patterns

```django
<!-- Load on page load -->
<div hx-get="{% url 'app:endpoint' %}" hx-trigger="load"></div>

<!-- Form submission -->
<form hx-post="{% url 'app:submit' %}" hx-target="#result">
    <c-button type="submit">Submit</c-button>
</form>

<!-- Click to load -->
<c-button hx-get="{% url 'app:more' %}" hx-target="#content">
    Load More
</c-button>
```

## Alpine.js

Loaded globally for reactive components. **The exact syntax depends on the project's Alpine build** —
read `.claude/ds/config.md` → `## Alpine.js` → `CSP build` and follow the `ds:alpine-js` skill:

- **CSP build `disabled`** (standard build) — inline expressions are allowed:

  ```django
  <div x-data="{ open: false }">
      <c-button @click="open = !open">Toggle</c-button>
      <div x-show="open">Content</div>
  </div>
  ```

- **CSP build `enabled`** (default) — inline expressions are forbidden; reference a registered
  `Alpine.data()` component instead:

  ```django
  <div x-data="toggle">
      <c-button x-on:click="toggle">Toggle</c-button>
      <div x-show="open">Content</div>
  </div>
  ```

See the `ds:alpine-js` skill (and `alpine_csp_build.md` / `alpine_no_csp.md`) for the full rules.

## Workflow

### Creating Templates

1. **Check location** - `<app>/templates/<app_name>/`
2. **Check existing templates** - Follow established patterns
3. **Check available components** - `ls templates/cotton/ */templates/cotton/` (project-level + app-local)
4. **Check reusable styles** - reuse existing cotton components; if the project has a
   `tailwind.components.css`, check it too (`cat tailwind.components.css`)
5. **Write template** - Extend `_base.html`, use existing components
6. **Build CSS** - `npm run tailwind_build`

### Editing Templates

1. Read the template
2. Understand structure (blocks, components, HTMX)
3. Check dependencies (partials, components)
4. Make focused changes
5. Don't refactor unnecessarily

## Key Rules

1. **Reuse before styling** - use existing cotton components (and `tailwind.components.css` classes if
   the project has that file) before writing raw utilities
2. **Don't duplicate base styles** - Typography/forms are pre-styled
3. **Don't create cotton components for one-off use** - Use partials
4. **Don't hardcode URLs** - Use `{% url %}` tag
5. **Don't skip app namespacing** - Page templates in `<app_name>/` subdirectory
