# Templates and Cotton Components

## Template Locations

```
freedom_ls/<app_name>/templates/
├── <app_name>/         # Page templates (app-namespaced)
├── cotton/             # Cotton components
└── partials/           # Template partials
```

**Base template:** `freedom_ls/base/templates/_base.html`

## Naming Conventions

- **Pages:** `freedom_ls/<app_name>/templates/<app_name>/<page>.html`
- **Cotton components:** `freedom_ls/<app_name>/templates/cotton/<component>.html`
- **Partials:** `freedom_ls/<app_name>/templates/partials/<partial>.html`

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

**Location:** `freedom_ls/<app_name>/templates/cotton/<name>.html`

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

### Best Practices

1. Define all props in `<c-vars>` with defaults
2. Support `class` and `{{ attrs }}` for flexibility
3. Use `{{ slot }}` for content
4. Include usage examples in comments
5. Don't reimplement existing components

## Template Partials

### Separate Files

**Location:** `freedom_ls/<app_name>/templates/partials/<name>.html`

```django
<!-- Include in template -->
{% include "partials/header.html" %}

<!-- Load via HTMX -->
<div hx-get="{% url 'app:partial' %}" hx-trigger="load"></div>
```

### Inline Partials (django-template-partials)

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

HTMX loaded globally. CSRF token set in `_base.html`.

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

Loaded globally for reactive components.

```django
<div x-data="{ open: false }">
    <c-button @click="open = !open">Toggle</c-button>
    <div x-show="open">Content</div>
</div>
```

## Workflow

### Creating Templates

1. **Check location** - `freedom_ls/<app_name>/templates/<app_name>/`
2. **Check existing templates** - Follow established patterns
3. **Check available components** - `ls freedom_ls/*/templates/cotton/`
4. **Check Tailwind classes** - `cat tailwind.components.css`
5. **Write template** - Extend `_base.html`, use existing components
6. **Build CSS** - `npm run tailwind_build`

### Editing Templates

1. Read the template
2. Understand structure (blocks, components, HTMX)
3. Check dependencies (partials, components)
4. Make focused changes
5. Don't refactor unnecessarily

## Key Rules

1. **Don't check `tailwind.components.css` first** - Use component classes
2. **Don't duplicate base styles** - Typography/forms are pre-styled
3. **Don't create cotton components for one-off use** - Use partials
4. **Don't hardcode URLs** - Use `{% url %}` tag
5. **Don't skip app namespacing** - Templates in `<app_name>/` subdirectory
